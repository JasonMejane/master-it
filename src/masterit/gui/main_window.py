import shutil
from collections.abc import Callable
from pathlib import Path
from typing import override

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QThreadPool
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import QMainWindow, QTabWidget, QToolButton, QWidget

from masterit.download.downloader import YtDlpDownloader
from masterit.gui.download_panel import DownloadPanel
from masterit.gui.library_panel import LibraryPanel
from masterit.gui.library_services import LibraryServices
from masterit.gui.settings_dialog import edit_tagger_keys
from masterit.gui.settings_store import SettingsStore
from masterit.tagging.native_setup import TaggerKeys, make_native_tagger
from masterit.tagging.tagger import Tagger
from masterit.tags.cover_store import MutagenCoverStore
from masterit.tags.tag_store import MutagenTagStore

type KeysEditor = Callable[[QWidget | None, TaggerKeys], TaggerKeys | None]


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: SettingsStore,
        download_panel: DownloadPanel,
        library_panel: LibraryPanel,
        edit_keys: KeysEditor = edit_tagger_keys,
    ) -> None:
        super().__init__()
        self._edit_keys = edit_keys
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
        self.settings_action = self._make_settings_action()
        self.tabs.setCornerWidget(self._make_settings_button(), Qt.Corner.TopRightCorner)
        self._restore_geometry()

    def _make_settings_action(self) -> QAction:
        icon = QIcon.fromTheme("configure", QIcon.fromTheme("preferences-system"))
        action = QAction(icon, "Settings", self)
        action.setShortcut(QKeySequence("Ctrl+,"))
        shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        action.setToolTip(f"Settings ({shortcut})")
        action.triggered.connect(self._edit_settings)
        self.addAction(action)
        return action

    def _make_settings_button(self) -> QToolButton:
        button = QToolButton()
        button.setDefaultAction(self.settings_action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        return button

    def _edit_settings(self) -> None:
        keys = self._edit_keys(self, self._store.load_tagger_keys())
        if keys is not None:
            self._store.save_tagger_keys(keys)

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
            # A second close abandons the file being auto-tagged instead of finishing it.
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


def get_default_music_folder() -> Path:
    location = QStandardPaths.StandardLocation.MusicLocation
    return Path(QStandardPaths.writableLocation(location))


def make_app_tagger(
    store: SettingsStore, make_tagger: Callable[[TaggerKeys], Tagger] = make_native_tagger
) -> Callable[[], Tagger]:
    return lambda: make_tagger(store.load_tagger_keys())


def make_main_window(settings: QSettings) -> MainWindow:
    store = SettingsStore(settings)
    music_folder = get_default_music_folder()
    thread_pool = QThreadPool.globalInstance()
    download_panel = DownloadPanel(
        store,
        YtDlpDownloader,
        thread_pool,
        music_folder,
        ffmpeg_available=shutil.which("ffmpeg") is not None,
    )
    services = LibraryServices(
        get_download_folder=lambda: store.load_download_settings(music_folder).output_dir,
        is_downloading=lambda: download_panel.is_running,
        thread_pool=thread_pool,
        tag_store=MutagenTagStore(),
        cover_store=MutagenCoverStore(),
        root_store=store,
        default_library_root=music_folder,
        make_tagger=make_app_tagger(store),
    )
    library_panel = LibraryPanel(services)
    return MainWindow(store, download_panel, library_panel)
