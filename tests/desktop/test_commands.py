import io
import sys
from pathlib import Path

import pytest

from masterit.desktop import commands
from masterit.desktop.commands import run_command_line

ENTRY = Path("applications") / "masterit.desktop"
ICON = Path("icons/hicolor/scalable/apps/masterit.svg")


def run(arguments: list[str], tmp_path: Path, **environ: str) -> tuple[int | None, str]:
    output = io.StringIO()
    environ = {"XDG_DATA_HOME": str(tmp_path), "UV_CACHE_DIR": str(tmp_path / "cache"), **environ}
    code = run_command_line(["masterit", *arguments], environ, output)
    return code, output.getvalue()


def test_install_option_installs_the_entry_for_this_python(tmp_path: Path):
    code, output = run(["--install-desktop"], tmp_path)
    assert code == 0
    assert f'Exec="{sys.executable}" -P -m masterit' in (tmp_path / ENTRY).read_text()
    assert output == f"Installed {tmp_path / ENTRY}\nInstalled {tmp_path / ICON}\n"


def test_uninstall_option_removes_the_entry(tmp_path: Path):
    run(["--install-desktop"], tmp_path)
    code, output = run(["--uninstall-desktop"], tmp_path)
    assert code == 0
    assert not (tmp_path / ENTRY).exists()
    assert output == f"Removed {tmp_path / ENTRY}\nRemoved {tmp_path / ICON}\n"


def test_uninstall_without_entry_says_so(tmp_path: Path):
    assert run(["--uninstall-desktop"], tmp_path) == (0, "Nothing to remove\n")


def test_other_arguments_are_left_to_the_app(tmp_path: Path):
    assert run(["-platform", "xcb"], tmp_path) == (None, "")
    assert not (tmp_path / "applications").exists()


def test_both_options_together_are_refused(tmp_path: Path):
    code, output = run(["--install-desktop", "--uninstall-desktop"], tmp_path)
    assert (code, output) == (2, "Use only one of --install-desktop and --uninstall-desktop.\n")
    assert not (tmp_path / "applications").exists()


@pytest.mark.parametrize(
    "environ",
    [
        {"UV_CACHE_DIR": "{tmp}/uv"},
        {"UV_CACHE_DIR": "", "XDG_CACHE_HOME": "{tmp}"},
    ],
)
def test_install_from_a_temporary_uv_environment_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, environ: dict[str, str]
):
    prefix = tmp_path / "uv" / "archive-v0" / "env"
    monkeypatch.setattr(commands.sys, "prefix", str(prefix))
    filled = {name: value.format(tmp=tmp_path) for name, value in environ.items()}
    code, output = run(["--install-desktop"], tmp_path, **filled)
    assert code == 1
    assert output.startswith("This MasterIt runs from uv's cache")
    assert not (tmp_path / "applications").exists()


def test_relative_uv_cache_is_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(commands.sys, "prefix", str(tmp_path / "uv" / "archive-v0" / "env"))
    code, _ = run(["--install-desktop"], tmp_path, UV_CACHE_DIR="uv")
    assert code == 1


def test_symlinked_uv_cache_is_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    monkeypatch.setattr(commands.sys, "prefix", str(tmp_path / "real" / "uv" / "env"))
    code, _ = run(["--install-desktop"], tmp_path, UV_CACHE_DIR=str(tmp_path / "link" / "uv"))
    assert code == 1


def test_uv_cache_defaults_to_home_cache(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(commands.Path, "home", lambda: Path("/home/user"))
    assert commands.get_uv_cache({}) == Path("/home/user/.cache/uv")


def test_file_errors_are_reported_without_traceback(tmp_path: Path):
    (tmp_path / "applications").write_text("not a folder")
    code, output = run(["--install-desktop"], tmp_path)
    assert code == 1
    assert output.startswith("Desktop entry failed: ")
