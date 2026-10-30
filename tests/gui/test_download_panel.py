from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QStyle, QStyleOptionViewItem
from pytestqt.qtbot import QtBot

from masterit.download.events import ItemProgress
from masterit.download.settings import AudioCodec, DownloadSettings
from masterit.gui.download_job import Downloader
from masterit.gui.download_panel import DownloadPanel

from .fakes import (
    SONG,
    BlockingDownloader,
    CrashingDownloader,
    FailingDownloader,
    PlaylistDownloader,
    RecordingDownloader,
    make_panel,
    make_store,
)


class PanelFixture:
    def __init__(self, qtbot: QtBot, tmp_path: Path, downloader: Downloader, ffmpeg: bool = True):
        self.store = make_store(tmp_path)
        self.downloader = downloader
        self.panel = make_panel(self.store, self.make_downloader, ffmpeg)
        qtbot.addWidget(self.panel)

    def make_downloader(self, settings: DownloadSettings) -> Downloader:
        if isinstance(self.downloader, RecordingDownloader):
            self.downloader.settings = settings
        return self.downloader


def make_folder_chooser(folder: str) -> Callable[..., str]:
    def choose_folder(*args: object) -> str:
        return folder

    return choose_folder


def get_status(panel: DownloadPanel, row: int) -> object:
    return panel.table_model.data(panel.table_model.index(row, 2))


def start_download(qtbot: QtBot, panel: DownloadPanel, text: str = "https://a") -> None:
    panel.url_input.setPlainText(text)
    with qtbot.waitSignal(panel.download_finished, timeout=5000):
        panel.download_button.click()


