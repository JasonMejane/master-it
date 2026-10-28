import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QStandardPaths, Qt, QThreadPool
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QToolButton
from pytestqt.qtbot import QtBot

from masterit.gui import tag_job
from masterit.gui.library_panel import LibraryPanel
from masterit.gui.library_services import LibraryServices
from masterit.gui.main_window import (
    MainWindow,
    get_default_music_folder,
    make_app_tagger,
    make_main_window,
)
from masterit.gui.settings_store import SettingsStore
from masterit.library import move_work
from masterit.library.relocation import RelocationOutcome
from masterit.tagging.native_setup import TaggerKeys
from masterit.tagging.tagger import Tagger
from masterit.tags.fields import TagField, Tags
from masterit.tags.tag_edits import TagOutcome
from masterit.tags.tag_store import TagStore

from ..tags.fakes import FakeCoverStore, FakeTagStore
from .fakes import BlockingDownloader, make_panel, make_store
from .library_helpers import FakeRootStore, UnusedTagger, choose, confirm_always, select_rows
from .test_auto_tag_action import FakeTagger


def make_window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    settings = QSettings(str(tmp_path / "t.conf"), QSettings.Format.IniFormat)
    window = make_main_window(settings)
    qtbot.addWidget(window)
    return window


def test_default_music_folder_is_the_system_music_folder():
    location = QStandardPaths.StandardLocation.MusicLocation
    assert get_default_music_folder() == Path(QStandardPaths.writableLocation(location))


def test_downloads_and_library_default_to_the_music_folder(qtbot: QtBot, tmp_path: Path):
    window = make_window(qtbot, tmp_path)
    music = str(get_default_music_folder())
    assert window.download_panel.output_dir_input.text() == music
    assert window.library_panel.auto_tag_action.root_label.text() == f"Library: {music}"


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


def make_library(tmp_path: Path, tagger: Tagger | None = None) -> LibraryPanel:
    services = LibraryServices(
        get_download_folder=lambda: tmp_path,
        is_downloading=lambda: False,
        thread_pool=QThreadPool(),
        tag_store=FakeTagStore(),
        cover_store=FakeCoverStore(),
        root_store=FakeRootStore(),
        default_library_root=tmp_path,
        make_tagger=lambda: tagger or UnusedTagger(),
        confirm_move=confirm_always,
    )
    return LibraryPanel(services)


def make_downloading_window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    store = make_store(tmp_path)
    panel = make_panel(store, lambda settings: BlockingDownloader())
    library = make_library(tmp_path)
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

    monkeypatch.setattr(move_work, "relocate_file", relocate_slowly)
    store = make_store(tmp_path)
    library = make_library(tmp_path)
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

    monkeypatch.setattr(move_work, "relocate_file", relocate_slowly)
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


def find_nothing(name: str) -> str | None:
    return None


def test_the_app_tagger_uses_the_saved_keys(tmp_path: Path):
    store = make_store(tmp_path)
    store.save_tagger_keys(TaggerKeys("Agent"))
    built: list[TaggerKeys] = []

    def make_tagger(keys: TaggerKeys) -> Tagger:
        built.append(keys)
        return FakeTagger()

    make_app_tagger(store, make_tagger)()
    assert built == [TaggerKeys("Agent")]


def test_settings_action_saves_the_edited_keys(qtbot: QtBot, tmp_path: Path):
    store = make_store(tmp_path)
    edited: list[TaggerKeys] = []

    def edit(_parent: object, keys: TaggerKeys) -> TaggerKeys | None:
        edited.append(keys)
        return TaggerKeys("New agent") if len(edited) == 1 else None

    window = MainWindow(
        store,
        make_panel(store, lambda settings: BlockingDownloader()),
        make_library(tmp_path),
        edit,
    )
    qtbot.addWidget(window)
    window.settings_action.trigger()
    window.settings_action.trigger()
    assert edited[1] == TaggerKeys("New agent")
    assert store.load_tagger_keys() == TaggerKeys("New agent")


def make_window_counting_edits(qtbot: QtBot, tmp_path: Path, edits: list[TaggerKeys]) -> MainWindow:
    store = make_store(tmp_path)

    def edit(_parent: object, keys: TaggerKeys) -> TaggerKeys | None:
        edits.append(keys)
        return None

    window = MainWindow(
        store,
        make_panel(store, lambda settings: BlockingDownloader()),
        make_library(tmp_path),
        edit,
    )
    qtbot.addWidget(window)
    return window


def get_settings_button(window: MainWindow) -> QToolButton:
    button = window.tabs.cornerWidget(Qt.Corner.TopRightCorner)
    assert isinstance(button, QToolButton)
    return button


def test_settings_button_beside_the_tabs_opens_the_editor(qtbot: QtBot, tmp_path: Path):
    edits: list[TaggerKeys] = []
    window = make_window_counting_edits(qtbot, tmp_path, edits)
    window.show()
    QTest.mouseClick(get_settings_button(window), Qt.MouseButton.LeftButton)
    assert len(edits) == 1


def test_settings_button_is_raised_with_text_and_shortcut_hint(qtbot: QtBot, tmp_path: Path):
    window = make_window(qtbot, tmp_path)
    button = get_settings_button(window)
    shortcut = QKeySequence("Ctrl+,").toString(QKeySequence.SequenceFormat.NativeText)
    assert button.text() == "Settings"
    assert button.toolTip() == f"Settings ({shortcut})"
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert not button.autoRaise()


def test_ctrl_comma_opens_settings_from_a_child_widget(qtbot: QtBot, tmp_path: Path):
    edits: list[TaggerKeys] = []
    window = make_window_counting_edits(qtbot, tmp_path, edits)
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    links = window.download_panel.url_input
    links.setFocus()
    QTest.keyClick(links, Qt.Key.Key_Comma, Qt.KeyboardModifier.ControlModifier)
    assert len(edits) == 1


def test_closing_while_auto_tagging_cancels_then_closes(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    tagger.wait_for_cancel = True
    library = make_library(tmp_path, tagger)
    store = make_store(tmp_path)
    window = MainWindow(store, make_panel(store, lambda settings: BlockingDownloader()), library)
    qtbot.addWidget(window)
    window.show()
    library.add_downloaded_file(tmp_path / "Song.mp3")
    select_rows(library, 0)
    library.auto_tag_action.auto_tag_button.click()
    assert tagger.started.wait(2)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)


def test_second_close_stops_auto_tag_at_once(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    tagger.wait_for_cancel = True
    tagger.cancel_requests_needed = 2
    library = make_library(tmp_path, tagger)
    store = make_store(tmp_path)
    window = MainWindow(store, make_panel(store, lambda settings: BlockingDownloader()), library)
    qtbot.addWidget(window)
    window.show()
    library.add_downloaded_file(tmp_path / "Song.mp3")
    select_rows(library, 0)
    library.auto_tag_action.auto_tag_button.click()
    assert tagger.started.wait(2)
    window.close()
    qtbot.wait(50)
    assert window.isVisible()
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)
