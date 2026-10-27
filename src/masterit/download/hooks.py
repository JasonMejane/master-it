from pathlib import Path
from typing import Any

from yt_dlp.utils import DownloadCancelled

from masterit.cancellation import CancelToken
from masterit.download.events import EventHandler, ItemProgress, ItemQueued, ItemRef
from masterit.download.item_tracker import ItemOutcomeTracker
from masterit.download.settings import AudioCodec


class UrlEventReporter:
    def __init__(
        self, source_url: str, on_event: EventHandler, cancel_token: CancelToken, codec: AudioCodec
    ) -> None:
        self._source_url = source_url
        self._on_event = on_event
        self._cancel_token = cancel_token
        self._codec = codec
        self._tracker = ItemOutcomeTracker(source_url, on_event)

    def match_filter(self, info: dict[str, Any], *, incomplete: bool) -> None:
        self._raise_if_cancelled()
        if not info.get("id"):
            return
        if is_listed_entry(info):
            self._on_event(ItemQueued(self._source_url, make_item_ref(info)))
            return
        self._tracker.start_item(make_item_ref(info))

    def on_progress(self, status: dict[str, Any]) -> None:
        self._raise_if_cancelled()
        item = make_item_ref(status.get("info_dict", {}))
        self._on_event(ItemProgress(self._source_url, item, get_percent(status)))

    def on_postprocess(self, status: dict[str, Any]) -> None:
        self._raise_if_cancelled()

    def on_file_ready(self, file_path: str) -> None:
        path = Path(file_path)
        if path.suffix != f".{self._codec}":
            self._tracker.fail_item(path, f"Audio was not converted to {self._codec}: {path.name}")
            return
        self._tracker.complete_item(path)

    def finish(self) -> None:
        self._tracker.finish()

    def debug(self, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        self._tracker.record_error(message.removeprefix("ERROR: "))

    def _raise_if_cancelled(self) -> None:
        if self._cancel_token.is_cancelled:
            raise DownloadCancelled()


def is_listed_entry(info: dict[str, Any]) -> bool:
    """yt-dlp matches every playlist entry raw before downloading any; it adds playlist
    fields when processing an entry, and extractor fields once the video is resolved."""
    return "playlist_autonumber" not in info and "extractor_key" not in info


def make_item_ref(info: dict[str, Any]) -> ItemRef:
    item_id = str(info.get("id", ""))
    return ItemRef(item_id, str(info.get("title") or info.get("url") or item_id))


def get_percent(status: dict[str, Any]) -> float:
    if status["status"] == "finished":
        return 100.0
    total = status.get("total_bytes") or status.get("total_bytes_estimate")
    if not total:
        return 0.0
    return status["downloaded_bytes"] * 100 / total
