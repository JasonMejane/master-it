import threading
from collections.abc import Callable, Collection
from pathlib import Path

from PySide6.QtCore import QSettings, QThreadPool

from masterit.cancellation import CancelToken
from masterit.download.events import (
    EventHandler,
    ItemCompleted,
    ItemFailed,
    ItemQueued,
    ItemRef,
    ItemSkipped,
)
from masterit.download.settings import DownloadSettings
from masterit.download.skip_list import SkipList
from masterit.gui.download_job import Downloader
from masterit.gui.download_panel import DownloadPanel
from masterit.gui.settings_store import SettingsStore

SONG = ItemRef("id1", "Song")
OTHER = ItemRef("id2", "Other")
SONG_FILE = Path("/music/Song.mp3")


def make_store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(QSettings(str(tmp_path / "t.conf"), QSettings.Format.IniFormat))


def make_panel(
    store: SettingsStore,
    make_downloader: Callable[[DownloadSettings], Downloader],
    ffmpeg: bool = True,
) -> DownloadPanel:
    return DownloadPanel(store, make_downloader, QThreadPool(), Path("/music/downloads"), ffmpeg)


class RecordingDownloader:
    def __init__(self) -> None:
        self.settings: DownloadSettings | None = None
        self.urls: list[str] = []

    def download(
        self,
        urls: Collection[str],
        on_event: EventHandler,
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None:
        self.urls = list(urls)
        on_event(ItemCompleted(self.urls[0], SONG, Path("/music/Song.mp3")))


class BlockingDownloader:
    def download(
        self,
        urls: Collection[str],
        on_event: EventHandler,
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None:
        for _ in range(3000):
            if cancel_token.is_cancelled:
                return
            threading.Event().wait(0.01)


class CrashingDownloader:
    def download(
        self,
        urls: Collection[str],
        on_event: EventHandler,
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None:
        raise RuntimeError("boom")


class FailingDownloader:
    def download(
        self,
        urls: Collection[str],
        on_event: EventHandler,
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None:
        on_event(ItemFailed(next(iter(urls)), None, "unavailable"))


class PlaylistDownloader:
    """Queues two entries, then skips SONG only if the user asked for it, like yt-dlp would."""

    def download(
        self,
        urls: Collection[str],
        on_event: EventHandler,
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None:
        url = next(iter(urls))
        on_event(ItemQueued(url, SONG))
        on_event(ItemQueued(url, OTHER))
        wait_until(lambda: skip_list.is_skipped(url, SONG.item_id) or cancel_token.is_cancelled)
        if cancel_token.is_cancelled:
            return
        skipped = skip_list.is_skipped(url, SONG.item_id)
        song_event = ItemSkipped(url, SONG) if skipped else ItemCompleted(url, SONG, SONG_FILE)
        on_event(song_event)
        on_event(ItemCompleted(url, OTHER, Path("/music/Other.mp3")))


def wait_until(condition: Callable[[], bool]) -> None:
    for _ in range(300):
        if condition():
            return
        threading.Event().wait(0.01)
