from masterit.cancellation import CancelToken
from masterit.download.events import ItemFailed
from masterit.gui.download_job import Downloader, DownloadJob

from .fakes import CrashingDownloader, FailingDownloader


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
