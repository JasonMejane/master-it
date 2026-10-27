import shutil
from pathlib import Path
from typing import override

from PySide6.QtCore import QSettings, QStandardPaths, QThreadPool
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from masterit.download.downloader import YtDlpDownloader
from masterit.gui.download_panel import DownloadPanel
from masterit.gui.library_panel import LibraryPanel
from masterit.gui.library_services import LibraryServices
from masterit.gui.settings_store import SettingsStore
from masterit.tagging.soundtag_cli import SoundTagCliTagger
from masterit.tagging.subprocess_process import start_subprocess
from masterit.tagging.tagger import Tagger
from masterit.tags.cover_store import MutagenCoverStore
from masterit.tags.tag_store import MutagenTagStore


class MainWindow(QMainWindow):
    def __init__(
        self, store: SettingsStore, download_panel: DownloadPanel, library_panel: LibraryPanel
    ) -> None:
        super().__init__()
        self.setWindowTitle("MasterIt")
        self._store = store
        self.download_panel = download_panel
        self.library_panel = library_panel
        self._is_closing = False
        self.tabs = QTabWidget()
        self.tabs.addTab(download_panel, "Download")
        self.tabs.addTab(library_panel, "Library")
        download_panel.file_downloaded.connect(library_panel.add_downloaded_file)
        self.setCentralWidget(self.tabs)
        self._restore_geometry()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._must_defer_close():
            self._close_when_idle(event)
            return
        self._store.save_window_geometry(self.saveGeometry())
        super().closeEvent(event)

    def _must_defer_close(self) -> bool:
        # A second close may abandon a download, never a move or tag write (partial file risk).
        is_download_pending = self.download_panel.is_running and not self._is_closing
        return self.library_panel.is_busy or is_download_pending

    def _close_when_idle(self, event: QCloseEvent) -> None:
        event.ignore()
        if self._is_closing:
            # A second close stops SoundTag at once instead of after its current file.
            self.library_panel.stop_work()
            return
        self._is_closing = True
        self.download_panel.download_finished.connect(self._close_if_idle)
        self.library_panel.work_finished.connect(self._close_if_idle)
        self._stop_download()
        self.library_panel.stop_work()

    def _stop_download(self) -> None:
        if self.download_panel.is_running:
            self.download_panel.stop()

    def _close_if_idle(self) -> None:
        if not (self.download_panel.is_running or self.library_panel.is_busy):
            self.close()

    def _restore_geometry(self) -> None:
        geometry = self._store.load_window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)


def get_default_output_dir() -> Path:
    location = QStandardPaths.StandardLocation.MusicLocation
    return Path(QStandardPaths.writableLocation(location)) / "YT_DL"


def make_soundtag_tagger() -> Tagger | None:
    executable = shutil.which("soundtag")
    return None if executable is None else SoundTagCliTagger(start_subprocess, Path(executable))


def make_main_window(settings: QSettings) -> MainWindow:
    store = SettingsStore(settings)
    default_output_dir = get_default_output_dir()
    thread_pool = QThreadPool.globalInstance()
    download_panel = DownloadPanel(
        store,
        YtDlpDownloader,
        thread_pool,
        default_output_dir,
        ffmpeg_available=shutil.which("ffmpeg") is not None,
    )
    services = LibraryServices(
        get_download_folder=lambda: store.load_download_settings(default_output_dir).output_dir,
        is_downloading=lambda: download_panel.is_running,
        thread_pool=thread_pool,
        tag_store=MutagenTagStore(),
        cover_store=MutagenCoverStore(),
        root_store=store,
        tagger=make_soundtag_tagger(),
    )
    library_panel = LibraryPanel(services)
    return MainWindow(store, download_panel, library_panel)
