# MasterIt

Desktop app (PySide6) that downloads audio from YouTube links with yt-dlp,
then lets you rename, move and tag the results into a clean library.

Work in progress — see [SPECS.md](SPECS.md) for the design and roadmap.

## Development

Requires Python 3.14+, [uv](https://docs.astral.sh/uv/) and ffmpeg.

```sh
uv sync                   # install dependencies
uv run masterit           # launch the app
uv run pytest             # tests with coverage (fails under 90%)
uv run ruff check .       # lint (incl. cyclomatic complexity ≤ 3)
uv run ruff format .      # format
uv run pyright            # type check
```
