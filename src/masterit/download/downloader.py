from collections.abc import Callable, Collection
from contextlib import AbstractContextManager
from itertools import takewhile
from typing import Any, Protocol, cast

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled, YoutubeDLError

from masterit.cancellation import CancelToken
from masterit.download.events import EventHandler
from masterit.download.hooks import UrlEventReporter
from masterit.download.options import make_ydl_options
from masterit.download.settings import DownloadSettings
from masterit.download.skip_list import SkipList


class YdlSession(AbstractContextManager["YdlSession"], Protocol):
    def download(self, url_list: Collection[str]) -> int: ...


type YdlFactory = Callable[[dict[str, Any]], YdlSession]


def make_youtube_dl(options: dict[str, Any]) -> YdlSession:
    return YoutubeDL(cast(Any, options))


class YtDlpDownloader:
    def __init__(
        self, settings: DownloadSettings, ydl_factory: YdlFactory = make_youtube_dl
    ) -> None:
        self._settings = settings
        self._ydl_factory = ydl_factory

    def download(
        self,
        urls: list[str],
        on_event: EventHandler,
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None:
        try:
            for url in takewhile(lambda _: not cancel_token.is_cancelled, urls):
                reporter = UrlEventReporter(
                    url, on_event, cancel_token, skip_list, self._settings.codec
                )
                self._download_unless_skipped(url, reporter)
        except DownloadCancelled:
            return

    def _download_unless_skipped(self, url: str, reporter: UrlEventReporter) -> None:
        if reporter.start_link_unless_skipped():
            self._download_url(url, reporter)

    def _download_url(self, url: str, reporter: UrlEventReporter) -> None:
        try:
            with self._ydl_factory(make_ydl_options(self._settings, reporter)) as ydl:
                ydl.download([url])
        except DownloadCancelled:
            raise
        except YoutubeDLError as error:
            reporter.error(str(error))
        reporter.finish()
