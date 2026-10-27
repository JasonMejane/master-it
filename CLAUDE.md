# CLAUDE.md

MasterIt: PySide6 desktop app — download audio with yt-dlp, then rename, move and
tag files into a library. Design and roadmap: [SPECS.md](SPECS.md).

## Commands

- `uv sync` — install deps
- `uv run pytest` — tests + coverage (fails under 90%)
- `uv run ruff check . && uv run ruff format --check . && uv run pyright` — quality gate

All must pass before committing. yt-dlp breaks often with YouTube changes:
update it with `uv lock -P yt-dlp && uv sync`.

## Architecture rules

- `src/masterit/{download,library,tags,tagging,repack}` are the Qt-free core;
  `tests/test_architecture.py` enforces it. Only `gui/` and `__main__.py` use PySide6;
  `__main__.py` stays a thin shim, app wiring lives in tested `gui/` code.
- File operations (rename, move, tag writes) are built as plans: preview first, then apply.
- Auto-tagging goes through the `Tagger` protocol; SoundTag (`soundtag --json`) is
  invoked as a subprocess by an adapter, never reimplemented ad hoc.
- Cyclomatic complexity ≤ 3 is enforced by ruff (`C90`); a function needing 4+ must be
  split or reported.
- Tests mirror `src/masterit/` under `tests/`; external tools (yt-dlp, soundtag,
  network) are always faked in unit tests.
