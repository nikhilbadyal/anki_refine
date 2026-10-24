# Refine (working title)

A modern, hooks-only UI refresh for Anki Desktop. See [PLAN.md](PLAN.md).
Current state: **M0 done** (dev environment and verification, no UI yet). See [docs/M0-REPORT.md](docs/M0-REPORT.md).

## Development setup (Windows; macOS/Linux use the same commands)

Requirements: Python 3.10–3.13 on PATH (`py`), Git. An installed Anki is optional.

```sh
py scripts/devenv.py venvs          # PyPI builds of Anki 25.09.5 and 26.09.3 in .venv/
py scripts/devenv.py targets        # shows which Anki builds were found
```

### Run a dev Anki

```sh
py scripts/devenv.py run 26.09.3-installed --port 8080
```

- Uses an isolated base folder `.anki-dev/<target>/`. Your normal profile is never opened, and a running Anki is left alone.
- `addons21/refine` is a junction/symlink to `src/refine`. Edit, then restart Anki.
- Webview DevTools: open `http://127.0.0.1:8080` in Chrome or Edge.
- Targets: `26.09.3-installed` (official installer), `26.09.3-pypi`, `25.09.5-pypi`.

### Snapshots and contract tests

```sh
py scripts/devenv.py snapshot --all              # drives each Anki build, captures HTML, writes docs/M0-RESULTS.md
py -m unittest discover -s tests -t .            # selector contract + unit tests (no Anki needed)
```

`snapshot` seeds a throwaway collection in `.anki-dev/<target>/`. It deletes and recreates that folder on every run. Never point it at real data. The probe refuses to run outside `.anki-dev`.

### Layout

| Path | What |
|---|---|
| `src/refine/` | The add-on (this is what gets packaged) |
| `devtools/m0_probe/` | Dev-only probe add-on; inert unless `REFINE_M0_OUT` is set; never shipped |
| `devtools/htmlinventory.py` | Stdlib HTML/selector helpers used by the report and tests |
| `scripts/devenv.py` | venvs, isolated profiles, linking, launching, snapshots, report |
| `tests/contract/fixtures/<target>/` | Captured HTML + probe/DevTools data per Anki build |

### Troubleshooting

- **Anki shows a language dialog / hangs on first start:** the profile wasn't pre-seeded. Run `py scripts/devenv.py setup <target> --fresh`.
- **Nothing happens on launch:** another dev instance of the same target is still open. Close it.
- **Rollback:** delete `.anki-dev/`. Nothing outside the repository is modified.
