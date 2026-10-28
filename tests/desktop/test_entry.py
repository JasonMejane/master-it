from pathlib import Path

import pytest

from masterit.desktop.entry import (
    get_data_home,
    get_icon_path,
    install_desktop_entry,
    make_desktop_entry,
    quote_exec_argument,
    uninstall_desktop_entry,
)

PYTHON = Path("/tools/masterit/bin/python")


def get_entry_path(data_home: Path) -> Path:
    return data_home / "applications" / "masterit.desktop"


def get_installed_icon_path(data_home: Path) -> Path:
    return data_home / "icons" / "hicolor" / "scalable" / "apps" / "masterit.svg"


def test_entry_launches_the_app_module_with_its_icon():
    entry = make_desktop_entry(PYTHON)
    assert entry.startswith("[Desktop Entry]\n")
    assert 'Exec="/tools/masterit/bin/python" -P -m masterit\n' in entry
    assert "Name=MasterIt\n" in entry
    assert "Icon=masterit\n" in entry
    assert "Terminal=false\n" in entry
    assert "StartupWMClass=MasterIt\n" in entry


@pytest.mark.parametrize(
    ("argument", "quoted"),
    [
        ("/a b/python", '"/a b/python"'),
        ('/a"b$c`d/python', '"/a\\\\"b\\\\$c\\\\`d/python"'),
        ("/a\\b/python", '"/a\\\\\\\\b/python"'),
        ("/100%/python", '"/100%%/python"'),
    ],
)
def test_exec_argument_is_quoted_and_escaped(argument: str, quoted: str):
    assert quote_exec_argument(argument) == quoted


@pytest.mark.parametrize(
    ("environ", "data_home"),
    [
        ({}, Path("/home/user/.local/share")),
        ({"XDG_DATA_HOME": ""}, Path("/home/user/.local/share")),
        ({"XDG_DATA_HOME": "relative"}, Path("/home/user/.local/share")),
        ({"XDG_DATA_HOME": "/data"}, Path("/data")),
    ],
)
def test_data_home_follows_xdg(environ: dict[str, str], data_home: Path):
    assert get_data_home(environ, Path("/home/user")) == data_home


def test_icon_is_a_packaged_svg():
    assert get_icon_path().read_text().startswith("<svg ")


def test_install_writes_entry_and_icon(tmp_path: Path):
    written = install_desktop_entry(tmp_path, PYTHON)
    assert written == [get_entry_path(tmp_path), get_installed_icon_path(tmp_path)]
    assert get_entry_path(tmp_path).read_text() == make_desktop_entry(PYTHON)
    assert get_installed_icon_path(tmp_path).read_bytes() == get_icon_path().read_bytes()


def test_entry_is_written_as_utf8(tmp_path: Path):
    install_desktop_entry(tmp_path, Path("/home/élise/python"))
    assert "/home/élise/python" in get_entry_path(tmp_path).read_text(encoding="utf-8")


def test_install_twice_replaces_files(tmp_path: Path):
    install_desktop_entry(tmp_path, Path("/old/python"))
    install_desktop_entry(tmp_path, PYTHON)
    assert get_entry_path(tmp_path).read_text() == make_desktop_entry(PYTHON)


def test_uninstall_removes_only_existing_files(tmp_path: Path):
    install_desktop_entry(tmp_path, PYTHON)
    get_installed_icon_path(tmp_path).unlink()
    assert uninstall_desktop_entry(tmp_path) == [get_entry_path(tmp_path)]
    assert not get_entry_path(tmp_path).exists()
    assert uninstall_desktop_entry(tmp_path) == []
