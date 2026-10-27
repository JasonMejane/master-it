from collections.abc import Callable, Collection
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled, DownloadError

from masterit.download.cancellation import CancelToken
from masterit.download.downloader import YtDlpDownloader, make_youtube_dl
from masterit.download.events import (
    DownloadEvent,
    ItemCompleted,
    ItemFailed,
    ItemProgress,
    ItemRef,
)
from masterit.download.settings import DownloadSettings

type Scenario = Callable[["FakeYoutubeDL", str], None]

SONG = ItemRef("id1", "Song")
OTHER = ItemRef("id2", "Other")


class FakeYoutubeDL:
    """Drives the callbacks in the order the real YoutubeDL calls them."""

    def __init__(self, options: dict[str, Any], scenario: Scenario):
        self.options = options
        self._scenario = scenario

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: type[BaseException] | BaseException | TracebackType | None) -> None:
        return None

    def download(self, url_list: Collection[str]) -> int:
        for url in url_list:
            self._scenario(self, url)
        return 0

    def start_item(self, item: ItemRef, incomplete: bool = False) -> None:
        info = {"id": item.item_id, "title": item.title}
        self.options["match_filter"](info, incomplete=incomplete)

    def report_progress(self, status: dict[str, Any]) -> None:
        for hook in self.options["progress_hooks"]:
            hook(status)

    def postprocess(self) -> None:
        for hook in self.options["postprocessor_hooks"]:
            hook({"status": "started", "postprocessor": "ExtractAudio", "info_dict": {}})

    def log_error(self, message: str) -> None:
        self.options["logger"].error(message)

    def finish_file(self, file_path: str) -> None:
        for hook in self.options["post_hooks"]:
            hook(file_path)


def run_download(
    scenario: Scenario, urls: list[str], token: CancelToken | None = None
) -> list[DownloadEvent]:
    events: list[DownloadEvent] = []
    downloader = YtDlpDownloader(
        DownloadSettings(Path("/music")), lambda options: FakeYoutubeDL(options, scenario)
    )
    downloader.download(urls, events.append, token or CancelToken())
    return events


def downloading(downloaded: int, total: int | None) -> dict[str, Any]:
    return {
        "status": "downloading",
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "info_dict": {"id": SONG.item_id, "title": SONG.title},
    }


def run_progress(status: dict[str, Any]) -> list[DownloadEvent]:
    return run_download(lambda ydl, url: ydl.report_progress(status), ["a"])


def test_completed_item_is_reported_with_its_file():
    def complete(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG)
        ydl.finish_file("/music/Song.mp3")

    assert run_download(complete, ["a"]) == [ItemCompleted("a", SONG, Path("/music/Song.mp3"))]


