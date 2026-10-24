"""Development environment for the Refine add-on (stdlib only).

    py scripts/devenv.py venvs [--python PATH]           PyPI builds of 25.09 / 26.09
    py scripts/devenv.py targets
    py scripts/devenv.py setup <target> [--fresh] [--probe]
    py scripts/devenv.py run <target> [--port 8080]      interactive dev Anki
    py scripts/devenv.py snapshot <target>... [--all]    automated probe run
    py scripts/devenv.py shots <target>... [--all] [--keep-profile]   PNG screenshots
    py scripts/devenv.py report                          cross-version report

Every target runs from an isolated base folder under .anki-dev/<target>/ and
uses its own single-instance key, so it never touches, and never hands off
to, your everyday Anki profile or a running Anki window.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from devtools.htmlinventory import inventory_file  # noqa: E402

DEV_BASE = ROOT / ".anki-dev"
OUT = ROOT / "out" / "m0"
FIXTURES = ROOT / "tests" / "contract" / "fixtures"
ADDON_SRC = ROOT / "src" / "refine"
PROBE_SRC = ROOT / "devtools" / "m0_probe"
UI_OUT = ROOT / "out" / "ui"
UI_PROBE_SRC = ROOT / "devtools" / "ui_probe"
IS_WIN = sys.platform == "win32"


@dataclass
class Target:
    name: str
    command: list[str]
    note: str

    def available(self) -> bool:
        return Path(self.command[0]).exists()


def _targets() -> dict[str, Target]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    scripts = "Scripts" if IS_WIN else "bin"
    exe = "anki.exe" if IS_WIN else "anki"
    venv = ROOT / ".venv"
    items = [
        Target(
            "26.09.3-installed",
            [str(local / "Programs" / "Anki" / "anki.exe")],
            "the Anki build users actually run (official installer)",
        ),
        Target(
            "26.09.3-pypi",
            [str(venv / "anki-26.9.3" / scripts / exe)],
            "aqt[qt]==26.9.3 from PyPI (PyQt6 6.11.0 / WebEngine 6.11.2)",
        ),
        Target(
            "25.09.5-pypi",
            [str(venv / "anki-25.9.5" / scripts / exe)],
            "aqt[qt]==25.9.5 from PyPI (PyQt6 6.9.1 / WebEngine 6.8.2, the pins of 25.09)",
        ),
    ]
    return {t.name: t for t in items}


TARGETS = _targets()

# ----------------------------------------------------------------- linking


def _is_link(p: Path) -> bool:
    if p.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if is_junction and is_junction(p):
        return True
    if IS_WIN and p.exists():
        try:
            return bool(os.lstat(p).st_file_attributes & 0x400)  # REPARSE_POINT
        except (AttributeError, OSError):
            return False
    return False


def _link(link: Path, target: Path) -> None:
    if _is_link(link):
        _unlink(link)
    elif link.exists():
        raise SystemExit(f"refusing to replace a real folder with a link: {link}")
    if IS_WIN:
        # junctions need no admin rights or developer mode
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def _unlink(link: Path) -> None:
    # os.rmdir removes a junction itself, never the folder it points to
    if IS_WIN and not link.is_symlink():
        os.rmdir(link)
    else:
        link.unlink()


def _remove_base(base: Path) -> None:
    """Delete an isolated base folder without ever following add-on links
    into the source tree."""
    if DEV_BASE not in base.resolve().parents:
        raise SystemExit(f"refusing to delete outside .anki-dev: {base}")
    addons = base / "addons21"
    if addons.exists():
        for child in addons.iterdir():
            if _is_link(child):
                _unlink(child)
        leftover = [c for c in addons.iterdir() if _is_link(c)]
        if leftover:
            raise SystemExit(f"could not remove links: {leftover}")
    shutil.rmtree(base)


# Anki's first run opens a modal language chooser (ProfileManager.setDefaultLang)
# that "-l en" does not skip. Creating prefs21.db up front with Anki's own
# ProfileManager, run headless from a matching venv, makes it a normal start.
_SEED_PREFS = r"""
import sys
import anki.lang
anki.lang.set_lang("en")
from aqt.profiles import ProfileManager
pm = ProfileManager(ProfileManager.get_created_base_folder(sys.argv[1]))
pm.setupMeta()
pm.setLang("en")
if not pm.profiles():
    pm.create("User 1")
