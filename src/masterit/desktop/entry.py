import re
import shutil
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path

APP_ID = "masterit"
EXEC_RESERVED = re.compile(r'(["`$\\])')
# -P keeps the launch folder off sys.path, so files there cannot shadow modules.
ENTRY_TEMPLATE = """[Desktop Entry]
Type=Application
Name=MasterIt
Comment=Download audio, then rename, move and tag it into a library
Exec={python} -P -m masterit
Icon=masterit
Terminal=false
StartupWMClass=MasterIt
Categories=AudioVideo;Audio;
"""


# Desktop entries escape twice: once for the Exec quoting, once for the string value.
def quote_exec_argument(argument: str) -> str:
    quoted = EXEC_RESERVED.sub(r"\\\1", argument)
    return '"' + quoted.replace("\\", "\\\\").replace("%", "%%") + '"'


def make_desktop_entry(python: Path) -> str:
    return ENTRY_TEMPLATE.format(python=quote_exec_argument(str(python)))


def get_data_home(environ: Mapping[str, str], home: Path) -> Path:
    data_home = Path(environ.get("XDG_DATA_HOME", ""))
    return data_home if data_home.is_absolute() else home / ".local" / "share"


def get_icon_path() -> Path:
    return Path(str(files("masterit.desktop").joinpath("masterit.svg")))


def get_installed_paths(data_home: Path) -> list[Path]:
    icons = data_home / "icons" / "hicolor" / "scalable" / "apps"
    return [data_home / "applications" / f"{APP_ID}.desktop", icons / f"{APP_ID}.svg"]


def install_desktop_entry(data_home: Path, python: Path) -> list[Path]:
    entry, icon = get_installed_paths(data_home)
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(make_desktop_entry(python), encoding="utf-8")
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(get_icon_path(), icon)
    return [entry, icon]


def uninstall_desktop_entry(data_home: Path) -> list[Path]:
    existing = [path for path in get_installed_paths(data_home) if path.exists()]
    for path in existing:
        path.unlink()
    return existing
