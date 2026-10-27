from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from masterit.download.cancellation import CancelToken
from masterit.download.events import DownloadEvent, ItemCompleted
from masterit.download.settings import AUDIO_QUALITIES, AudioCodec, DownloadSettings
from masterit.download.url_input import parse_urls
from masterit.gui.download_job import Downloader, DownloadJob
from masterit.gui.download_rows import DownloadSummary
from masterit.gui.download_table_model import DownloadTableModel
from masterit.gui.settings_store import SettingsStore

MISSING_FFMPEG_MESSAGE = "ffmpeg was not found: install it to download audio."

type DownloaderFactory = Callable[[DownloadSettings], Downloader]


def get_start_problem(urls: list[str], output_dir_text: str) -> str:
    if not urls:
        return "Paste at least one link."
    if not output_dir_text.strip():
        return "Choose an output folder."
    return ""


def format_summary(summary: DownloadSummary) -> str:
    return (
        f"{summary.completed} completed, {summary.with_warnings} with warnings, "
        f"{summary.failed} failed."
    )


class DownloadPanel(QWidget):
    download_finished = Signal()
    file_downloaded = Signal(object)

    def __init__(
        self,
        store: SettingsStore,
        make_downloader: DownloaderFactory,
        thread_pool: QThreadPool,
        default_output_dir: Path,
        ffmpeg_available: bool,
    ) -> None:
        super().__init__()
        self._store = store
        self._make_downloader = make_downloader
        self._thread_pool = thread_pool
        self._ffmpeg_available = ffmpeg_available
        self._job: DownloadJob | None = None
        self._cancel_token = CancelToken()
        self._crash_message = ""
        self._build_widgets()
        self._build_layout()
        self._connect_signals()
        self._show_settings(store.load_download_settings(default_output_dir))
        self._set_running(False)
        self._show_ffmpeg_warning()

    def start_download(self) -> None:
        urls = parse_urls(self.url_input.toPlainText())
        problem = get_start_problem(urls, self.output_dir_input.text())
        if problem:
            self.status_label.setText(problem)
            return
        settings = self._read_settings()
        self._store.save_download_settings(settings)
        self.table_model.clear()
        self._start_job(DownloadJob(self._make_downloader(settings), urls, CancelToken()))

    def cancel_download(self) -> None:
        self._cancel_token.cancel()
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancelling after the current step…")

    @property
    def is_running(self) -> bool:
        return self._job is not None

    def stop(self) -> None:
        self.cancel_download()
        self.status_label.setText("Closing after the current step…")

    def _start_job(self, job: DownloadJob) -> None:
        self._job = job
        self._cancel_token = job.cancel_token
        self._crash_message = ""
        job.signals.event_received.connect(self.table_model.apply_event)
        job.signals.event_received.connect(self._announce_downloaded_file)
        job.signals.crashed.connect(self._remember_crash)
        job.signals.finished.connect(self._finish_download)
        self._set_running(True)
        self.status_label.setText("Downloading…")
        self._thread_pool.start(job)

    def _announce_downloaded_file(self, event: DownloadEvent) -> None:
        if isinstance(event, ItemCompleted):
            self.file_downloaded.emit(event.file_path)

    def _remember_crash(self, message: str) -> None:
        self._crash_message = message

    def _finish_download(self) -> None:
        self._job = None
        if self._cancel_token.is_cancelled:
            self.table_model.mark_unfinished_cancelled()
        self._set_running(False)
        self.status_label.setText(self._get_finish_message())
        self.download_finished.emit()

    def _get_finish_message(self) -> str:
        if self._crash_message:
            return f"Download stopped by an unexpected error: {self._crash_message}"
        prefix = "Cancelled" if self._cancel_token.is_cancelled else "Finished"
        return f"{prefix}: {format_summary(self.table_model.get_summary())}"

    def _set_running(self, running: bool) -> None:
        self.download_button.setEnabled(self._ffmpeg_available and not running)
        self.cancel_button.setEnabled(running)
        for widget in (self.url_input, self.output_dir_input, self.browse_button, self.codec_input):
            widget.setEnabled(not running)
        self._update_quality_availability()

    def _show_ffmpeg_warning(self) -> None:
        if not self._ffmpeg_available:
            self.status_label.setText(MISSING_FFMPEG_MESSAGE)

    def _show_settings(self, settings: DownloadSettings) -> None:
        self.output_dir_input.setText(str(settings.output_dir))
        self.codec_input.setCurrentIndex(self.codec_input.findData(settings.codec))
        self.quality_input.setCurrentText(settings.quality)

    def _read_settings(self) -> DownloadSettings:
        return DownloadSettings(
            output_dir=Path(self.output_dir_input.text()),
            codec=AudioCodec(self.codec_input.currentData()),
            quality=self.quality_input.currentText(),
        )

    def _update_quality_availability(self) -> None:
        is_lossy = self.codec_input.currentData() != AudioCodec.FLAC
        self.quality_input.setEnabled(is_lossy and not self.is_running)

    def _browse_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Output folder", self.output_dir_input.text()
        )
        if folder:
            self.output_dir_input.setText(folder)

    def _build_widgets(self) -> None:
        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText("Paste one or more YouTube links, one per line")
        self.url_input.setMaximumHeight(120)
        self.output_dir_input = QLineEdit()
        self.browse_button = QPushButton("Browse…")
        self.codec_input = QComboBox()
        for codec in AudioCodec:
            self.codec_input.addItem(codec.upper(), codec)
        self.quality_input = QComboBox()
        self.quality_input.addItems(AUDIO_QUALITIES)
        self.download_button = QPushButton("Download")
        self.cancel_button = QPushButton("Cancel")
        self.status_label = QLabel()
        self.table_model = DownloadTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

    def _build_layout(self) -> None:
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_input)
        output_row.addWidget(self.browse_button)
        form = QFormLayout()
        form.addRow("Links", self.url_input)
        form.addRow("Output folder", output_row)
        form.addRow("Format", self.codec_input)
        form.addRow("Quality (kbps)", self.quality_input)
        buttons = QHBoxLayout()
        buttons.addWidget(self.download_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.status_label, stretch=1)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.table_view, stretch=1)

    def _connect_signals(self) -> None:
        self.codec_input.currentIndexChanged.connect(self._update_quality_availability)
        self.browse_button.clicked.connect(self._browse_output_dir)
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.cancel_download)
