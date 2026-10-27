from pathlib import Path

from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from masterit.gui.main_window import MainWindow, make_main_window
from masterit.gui.settings_store import SettingsStore

from .fakes import BlockingDownloader, make_panel, make_store


def make_window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    settings = QSettings(str(tmp_path / "t.conf"), QSettings.Format.IniFormat)
    window = make_main_window(settings)
    qtbot.addWidget(window)
    return window


def test_main_window_is_titled_masterit(qtbot: QtBot, tmp_path: Path):
    assert make_window(qtbot, tmp_path).windowTitle() == "MasterIt"


def test_main_window_has_download_tab(qtbot: QtBot, tmp_path: Path):
    window = make_window(qtbot, tmp_path)
    tabs = window.tabs
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Download"]


def test_closing_saves_geometry_and_reopening_restores_it(qtbot: QtBot, tmp_path: Path):
    window = make_window(qtbot, tmp_path)
    window.resize(640, 480)
    window.close()
    store = SettingsStore(QSettings(str(tmp_path / "t.conf"), QSettings.Format.IniFormat))
    assert store.load_window_geometry() is not None
    assert make_window(qtbot, tmp_path).size().width() == 640


def make_downloading_window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    store = make_store(tmp_path)
    window = MainWindow(store, make_panel(store, lambda settings: BlockingDownloader()))
    qtbot.addWidget(window)
    window.show()
    window.download_panel.url_input.setPlainText("https://a")
    window.download_panel.download_button.click()
    return window


def test_closing_while_downloading_waits_for_cancel(qtbot: QtBot, tmp_path: Path):
    window = make_downloading_window(qtbot, tmp_path)
    window.close()
    assert window.isVisible()
    with qtbot.waitSignal(window.download_panel.download_finished, timeout=1000):
        pass
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=1000)


def test_second_close_while_downloading_closes_at_once(qtbot: QtBot, tmp_path: Path):
    window = make_downloading_window(qtbot, tmp_path)
    window.close()
    window.close()
    assert not window.isVisible()
    with qtbot.waitSignal(window.download_panel.download_finished, timeout=1000):
        pass