def test_form_shows_default_settings(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    assert panel.output_dir_input.text() == "/music/downloads"
    assert panel.codec_input.currentData() == AudioCodec.MP3
    assert panel.quality_input.currentText() == "192"
    assert not panel.cancel_button.isEnabled()


def test_flac_disables_quality(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    panel.codec_input.setCurrentIndex(panel.codec_input.findData(AudioCodec.FLAC))
    assert not panel.quality_input.isEnabled()
    panel.codec_input.setCurrentIndex(panel.codec_input.findData(AudioCodec.OPUS))
    assert panel.quality_input.isEnabled()


def test_download_without_links_asks_for_them(qtbot: QtBot, tmp_path: Path):
    fixture = PanelFixture(qtbot, tmp_path, RecordingDownloader())
    fixture.panel.download_button.click()
    assert fixture.panel.status_label.text() == "Paste at least one link."
    assert isinstance(fixture.downloader, RecordingDownloader)
    assert fixture.downloader.urls == []


def test_download_uses_form_settings_and_shows_results(qtbot: QtBot, tmp_path: Path):
    fixture = PanelFixture(qtbot, tmp_path, RecordingDownloader())
    panel = fixture.panel
    panel.codec_input.setCurrentIndex(panel.codec_input.findData(AudioCodec.OPUS))
    panel.quality_input.setCurrentText("320")
    start_download(qtbot, panel, "https://a\nhttps://b https://a")
    downloader = fixture.downloader
    assert isinstance(downloader, RecordingDownloader)
    assert downloader.urls == ["https://a", "https://b"]
    assert downloader.settings == DownloadSettings(Path("/music/downloads"), AudioCodec.OPUS, "320")
    assert panel.table_model.rowCount() == 2
    assert panel.status_label.text() == "Finished: 1 completed, 0 with warnings, 1 failed."
    assert get_status(panel, 1) == "Failed"
    assert panel.download_button.isEnabled()


def test_download_saves_settings(qtbot: QtBot, tmp_path: Path):
    fixture = PanelFixture(qtbot, tmp_path, RecordingDownloader())
    fixture.panel.output_dir_input.setText("/elsewhere")
    start_download(qtbot, fixture.panel)
    assert fixture.store.load_download_settings(Path("/x")).output_dir == Path("/elsewhere")


def test_new_download_clears_previous_rows(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    start_download(qtbot, panel)
    start_download(qtbot, panel)
    assert panel.table_model.rowCount() == 1


def start_blocking_download(qtbot: QtBot, tmp_path: Path) -> DownloadPanel:
    panel = PanelFixture(qtbot, tmp_path, BlockingDownloader()).panel
    panel.url_input.setPlainText("https://a")
    panel.download_button.click()
    return panel


def test_inputs_are_locked_while_downloading(qtbot: QtBot, tmp_path: Path):
    panel = start_blocking_download(qtbot, tmp_path)
    inputs = (panel.url_input, panel.output_dir_input, panel.browse_button, panel.codec_input)
    assert not any(widget.isEnabled() for widget in (*inputs, panel.quality_input))
    with qtbot.waitSignal(panel.download_finished, timeout=1000):
        panel.cancel_button.click()
    assert all(widget.isEnabled() for widget in (*inputs, panel.quality_input))


def test_flac_keeps_quality_disabled_after_download(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    panel.codec_input.setCurrentIndex(panel.codec_input.findData(AudioCodec.FLAC))
    start_download(qtbot, panel)
    assert not panel.quality_input.isEnabled()


def test_cancel_stops_running_download(qtbot: QtBot, tmp_path: Path):
    panel = start_blocking_download(qtbot, tmp_path)
    assert not panel.download_button.isEnabled()
    with qtbot.waitSignal(panel.download_finished, timeout=1000):
        panel.cancel_button.click()
    assert panel.status_label.text().startswith("Cancelled:")
    assert not panel.cancel_button.isEnabled()


def test_cancel_marks_unfinished_rows_cancelled(qtbot: QtBot, tmp_path: Path):
    panel = start_blocking_download(qtbot, tmp_path)
    panel.table_model.apply_event(ItemProgress("https://a", SONG, 10.0))
    with qtbot.waitSignal(panel.download_finished, timeout=1000):
        panel.cancel_button.click()
    assert panel.table_model.data(panel.table_model.index(0, 2)) == "Cancelled"


def test_pasted_links_are_pending_until_they_start(qtbot: QtBot, tmp_path: Path):
    panel = start_blocking_download(qtbot, tmp_path)
    assert panel.table_model.rowCount() == 1
    assert get_status(panel, 0) == "Pending"
    with qtbot.waitSignal(panel.download_finished, timeout=1000):
        panel.cancel_button.click()
    assert get_status(panel, 0) == "Cancelled"


def test_new_download_after_cancel_finishes_normally(qtbot: QtBot, tmp_path: Path):
    fixture = PanelFixture(qtbot, tmp_path, BlockingDownloader())
    fixture.panel.url_input.setPlainText("https://a")
    fixture.panel.download_button.click()
    with qtbot.waitSignal(fixture.panel.download_finished, timeout=1000):
        fixture.panel.cancel_button.click()
    fixture.downloader = RecordingDownloader()
    start_download(qtbot, fixture.panel)
    assert fixture.panel.status_label.text().startswith("Finished:")


def test_download_without_output_folder_asks_for_it(qtbot: QtBot, tmp_path: Path):
    fixture = PanelFixture(qtbot, tmp_path, RecordingDownloader())
    fixture.panel.url_input.setPlainText("https://a")
    fixture.panel.output_dir_input.setText("  ")
    fixture.panel.download_button.click()
    assert fixture.panel.status_label.text() == "Choose an output folder."
    assert isinstance(fixture.downloader, RecordingDownloader)
    assert fixture.downloader.urls == []


def test_crash_is_shown(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, CrashingDownloader()).panel
    start_download(qtbot, panel)
    assert panel.status_label.text() == "Download stopped by an unexpected error: boom"


def test_missing_ffmpeg_disables_download(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader(), ffmpeg=False).panel
    assert not panel.download_button.isEnabled()
    assert "ffmpeg" in panel.status_label.text()


def test_browse_sets_chosen_folder(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", make_folder_chooser("/chosen"))
    panel.browse_button.click()
    assert panel.output_dir_input.text() == "/chosen"


def test_browse_cancelled_keeps_folder(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", make_folder_chooser(""))
    panel.browse_button.click()
    assert panel.output_dir_input.text() == "/music/downloads"


def test_stop_cancels_running_download_before_closing(qtbot: QtBot, tmp_path: Path):
    panel = start_blocking_download(qtbot, tmp_path)
    assert panel.is_running
    panel.stop()
    assert panel.status_label.text() == "Closing after the current step…"
    with qtbot.waitSignal(panel.download_finished, timeout=1000):
        pass
    assert not panel.is_running


def test_completed_downloads_are_announced(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    panel.url_input.setPlainText("https://a")
    downloaded: list[Path] = []
    panel.file_downloaded.connect(downloaded.append)
    with qtbot.waitSignal(panel.download_finished, timeout=5000):
        panel.download_button.click()
    assert downloaded == [Path("/music/Song.mp3")]


def test_failed_downloads_are_not_announced(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, FailingDownloader()).panel
    downloaded: list[Path] = []
    panel.file_downloaded.connect(downloaded.append)
    start_download(qtbot, panel)
    assert downloaded == []


def start_playlist_download(qtbot: QtBot, tmp_path: Path) -> DownloadPanel:
    panel = PanelFixture(qtbot, tmp_path, PlaylistDownloader()).panel
    panel.url_input.setPlainText("https://a")
    panel.download_button.click()
    qtbot.waitUntil(lambda: panel.table_model.rowCount() == 2)
    return panel


def set_check(panel: DownloadPanel, row: int, state: Qt.CheckState) -> bool:
    model = panel.table_model
    return model.setData(model.index(row, 0), state.value, Qt.ItemDataRole.CheckStateRole)


def test_rows_are_not_checkable_without_running_download(qtbot: QtBot, tmp_path: Path):
    panel = PanelFixture(qtbot, tmp_path, RecordingDownloader()).panel
    panel.table_model.add_links(["https://a"])
    assert not set_check(panel, 0, Qt.CheckState.Unchecked)


def test_unchecked_row_is_not_downloaded_and_counted(qtbot: QtBot, tmp_path: Path):
    panel = start_playlist_download(qtbot, tmp_path)
    with qtbot.waitSignal(panel.download_finished, timeout=5000):
        set_check(panel, 0, Qt.CheckState.Unchecked)
    assert [get_status(panel, row) for row in range(2)] == ["Skipped", "Done"]
    assert panel.status_label.text() == (
        "Finished: 1 completed, 0 with warnings, 0 failed, 1 skipped."
    )
    assert not set_check(panel, 1, Qt.CheckState.Unchecked)


def test_checking_again_puts_row_back_to_pending(qtbot: QtBot, tmp_path: Path):
    panel = start_playlist_download(qtbot, tmp_path)
    set_check(panel, 1, Qt.CheckState.Unchecked)
    assert get_status(panel, 1) == "Will skip"
    set_check(panel, 1, Qt.CheckState.Checked)
    assert get_status(panel, 1) == "Pending"
    with qtbot.waitSignal(panel.download_finished, timeout=5000):
        panel.cancel_button.click()


def select_rows(panel: DownloadPanel, rows: list[int]) -> None:
    selection = panel.table_view.selectionModel()
    for row in rows:
        index = panel.table_model.index(row, 0)
        selection.select(index, selection.SelectionFlag.Select | selection.SelectionFlag.Rows)


def test_checking_a_selected_row_applies_to_whole_selection(qtbot: QtBot, tmp_path: Path):
    panel = start_playlist_download(qtbot, tmp_path)
    select_rows(panel, [0, 1])
    set_check(panel, 1, Qt.CheckState.Unchecked)
    assert [get_status(panel, row) for row in range(2)] == ["Will skip", "Will skip"]
    with qtbot.waitSignal(panel.download_finished, timeout=5000):
        panel.cancel_button.click()


def test_checking_an_unselected_row_leaves_selection_alone(qtbot: QtBot, tmp_path: Path):
    panel = start_playlist_download(qtbot, tmp_path)
    select_rows(panel, [0])
    set_check(panel, 1, Qt.CheckState.Unchecked)
    assert [get_status(panel, row) for row in range(2)] == ["Pending", "Will skip"]
    with qtbot.waitSignal(panel.download_finished, timeout=5000):
        panel.cancel_button.click()


def get_checkbox_center(panel: DownloadPanel, row: int) -> QPoint:
    option = QStyleOptionViewItem()
    option.rect = panel.table_view.visualRect(panel.table_model.index(row, 0))
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    indicator = QStyle.SubElement.SE_ItemViewItemCheckIndicator
    return panel.table_view.style().subElementRect(indicator, option, panel.table_view).center()


def get_selected_rows(panel: DownloadPanel) -> list[int]:
    return sorted(index.row() for index in panel.table_view.selectionModel().selectedRows())


def test_clicking_a_selected_checkbox_keeps_the_selection(qtbot: QtBot, tmp_path: Path):
    panel = start_playlist_download(qtbot, tmp_path)
    panel.show()
    qtbot.waitExposed(panel)
    select_rows(panel, [0, 1])
    viewport = panel.table_view.viewport()
    with qtbot.waitSignal(panel.download_finished, timeout=5000):
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=get_checkbox_center(panel, 1))
        assert [get_status(panel, row) for row in range(2)] == ["Will skip", "Will skip"]
    assert get_selected_rows(panel) == [0, 1]
