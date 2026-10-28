import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

from masterit.desktop.entry import get_data_home, install_desktop_entry, uninstall_desktop_entry

type DesktopCommand = Callable[[Path], list[Path]]

BOTH_OPTIONS = "Use only one of --install-desktop and --uninstall-desktop.\n"
TEMPORARY_ENVIRONMENT = (
    "This MasterIt runs from uv's cache, which uv may delete: install it with "
    "`uv tool install`, then run `masterit --install-desktop`.\n"
)


def get_uv_cache(environ: Mapping[str, str]) -> Path:
    if environ.get("UV_CACHE_DIR"):
        return Path(environ["UV_CACHE_DIR"])
    cache_home = environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "uv"


def install_for_this_python(data_home: Path) -> list[Path]:
    return install_desktop_entry(data_home, Path(sys.executable))


COMMANDS: dict[str, tuple[DesktopCommand, str]] = {
    "--install-desktop": (install_for_this_python, "Installed"),
    "--uninstall-desktop": (uninstall_desktop_entry, "Removed"),
}


def run_command_line(
    arguments: list[str], environ: Mapping[str, str], output: TextIO
) -> int | None:
    names = [name for name in arguments[1:] if name in COMMANDS]
    if len(names) > 1:
        output.write(BOTH_OPTIONS)
        return 2
    return run_desktop_command(names[0], environ, output) if names else None


def run_desktop_command(name: str, environ: Mapping[str, str], output: TextIO) -> int:
    in_uv_cache = Path(sys.prefix).resolve().is_relative_to(get_uv_cache(environ).resolve())
    if name == "--install-desktop" and in_uv_cache:
        output.write(TEMPORARY_ENVIRONMENT)
        return 1
    try:
        write_paths(name, get_data_home(environ, Path.home()), output)
    except OSError as error:
        output.write(f"Desktop entry failed: {error}\n")
        return 1
    return 0


def write_paths(name: str, data_home: Path, output: TextIO) -> None:
    run, verb = COMMANDS[name]
    paths = run(data_home)
    output.write("".join(f"{verb} {path}\n" for path in paths) or "Nothing to remove\n")
