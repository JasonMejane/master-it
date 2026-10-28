import os
import subprocess
import sys
from pathlib import Path

CORE_PACKAGES = ("download", "library", "tags", "tagging", "repack", "desktop")
QT_PREFIXES = ("PySide6", "shiboken6", "PyQt")

LOADED_QT_MODULES_SCRIPT = f"""
import importlib, pkgutil, sys
for name in {CORE_PACKAGES!r}:
    package = importlib.import_module("masterit." + name)
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module.name)
print(",".join(name for name in sys.modules if name.startswith({QT_PREFIXES!r})))
"""


def test_core_packages_do_not_load_qt():
    result = subprocess.run(  # noqa: S603 - trusted interpreter and script
        [sys.executable, "-c", LOADED_QT_MODULES_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == ""


DESKTOP_OPTION_SCRIPT = f"""
import sys
from masterit.__main__ import main
sys.argv = ["masterit", "--install-desktop"]
code = main()
print(code, ",".join(name for name in sys.modules if name.startswith({QT_PREFIXES!r})))
"""


def test_desktop_options_run_without_loading_qt(tmp_path: Path):
    environ = {**os.environ, "XDG_DATA_HOME": str(tmp_path), "UV_CACHE_DIR": str(tmp_path / "c")}
    result = subprocess.run(  # noqa: S603 - trusted interpreter and script
        [sys.executable, "-c", DESKTOP_OPTION_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
        env=environ,
    )
    assert result.stdout.splitlines()[-1] == "0 "
