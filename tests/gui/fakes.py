import threading
from collections.abc import Callable, Collection
from pathlib import Path

from PySide6.QtCore import QSettings, QThreadPool

from masterit.cancellation import CancelToken
from masterit.download.events import EventHandler, ItemCompleted, ItemFailed, ItemRef
from masterit.download.settings import DownloadSettings
from masterit.gui.download_job import Downloader
from masterit.gui.download_panel import DownloadPanel
from masterit.gui.settings_store import SettingsStore

SONG = ItemRef("id1", "Song")


def make_store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(QSettings(str(tmp_path / "t.conf"), QSettings.Format.IniFormat))


def make_panel(
    store: SettingsStore,
    make_downloader: Callable[[DownloadSettings], Downloader],
    ffmpeg: bool = True,
) -> DownloadPanel:
    return DownloadPanel(store, make_downloader, QThreadPool(), Path("/music/YT_DL"), ffmpeg)


class RecordingDownloader:
    def __init__(self) -> None:
        self.settings: DownloadSettings | None = None
        self.urls: list[str] = []

    def download(
        self, urls: Collection[str], on_event: EventHandler, cancel_token: CancelToken
    ) -> None:
        self.urls = list(urls)
        on_event(ItemCompleted(self.urls[0], SONG, Path("/music/Song.mp3")))


class BlockingDownloader:
    def download(
        self, urls: Collection[str], on_event: EventHandler, cancel_token: CancelToken
    ) -> None:
        for _ in range(3000):
            if cancel_token.is_cancelled:
                return
            threading.Event().wait(0.01)


class CrashingDownloader:
    def download(
        self, urls: Collection[str], on_event: EventHandler, cancel_token: CancelToken
    ) -> None:
        raise RuntimeError("boom")


class FailingDownloader:
    def download(
        self, urls: Collection[str], on_event: EventHandler, cancel_token: CancelToken
    ) -> None:
        on_event(ItemFailed(next(iter(urls)), None, "unavailable"))
