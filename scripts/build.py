"""Build dist/refine-<human_version>.ankiaddon from the contents of src/refine.

Usage: py -3.11 scripts/build.py [--out dist] [--check] [--src DIR]

The archive has no top-level folder (AnkiWeb rejects that), no __pycache__,
forward-slash relative paths, sorted entries and fixed timestamps, so the same
input always yields the same bytes.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "refine"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)
EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_NAMES = {"meta.json", ".DS_Store", "Thumbs.db"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".log")


def _excluded(rel: PurePosixPath) -> bool:
    parts = rel.parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return True
    name = parts[-1]
    if name in EXCLUDED_NAMES or name.endswith(EXCLUDED_SUFFIXES):
        return True
    if parts[0] == "user_files" and rel.as_posix() != "user_files/README.txt":
        return True
    # a top-level meta.json is the user's add-on state; ignore it anywhere
    return False


def collect_files(src: Path) -> list[tuple[str, Path]]:
    out = []
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel = PurePosixPath(p.relative_to(src).as_posix())
        if not _excluded(rel):
            out.append((rel.as_posix(), p))
    out.sort(key=lambda t: t[0])
    return out


def read_manifest(src: Path) -> dict:
    return json.loads((src / "manifest.json").read_text(encoding="utf-8"))


def build(src: Path, out_dir: Path) -> Path:
    manifest = read_manifest(src)
    for key in ("package", "name", "human_version"):
        if not manifest.get(key):
            raise SystemExit(f"manifest.json is missing {key!r}")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"refine-{manifest['human_version']}.ankiaddon"
    tmp = target.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arc, path in collect_files(src):
            info = zipfile.ZipInfo(arc, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
    tmp.replace(target)
    return target


def validate(path: Path) -> tuple[list[str], int]:
    """Returns (problems, total_uncompressed_bytes). Empty problems = valid."""
    problems: list[str] = []
    total = 0
    if path.suffix != ".ankiaddon":
        problems.append("file name does not end in .ankiaddon")
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        return [f"cannot open: {e}"], 0
    with z:
        bad = z.testzip()
        if bad:
            problems.append(f"corrupt entry: {bad}")
        names = [i.filename for i in z.infolist()]
        for i in z.infolist():
            n = i.filename
            total += i.file_size
            if "\\" in n:
                problems.append(f"backslash in path: {n}")
            if n.startswith("/") or (len(n) > 1 and n[1] == ":"):
                problems.append(f"absolute path: {n}")
            if ".." in n.split("/"):
                problems.append(f"'..' in path: {n}")
            if "__pycache__" in n or n.endswith((".pyc", ".pyo")):
                problems.append(f"bytecode included: {n}")
        if len(set(names)) != len(names):
            problems.append("duplicate entries")
        for required in ("__init__.py", "manifest.json"):
            if required not in names:
                problems.append(f"{required} not at archive root")
        if "manifest.json" in names:
            try:
                m = json.loads(z.read("manifest.json"))
                if not (m.get("package") and m.get("name")):
                    problems.append("manifest.json needs package and name")
            except ValueError:
                problems.append("manifest.json is not valid JSON")
    return problems, total


def top_level(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        tops = {n.split("/", 1)[0] + ("/" if "/" in n else "") for n in z.namelist()}
    return sorted(tops)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="dist", help="output directory (default: dist)")
    ap.add_argument("--src", default=str(SRC), help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help="only validate the existing archive")
    args = ap.parse_args(argv)
    src = Path(args.src)
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if args.check:
        target = out_dir / f"refine-{read_manifest(src)['human_version']}.ankiaddon"
        if not target.is_file():
            print(f"not found: {target}", file=sys.stderr)
            return 1
    else:
        target = build(src, out_dir)
    problems, total = validate(target)
    with zipfile.ZipFile(target) as z:
        count = len(z.namelist())
    print(f"{'checked' if args.check else 'built'}: {target}")
    print(f"  entries: {count}, uncompressed: {total:,} bytes, archive: {target.stat().st_size:,} bytes")
    print("  top level: " + ", ".join(top_level(target)))
    for p in problems:
        print(f"  PROBLEM: {p}", file=sys.stderr)
    print("  OK" if not problems else "  FAILED")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