def test_repeated_match_of_same_item_keeps_latest_title():
    def complete(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(ItemRef("id1", "Song (Official Video)"))
        ydl.start_item(SONG)
        ydl.finish_file("/music/Song.mp3")

    assert run_download(complete, ["a"]) == [ItemCompleted("a", SONG, Path("/music/Song.mp3"))]


def test_playlist_reports_each_item():
    def complete_playlist(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG, incomplete=True)
        ydl.start_item(SONG)
        ydl.finish_file("/music/list/Song.mp3")
        ydl.start_item(OTHER, incomplete=True)
        ydl.start_item(OTHER)
        ydl.finish_file("/music/list/Other.mp3")

    events = run_download(complete_playlist, ["list"])
    assert [(event.source_url, event.item) for event in events] == [("list", SONG), ("list", OTHER)]


def test_file_without_matched_item_is_named_after_file():
    events = run_download(lambda ydl, url: ydl.finish_file("/music/Song.mp3"), ["a"])
    assert events == [ItemCompleted("a", ItemRef("", "Song"), Path("/music/Song.mp3"))]


def test_progress_is_reported_as_percent():
    assert run_progress(downloading(25, 100)) == [ItemProgress("a", SONG, 25.0)]


def test_progress_falls_back_to_estimated_total():
    status = {**downloading(50, None), "total_bytes_estimate": 200}
    assert run_progress(status) == [ItemProgress("a", SONG, 25.0)]


def test_progress_without_total_is_zero_percent():
    assert run_progress(downloading(50, None)) == [ItemProgress("a", SONG, 0.0)]


def test_finished_status_is_full_progress():
    status = {"status": "finished", "info_dict": {"id": "id1", "title": "Song"}}
    assert run_progress(status) == [ItemProgress("a", SONG, 100.0)]


def test_errors_before_file_become_completion_warnings():
    def embed_failure(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG)
        ydl.log_error("ERROR: Postprocessing: thumbnail embed failed")
        ydl.log_error("ERROR: Postprocessing: thumbnail embed failed")
        ydl.finish_file("/music/Song.mp3")

    assert run_download(embed_failure, ["a"]) == [
        ItemCompleted(
            "a", SONG, Path("/music/Song.mp3"), ("Postprocessing: thumbnail embed failed",)
        )
    ]


def test_file_not_converted_to_codec_fails_with_its_errors():
    def extraction_failure(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG)
        ydl.log_error("ERROR: Postprocessing: ffprobe and ffmpeg not found")
        ydl.finish_file("/music/Song.webm")

    assert run_download(extraction_failure, ["a"]) == [
        ItemFailed("a", SONG, "Postprocessing: ffprobe and ffmpeg not found")
    ]


def test_file_not_converted_to_codec_fails_without_logged_error():
    def silent_failure(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG)
        ydl.finish_file("/music/Song.webm")

    assert run_download(silent_failure, ["a"]) == [
        ItemFailed("a", SONG, "Audio was not converted to mp3: Song.webm")
    ]


def test_item_ending_without_file_fails_once_with_its_errors():
    def fail(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG)
        ydl.log_error("ERROR: first")
        ydl.log_error("ERROR: first")
        ydl.log_error("ERROR: second")

    assert run_download(fail, ["a"]) == [ItemFailed("a", SONG, "first; second")]


def test_item_ending_silently_without_file_fails():
    events = run_download(lambda ydl, url: ydl.start_item(SONG), ["a"])
    assert events == [ItemFailed("a", SONG, "No file was produced")]


def test_failed_item_is_reported_before_next_item():
    def fail_then_complete(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG)
        ydl.start_item(OTHER)
        ydl.finish_file("/music/Other.mp3")

    events = run_download(fail_then_complete, ["list"])
    assert events == [
        ItemFailed("list", SONG, "No file was produced"),
        ItemCompleted("list", OTHER, Path("/music/Other.mp3")),
    ]


def test_error_before_any_item_fails_the_url():
    events = run_download(lambda ydl, url: ydl.log_error("ERROR: Unsupported URL"), ["a"])
    assert events == [ItemFailed("a", None, "Unsupported URL")]


def test_error_between_items_is_reported_before_next_item():
    def unavailable_entry(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG)
        ydl.finish_file("/music/Song.mp3")
        ydl.log_error("ERROR: [youtube] xyz: Video unavailable")
        ydl.start_item(OTHER)
        ydl.finish_file("/music/Other.mp3")

    events = run_download(unavailable_entry, ["list"])
    assert events == [
        ItemCompleted("list", SONG, Path("/music/Song.mp3")),
        ItemFailed("list", None, "[youtube] xyz: Video unavailable"),
        ItemCompleted("list", OTHER, Path("/music/Other.mp3")),
    ]


def test_unavailable_playlist_entry_fails_on_its_own():
    def unavailable_entry(ydl: FakeYoutubeDL, url: str) -> None:
        ydl.start_item(SONG, incomplete=True)
        ydl.log_error("ERROR: [youtube] id1: Video unavailable")
        ydl.start_item(OTHER, incomplete=True)
        ydl.start_item(OTHER)
        ydl.finish_file("/music/Other.mp3")

    assert run_download(unavailable_entry, ["list"]) == [
        ItemFailed("list", SONG, "[youtube] id1: Video unavailable"),
        ItemCompleted("list", OTHER, Path("/music/Other.mp3")),
    ]


def test_non_error_logs_are_ignored():
    def chatter(ydl: FakeYoutubeDL, url: str) -> None:
        logger = ydl.options["logger"]
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")

    assert run_download(chatter, ["a"]) == []


def test_raised_error_fails_only_its_url():
    def fail_first(ydl: FakeYoutubeDL, url: str) -> None:
        if url == "a":
            raise DownloadError("boom")
        ydl.start_item(SONG)
        ydl.finish_file("/music/Song.mp3")

    events = run_download(fail_first, ["a", "b"])
    assert events == [
        ItemFailed("a", None, "boom"),
        ItemCompleted("b", SONG, Path("/music/Song.mp3")),
    ]


def run_cancelled(step: Callable[[FakeYoutubeDL], None]) -> tuple[list[str], list[DownloadEvent]]:
    token = CancelToken()
    started: list[str] = []

    def cancel_then_step(ydl: FakeYoutubeDL, url: str) -> None:
        started.append(url)
        ydl.start_item(SONG)
        token.cancel()
        step(ydl)

    return started, run_download(cancel_then_step, ["a", "b"], token)


def test_cancel_during_progress_stops_without_failure():
    assert run_cancelled(lambda ydl: ydl.report_progress(downloading(1, 2))) == (["a"], [])


def test_cancel_before_next_item_stops_without_failure():
    assert run_cancelled(lambda ydl: ydl.start_item(OTHER, incomplete=True)) == (["a"], [])


def test_cancel_between_postprocessors_stops_without_failure():
    assert run_cancelled(lambda ydl: ydl.postprocess()) == (["a"], [])


def test_postprocessing_without_cancel_reports_nothing():
    assert run_download(lambda ydl, url: ydl.postprocess(), ["a"]) == []


def test_cancelled_downloader_does_not_start():
    token = CancelToken()
    token.cancel()
    started: list[str] = []
    run_download(lambda ydl, url: started.append(url), ["a"], token)
    assert started == []


def test_cancel_raised_by_yt_dlp_stops_remaining_urls():
    started: list[str] = []

    def cancel(ydl: FakeYoutubeDL, url: str) -> None:
        started.append(url)
        raise DownloadCancelled()

    run_download(cancel, ["a", "b"])
    assert started == ["a"]


def test_default_factory_builds_real_youtube_dl_with_options():
    with make_youtube_dl({"format": "bestaudio/best"}) as ydl:
        assert isinstance(ydl, YoutubeDL)
        assert ydl.params.get("format") == "bestaudio/best"
