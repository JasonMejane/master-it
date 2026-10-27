import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog
from pytestqt.qtbot import QtBot

from masterit.gui import move_job, tag_job
from masterit.gui.library_panel import LibraryPanel
from masterit.gui.main_window import MainWindow, make_main_window
from masterit.gui.settings_store import SettingsStore
from masterit.library.relocation import RelocationOutcome
from masterit.tags.fields import TagField, Tags
from masterit.tags.tag_edits import TagOutcome
from masterit.tags.tag_store import TagStore

from ..tags.fakes import FakeTagStore
from .fakes import BlockingDownloader, make_panel, make_store
from .library_helpers import choose, confirm_always


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
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Download", "Library"]


def test_closing_saves_geometry_and_reopening_restores_it(qtbot: QtBot, tmp_path: Path):
    window = make_window(qtbot, tmp_path)
    window.resize(640, 480)
    window.close()
    store = SettingsStore(QSettings(str(tmp_path / "t.conf"), QSettings.Format.IniFormat))
    assert store.load_window_geometry() is not None
    assert make_window(qtbot, tmp_path).size().width() == 640


def make_downloading_window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    store = make_store(tmp_path)
    panel = make_panel(store, lambda settings: BlockingDownloader())
    library = LibraryPanel(
        lambda: tmp_path, lambda: False, QThreadPool(), FakeTagStore(), confirm_always
    )
    window = MainWindow(store, panel, library)
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


def test_downloaded_files_reach_library(qtbot: QtBot, tmp_path: Path):
    window = make_window(qtbot, tmp_path)
    window.download_panel.file_downloaded.emit(Path("/music/Song.mp3"))
    assert window.library_panel.table_model.get_path(0) == Path("/music/Song.mp3")


def test_closing_while_moving_waits_for_move(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    release = threading.Event()

    def relocate_slowly(source: Path, target: Path) -> RelocationOutcome:
        release.wait(5)
        return RelocationOutcome(source, target)

    monkeypatch.setattr(move_job, "relocate_file", relocate_slowly)
    store = make_store(tmp_path)
    library = LibraryPanel(
        lambda: tmp_path, lambda: False, QThreadPool(), FakeTagStore(), confirm_always
    )
    window = MainWindow(store, make_panel(store, lambda settings: BlockingDownloader()), library)
    qtbot.addWidget(window)
    window.show()
    song = tmp_path / "Song.mp3"
    song.touch()
    library.add_downloaded_file(song)
    library.table_view.selectRow(0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "d")))
    library.move_action.move_button.click()
    try:
        window.close()
        window.close()
        qtbot.wait(100)
        assert window.isVisible()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)


def test_closing_while_downloading_and_moving_waits_for_both(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    release = threading.Event()

    def relocate_slowly(source: Path, target: Path) -> RelocationOutcome:
        release.wait(5)
        return RelocationOutcome(source, target)

    monkeypatch.setattr(move_job, "relocate_file", relocate_slowly)
    window = make_downloading_window(qtbot, tmp_path)
    library = window.library_panel
    song = tmp_path / "Song.mp3"
    song.touch()
    library.add_downloaded_file(song)
    library.table_view.selectRow(0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "d")))
    library.move_action.move_button.click()
    try:
        with qtbot.waitSignal(window.download_panel.download_finished, timeout=1000):
            window.close()
        assert window.isVisible()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)


def test_closing_while_tagging_waits_for_tag_writes(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    release = threading.Event()

    def write_slowly(path: Path, edits: Tags, store: TagStore) -> TagOutcome:
        release.wait(5)
        return TagOutcome(path)

    monkeypatch.setattr(tag_job, "write_tag_edits", write_slowly)
    window = make_window(qtbot, tmp_path)
    window.show()
    library = window.library_panel
    library.add_downloaded_file(tmp_path / "Song.mp3")
    library.table_view.selectRow(0)
    genre_input = library.tag_form.field_inputs[TagField.GENRE]
    QTest.keyClicks(genre_input, "Rock")
    library.tag_form.apply_button.click()
    try:
        window.close()
        window.close()
        qtbot.wait(100)
        assert window.isVisible()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)
