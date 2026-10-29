from typing import Protocol, override

from PySide6.QtCore import QObject, QRunnable, Signal

from masterit.cancellation import CancelToken
from masterit.download.events import EventHandler
from masterit.download.skip_list import SkipList


class Downloader(Protocol):
    def download(
        self,
        urls: list[str],
        on_event: EventHandler,
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None: ...


class DownloadSignals(QObject):
    event_received = Signal(object)
    crashed = Signal(str)
    finished = Signal()


class DownloadJob(QRunnable):
    def __init__(
        self,
        downloader: Downloader,
        urls: list[str],
        cancel_token: CancelToken,
        skip_list: SkipList,
    ) -> None:
        super().__init__()
        self.signals = DownloadSignals()
        self._downloader = downloader
        self._urls = urls
        self.cancel_token = cancel_token
        self.skip_list = skip_list

    @override
    def run(self) -> None:
        try:
            self._downloader.download(
                self._urls, self.signals.event_received.emit, self.cancel_token, self.skip_list
            )
        except Exception as error:
            self.signals.crashed.emit(str(error))
        finally:
            self.signals.finished.emit()
