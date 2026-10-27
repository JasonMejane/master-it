import shutil
from pathlib import Path
from typing import override

from PySide6.QtCore import QSettings, QStandardPaths, QThreadPool
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from masterit.download.downloader import YtDlpDownloader
from masterit.gui.download_panel import DownloadPanel
from masterit.gui.settings_store import SettingsStore


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore, download_panel: DownloadPanel) -> None:
        super().__init__()
        self.setWindowTitle("MasterIt")
        self._store = store
        self.download_panel = download_panel
        self._is_closing = False
        self.tabs = QTabWidget()
        self.tabs.addTab(download_panel, "Download")
        self.setCentralWidget(self.tabs)
        self._restore_geometry()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self.download_panel.is_running and not self._is_closing:
            self._close_after_download(event)
            return
        self._store.save_window_geometry(self.saveGeometry())
        super().closeEvent(event)

    def _close_after_download(self, event: QCloseEvent) -> None:
        self._is_closing = True
        event.ignore()
        self.download_panel.download_finished.connect(self.close)
        self.download_panel.stop()

    def _restore_geometry(self) -> None:
        geometry = self._store.load_window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)


def get_default_output_dir() -> Path:
    location = QStandardPaths.StandardLocation.MusicLocation
    return Path(QStandardPaths.writableLocation(location)) / "YT_DL"


def make_main_window(settings: QSettings) -> MainWindow:
    store = SettingsStore(settings)
    panel = DownloadPanel(
        store,
        YtDlpDownloader,
        QThreadPool.globalInstance(),
        get_default_output_dir(),
        ffmpeg_available=shutil.which("ffmpeg") is not None,
    )
    return MainWindow(store, panel)