pm.db.commit()
print(pm.profiles())
"""


def _seed_python(target: Target) -> Path:
    scripts = "Scripts" if IS_WIN else "bin"
    exe = "python.exe" if IS_WIN else "python"
    # the installer build has no standalone interpreter; use the same-version venv
    venv = "anki-25.9.5" if target.name.startswith("25.09") else "anki-26.9.3"
    return ROOT / ".venv" / venv / scripts / exe


def _seed_prefs(target: Target, base: Path) -> None:
    if (base / "prefs21.db").exists():
        return
    py = _seed_python(target)
    if not py.exists():
        raise SystemExit(f"need {py} to pre-seed the profile; create the venvs first (README)")
    res = subprocess.run([str(py), "-c", _SEED_PREFS, str(base)], capture_output=True, text=True)
    if res.returncode != 0 or not (base / "prefs21.db").exists():
        raise SystemExit(f"profile pre-seed failed:\n{res.stdout}\n{res.stderr}")


def setup(target: Target, fresh: bool, probe: bool, probes: tuple[tuple[str, Path], ...] = ()) -> Path:
    """probes: extra (link name, devtools folder) pairs to link into addons21."""
    base = DEV_BASE / target.name
    if fresh and base.exists():
        _remove_base(base)
    addons = base / "addons21"
    addons.mkdir(parents=True, exist_ok=True)
    _seed_prefs(target, base)
    _link(addons / "refine", ADDON_SRC)
    probe_link = addons / "refine_m0_probe"
    if probe:
        _link(probe_link, PROBE_SRC)
    elif _is_link(probe_link):
        _unlink(probe_link)
    for link_name, src in probes:
        _link(addons / link_name, src)
    return base


# ----------------------------------------------------------------- running


def _env(target: Target, port: int, out: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    env["QTWEBENGINE_REMOTE_DEBUGGING"] = str(port)
    # 26.x honours ANKI_SINGLE_INSTANCE_KEY; 25.09 derives its key from
    # getpass.getuser(), which reads LOGNAME first. Setting both keeps the
    # dev instance from signalling (and deferring to) an Anki already open.
    env["ANKI_SINGLE_INSTANCE_KEY"] = f"refine-dev-{target.name}"
    env["LOGNAME"] = f"refine-dev-{target.name}"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("REFINE_M0_OUT", None)
    env.pop("REFINE_M0_AUTOQUIT", None)
    env.pop("REFINE_UI_OUT", None)
    env.pop("REFINE_UI_AUTOQUIT", None)
    if out is not None:
        env["REFINE_M0_OUT"] = str(out)
        env["REFINE_M0_AUTOQUIT"] = "1"
    return env


def _cmd(target: Target, base: Path) -> list[str]:
    return [*target.command, "-b", str(base), "-l", "en"]


def run(target: Target, port: int) -> None:
    base = setup(target, fresh=False, probe=False)
    print(f"Anki {target.name}\n  base: {base}\n  devtools: http://127.0.0.1:{port}")
    subprocess.run(_cmd(target, base), env=_env(target, port, None))


def _get_json(url: str) -> object | None:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def snapshot(target: Target, port: int, timeout_s: int = 300) -> dict:
    out = OUT / target.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    base = setup(target, fresh=True, probe=True)
    log = (out / "anki-console.log").open("w", encoding="utf-8", errors="replace")
    started = time.time()
    proc = subprocess.Popen(
        _cmd(target, base),
        env=_env(target, port, out),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    cdp: dict = {"port": port}
    try:
        while proc.poll() is None and time.time() - started < timeout_s:
            if "version" not in cdp:
                v = _get_json(f"http://127.0.0.1:{port}/json/version")
                if v:
                    cdp["version"] = v
                    cdp["first_seen_after_s"] = round(time.time() - started, 1)
            if (out / "probe_done").exists() and "targets" not in cdp:
                cdp["targets"] = _get_json(f"http://127.0.0.1:{port}/json/list")
                (out / "cdp.json").write_text(json.dumps(cdp, indent=2), encoding="utf-8")
                (out / "cdp_done").write_text("1")
            time.sleep(0.5)
        if proc.poll() is None:
            cdp["killed_after_timeout"] = True
            proc.kill()
            proc.wait(timeout=30)
    finally:
        log.close()
    cdp["exit_code"] = proc.returncode
    cdp["wall_seconds"] = round(time.time() - started, 1)
    (out / "cdp.json").write_text(json.dumps(cdp, indent=2), encoding="utf-8")

    fixture = FIXTURES / target.name
    if fixture.exists():
        shutil.rmtree(fixture)
    if (out / "snapshots").exists():
        shutil.copytree(out / "snapshots", fixture)
    fixture.mkdir(parents=True, exist_ok=True)
    for name in ("probe.json", "cdp.json"):
        if (out / name).exists():
            # fixtures are committed: keep local paths out of them
            text = (out / name).read_text(encoding="utf-8")
            for path, alias in ((ROOT, "<repo>"), (Path.home(), "~")):
                for form in (str(path), str(path).replace("\\", "\\\\"), path.as_posix()):
                    text = text.replace(form, alias)
            (fixture / name).write_text(text, encoding="utf-8")
    return cdp


def shots(target: Target, keep_profile: bool, timeout_s: int = 300) -> list[Path]:
    out = UI_OUT / target.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    base = setup(target, fresh=not keep_profile, probe=False, probes=(("refine_ui_probe", UI_PROBE_SRC),))
    env = _env(target, 0, None)
    env.pop("QTWEBENGINE_REMOTE_DEBUGGING", None)
    env["REFINE_UI_OUT"] = str(out)
    env["REFINE_UI_AUTOQUIT"] = "1"
    started = time.time()
    with (out / "anki-console.log").open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(_cmd(target, base), env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            print(f"{target.name}: timed out after {timeout_s} s, killing")
            proc.kill()
            proc.wait(timeout=30)
    print(f"{target.name}: exit={proc.returncode} in {round(time.time() - started, 1)} s")
    return sorted(out.glob("*.png"))


# Anki's own "aqt[qt]" extra pins the exact PyQt/QtWebEngine of each release.
# Note: the add-on docs' "aqt[qt6]" names no such extra; pip then silently
# installs the newest PyQt6 instead of the release's pinned one.
VENVS = {"anki-25.9.5": "aqt[qt]==25.9.5", "anki-26.9.3": "aqt[qt]==26.9.3"}


def venvs(python: str) -> None:
    for name, req in VENVS.items():
        path = ROOT / ".venv" / name
        if not path.exists():
            subprocess.run([python, "-m", "venv", str(path)], check=True)
        py = path / ("Scripts/python.exe" if IS_WIN else "bin/python")
        subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", req], check=True)
        print(f"{name}: ok")


# ------------------------------------------------------------------ report

SCREENS = [
    "deck_browser",
    "deck_browser_after_review",
    "deck_browser_flipped_theme",
    "deck_browser_bottom",
    "toolbar",
    "overview",
    "overview_bottom",
    "reviewer_question",
    "reviewer_answer",
    "reviewer_bottom_question",
    "reviewer_bottom_answer",
]


def report() -> Path:
    names = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()) if FIXTURES.exists() else []
    data: dict[str, dict] = {}
    for n in names:
        p = FIXTURES / n / "probe.json"
        c = FIXTURES / n / "cdp.json"
        data[n] = {
            "probe": json.loads(p.read_text(encoding="utf-8")) if p.exists() else {},
            "cdp": json.loads(c.read_text(encoding="utf-8")) if c.exists() else {},
        }

    lines = ["# M0 automated results", "", f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `scripts/devenv.py report`.", ""]

    lines += ["## Versions and engine", "", "| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]

    def row(label: str, fn) -> None:
        vals = []
        for n in names:
            try:
                vals.append(str(fn(data[n])))
            except Exception:
                vals.append("—")
        lines.append(f"| {label} | " + " | ".join(vals) + " |")

    row("Anki", lambda d: d["probe"]["versions"]["anki"])
    row("int_version", lambda d: d["probe"]["versions"]["int_version"])
    row("Python", lambda d: d["probe"]["versions"]["python"].split()[0])
    row("Qt / PyQt", lambda d: f'{d["probe"]["versions"]["qt"]} / {d["probe"]["versions"]["pyqt"]}')
    row("QtWebEngine", lambda d: d["probe"]["versions"]["webengine"])
    row("Chromium (Qt API)", lambda d: d["probe"]["versions"]["chromium_from_qt"])
    row("Chrome (user agent)", lambda d: d["probe"]["engine"]["chrome"])
    row("Chrome (DevTools /json/version)", lambda d: d["cdp"]["version"]["Browser"])
    row("DevTools reachable after", lambda d: f'{d["cdp"]["first_seen_after_s"]} s')
    row("DevTools page targets", lambda d: ", ".join(sorted({t.get("title", "") for t in d["cdp"]["targets"] if t.get("type") == "page"})))
    for feat in ("layer_applies", "layer_loses_to_unlayered", "nesting"):
        row(f"`{feat}`", lambda d, f=feat: d["probe"]["engine"][f])
    feats = sorted(next((d["probe"].get("engine", {}).get("supports", {}) for d in data.values() if d["probe"].get("engine")), {}))
    for feat in feats:
        row(f"supports `{feat}`", lambda d, f=feat: d["probe"]["engine"]["supports"][f])
    row("web export served", lambda d: "; ".join(f"{u.split('/web/')[-1] if '/web/' in u else u.rsplit('/', 1)[-1]} → {s}" for u, s, _ in d["probe"]["web_exports"]))
    row("style_did_init calls before main_window_did_init", lambda d: sum(1 for c in d["probe"]["style_did_init_calls"] if c["before_main_window_did_init"]))
    row("style_did_init calls total", lambda d: len(d["probe"]["style_did_init_calls"]))
    row("probe errors", lambda d: len(d["probe"]["errors"]))
    row("exit code / wall time", lambda d: f'{d["cdp"]["exit_code"]} / {d["cdp"]["wall_seconds"]} s')

    lines += ["", "## Toolbar height (px)", ""]
    for n in names:
        th = data[n]["probe"].get("toolbar_height", {})
        lines.append(f"**{n}**")
        lines.append("")
        lines.append("| phase | Qt widget height | document offsetHeight | innerHeight | content hook re-ran |")
        lines.append("|---|---|---|---|---|")
        for k in sorted(th):
            v = th[k]
            hook = ", ".join(v["content_hook_contexts"]) if "content_hook_contexts" in v else ""
            lines.append(
                f"| {k} | {v.get('qt_widget_height')} | {v.get('offsetHeight')} | {v.get('innerHeight')} | {hook} |"
            )
        lines.append("")

    lines += ["## Theme toggle", ""]
    for n in names:
        tt = data[n]["probe"].get("theme_toggle")
        if not tt:
            continue
        lines.append(f"**{n}** (original theme {tt.get('original_theme')}, night mode {tt.get('start_night_mode')})")
        lines.append("")
        lines.append("| sample | night_mode | style_did_init calls (cum.) | content hook calls (cum.) | main `<html>` class | toolbar `<html>` class |")
        lines.append("|---|---|---|---|---|---|")
        for k in ("before", "after_flip", "after_restore"):
            v = tt.get(k, {})
            mc = (v.get("main_classes") or ["?"])[0]
            tc = (v.get("toolbar_classes") or ["?"])[0]
            lines.append(
                f"| {k} | {v.get('night_mode')} | {v.get('style_did_init_calls')} | {v.get('content_hook_calls')} | `{mc}` | `{tc}` |"
            )
        lines.append("")

    lines += ["## Day cutoff", ""]
    for n in names:
        lines.append(f"**{n}**")
        lines.append("```json")
        lines.append(json.dumps(data[n]["probe"].get("day_cutoff"), indent=2, ensure_ascii=False))
        lines.append("```")

    lines += ["", "## Reviewer refresh paths", ""]
    for n in names:
        lines.append(f"**{n}**")
        lines.append("")
        lines.append("| path | content-hook contexts fired | same card | state before → after | window focused |")
        lines.append("|---|---|---|---|---|")
        for k, v in data[n]["probe"].get("reviewer_refresh_paths", {}).items():
            ctx = ", ".join(v.get("content_hook_contexts", [])) or "none"
            st = f'{v["before"]["reviewer_state"]} → {v["after"]["reviewer_state"]}'
            same = v.get("same_card", v["before"]["card_id"] == v["after"]["card_id"])
            focus = v["before"].get("window_active")
            lines.append(f"| `{k}` | {ctx} | {same} | {st} | {focus} |")
        lines.append("")

    lines += ["## Class / id inventory differences", ""]
    if len(names) >= 2:
        for screen in SCREENS:
            invs = {}
            for n in names:
                f = FIXTURES / n / f"{screen}.html"
                if f.exists():
                    invs[n] = inventory_file(f)
            if len(invs) < 2:
                lines.append(f"- `{screen}`: missing in some targets ({', '.join(invs) or 'none'})")
                continue
            keys = list(invs)
            sets = {
                k: {f".{c}" for c in i.classes()} | {f"#{x}" for x in i.ids()} | {f"[{a}]" for a in i.data_attrs()}
                for k, i in invs.items()
            }
            common = set.intersection(*sets.values())
            diffs = {k: sorted(s - common) for k, s in sets.items() if s - common}
            if diffs:
                lines.append(f"- `{screen}`: " + "; ".join(f"only in {k}: {', '.join(v)}" for k, v in diffs.items()))
            else:
                lines.append(f"- `{screen}`: identical ({len(common)} classes/ids/data-attrs)")
    lines += ["", "## Probe errors", ""]
    for n in names:
        for e in data[n]["probe"].get("errors", []):
            lines.append(f"- **{n}** `{e['where']}`: {e['trace'].strip().splitlines()[-1]}")
    path = ROOT / "docs" / "M0-RESULTS.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------- cli


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("targets")
    v = sub.add_parser("venvs")
    v.add_argument("--python", default=sys.executable, help="interpreter for the venvs (3.10 to 3.13)")
    s = sub.add_parser("setup")
    s.add_argument("target", choices=TARGETS)
    s.add_argument("--fresh", action="store_true")
    s.add_argument("--probe", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("target", choices=TARGETS)
    r.add_argument("--port", type=int, default=8080)
    sn = sub.add_parser("snapshot")
    sn.add_argument("targets", nargs="*", metavar="target")
    sn.add_argument("--all", action="store_true")
    sn.add_argument("--port", type=int, default=9231)
    sh = sub.add_parser("shots")
    sh.add_argument("targets", nargs="*", metavar="target")
    sh.add_argument("--all", action="store_true")
    sh.add_argument("--keep-profile", action="store_true")
    sub.add_parser("report")
    a = ap.parse_args()

    if a.cmd == "venvs":
        venvs(a.python)
    elif a.cmd == "targets":
        for t in TARGETS.values():
            print(f"{t.name:20} {'ok' if t.available() else 'MISSING'}  {t.note}\n{'':20} {t.command[0]}")
    elif a.cmd == "setup":
        print(setup(TARGETS[a.target], a.fresh, a.probe))
    elif a.cmd == "run":
        run(TARGETS[a.target], a.port)
    elif a.cmd == "snapshot":
        chosen = list(TARGETS) if a.all else a.targets
        unknown = [n for n in chosen if n not in TARGETS]
        if unknown or not chosen:
            raise SystemExit(f"choose targets from {list(TARGETS)} or pass --all")
        for i, name in enumerate(chosen):
            t = TARGETS[name]
            if not t.available():
                print(f"{name}: skipped, not installed ({t.command[0]})")
                continue
            print(f"{name}: running probe ...", flush=True)
            res = snapshot(t, a.port + i)
            print(f"{name}: exit={res.get('exit_code')} in {res.get('wall_seconds')} s")
        print(report())
    elif a.cmd == "shots":
        chosen = list(TARGETS) if a.all else a.targets
        unknown = [n for n in chosen if n not in TARGETS]
        if unknown or not chosen:
            raise SystemExit(f"choose targets from {list(TARGETS)} or pass --all")
        for name in chosen:
            t = TARGETS[name]
            if not t.available():
                print(f"{name}: skipped, not installed ({t.command[0]})")
                continue
            print(f"{name}: capturing screenshots ...", flush=True)
            for png in shots(t, a.keep_profile):
                print(f"  {png}")
    elif a.cmd == "report":
        print(report())


if __name__ == "__main__":
    main()
