from pathlib import Path

import pytest
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage
from pytestqt.qtbot import QtBot

from masterit.gui.library_panel import LibraryPanel

from ..tags.fakes import FakeCoverStore
from .library_helpers import make_files, make_panel, open_folder, select_rows

SONG_A = Path("/music/a.mp3")
SONG_B = Path("/music/b.mp3")


def make_png(color: Qt.GlobalColor) -> bytes:
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")  # pyright: ignore[reportCallIssue, reportArgumentType]
    return bytes(buffer.data().data())


def make_cover_panel(qtbot: QtBot, store: FakeCoverStore) -> LibraryPanel:
    panel = make_panel(qtbot, cover_store=store)
    panel.add_downloaded_file(SONG_A)
    panel.add_downloaded_file(SONG_B)
    return panel


def is_showing_cover(panel: LibraryPanel) -> bool:
    return not panel.cover_view.pixmap().isNull()


def test_nothing_is_shown_without_selection(qtbot: QtBot):
    panel = make_cover_panel(qtbot, FakeCoverStore({SONG_A: make_png(Qt.GlobalColor.red)}))
    assert panel.cover_view.text() == ""
    assert not is_showing_cover(panel)


def test_cover_of_selected_file_is_shown(qtbot: QtBot):
    panel = make_cover_panel(qtbot, FakeCoverStore({SONG_A: make_png(Qt.GlobalColor.red)}))
    select_rows(panel, 0)
    assert is_showing_cover(panel)
    assert panel.cover_view.text() == ""


def test_file_without_cover_says_so(qtbot: QtBot):
    panel = make_cover_panel(qtbot, FakeCoverStore({SONG_A: make_png(Qt.GlobalColor.red)}))
    select_rows(panel, 0)
    panel.table_view.clearSelection()
    select_rows(panel, 1)
    assert panel.cover_view.text() == "No cover"
    assert not is_showing_cover(panel)


def test_shared_cover_is_shown_for_several_files(qtbot: QtBot):
    cover = make_png(Qt.GlobalColor.red)
    panel = make_cover_panel(qtbot, FakeCoverStore({SONG_A: cover, SONG_B: cover}))
    select_rows(panel, 0, 1)
    assert is_showing_cover(panel)


@pytest.mark.parametrize("second_cover", [b"other", None])
def test_differing_covers_are_reported(qtbot: QtBot, second_cover: bytes | None):
    covers = {SONG_A: make_png(Qt.GlobalColor.red)}
    if second_cover is not None:
        covers[SONG_B] = second_cover
    panel = make_cover_panel(qtbot, FakeCoverStore(covers))
    select_rows(panel, 0, 1)
    assert panel.cover_view.text() == "<multiple covers>"
    assert not is_showing_cover(panel)


def test_unreadable_image_is_reported(qtbot: QtBot):
    panel = make_cover_panel(qtbot, FakeCoverStore({SONG_A: b"not an image"}))
    select_rows(panel, 0)
    assert panel.cover_view.text() == "Unreadable cover"


def test_file_turning_unreadable_after_its_cover_was_seen_is_reported(qtbot: QtBot):
    store = FakeCoverStore({SONG_A: make_png(Qt.GlobalColor.red)})
    panel = make_cover_panel(qtbot, store)
    select_rows(panel, 0)
    store.failing.add(SONG_A)
    panel.table_view.clearSelection()
    select_rows(panel, 0)
    assert panel.cover_view.text() == "Unreadable cover"


def test_unreadable_file_has_no_cover(qtbot: QtBot):
    panel = make_cover_panel(qtbot, FakeCoverStore(failing={SONG_A}))
    select_rows(panel, 0)
    assert panel.cover_view.text() == "No cover"


def test_refreshed_files_show_their_new_cover(qtbot: QtBot):
    store = FakeCoverStore()
    panel = make_cover_panel(qtbot, store)
    select_rows(panel, 0)
    store.covers[SONG_A] = make_png(Qt.GlobalColor.red)
    panel.refresh_tags([SONG_A])
    assert is_showing_cover(panel)


def test_reopening_a_folder_reads_covers_again(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    song = make_files(tmp_path, "a.mp3")[0]
    store = FakeCoverStore()
    panel = make_panel(qtbot, cover_store=store)
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 0)
    store.covers[song] = make_png(Qt.GlobalColor.red)
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 0)
    assert is_showing_cover(panel)


def test_shared_cover_is_not_read_again_when_moving_between_its_files(qtbot: QtBot):
    cover = make_png(Qt.GlobalColor.red)
    store = FakeCoverStore({SONG_A: cover, SONG_B: cover})
    panel = make_cover_panel(qtbot, store)
    for row in (0, 1, 0):
        panel.table_view.selectRow(row)
    assert store.reads == [SONG_A, SONG_A, SONG_B]
    assert is_showing_cover(panel)


def test_cover_is_shown_again_after_a_text(qtbot: QtBot):
    panel = make_cover_panel(qtbot, FakeCoverStore({SONG_A: make_png(Qt.GlobalColor.red)}))
    select_rows(panel, 0)
    panel.table_view.clearSelection()
    select_rows(panel, 0)
    assert is_showing_cover(panel)


def test_downloaded_again_file_shows_its_new_cover(qtbot: QtBot):
    store = FakeCoverStore()
    panel = make_cover_panel(qtbot, store)
    select_rows(panel, 0)
    store.covers[SONG_A] = make_png(Qt.GlobalColor.red)
    panel.add_downloaded_file(SONG_A)
    assert is_showing_cover(panel)
    assert panel.table_model.rowCount() == 2


def test_overwritten_file_of_opened_folder_shows_its_new_cover(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    song = make_files(tmp_path, "a.mp3")[0]
    store = FakeCoverStore()
    panel = make_panel(qtbot, cover_store=store)
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 0)
    store.covers[song] = make_png(Qt.GlobalColor.red)
    panel.add_downloaded_file(song)
    assert is_showing_cover(panel)
    assert panel.table_model.rowCount() == 1


def get_shown_color(panel: LibraryPanel) -> QColor:
    return panel.cover_view.pixmap().toImage().pixelColor(0, 0)


def test_different_cover_replaces_the_shown_one(qtbot: QtBot):
    covers = {SONG_A: make_png(Qt.GlobalColor.red), SONG_B: make_png(Qt.GlobalColor.blue)}
    panel = make_cover_panel(qtbot, FakeCoverStore(covers))
    panel.table_view.selectRow(0)
    assert get_shown_color(panel) == QColor(Qt.GlobalColor.red)
    panel.table_view.selectRow(1)
    assert get_shown_color(panel) == QColor(Qt.GlobalColor.blue)
