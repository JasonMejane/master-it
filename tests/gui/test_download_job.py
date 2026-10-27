from collections.abc import Collection

from masterit.download.cancellation import CancelToken
from masterit.download.events import EventHandler, ItemFailed
from masterit.gui.download_job import Downloader, DownloadJob

from .fakes import CrashingDownloader


class FailingDownloader:
    def download(
        self, urls: Collection[str], on_event: EventHandler, cancel_token: CancelToken
    ) -> None:
        on_event(ItemFailed(next(iter(urls)), None, "unavailable"))


def run_job(downloader: Downloader) -> list[object]:
    emitted: list[object] = []
    job = DownloadJob(downloader, ["a"], CancelToken())
    job.signals.event_received.connect(emitted.append)
    job.signals.crashed.connect(emitted.append)
    job.signals.finished.connect(lambda: emitted.append("finished"))
    job.run()
    return emitted


def test_job_forwards_events_then_finishes():
    assert run_job(FailingDownloader()) == [ItemFailed("a", None, "unavailable"), "finished"]


def test_job_reports_crash_then_finishes():
    assert run_job(CrashingDownloader()) == ["boom", "finished"]
