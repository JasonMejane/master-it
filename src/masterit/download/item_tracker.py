from pathlib import Path

from masterit.download.events import EventHandler, ItemCompleted, ItemFailed, ItemRef

NO_FILE_MESSAGE = "No file was produced"


class ItemOutcomeTracker:
    """Decides each item's outcome, since yt-dlp also logs non-fatal problems as errors."""

    def __init__(self, source_url: str, on_event: EventHandler) -> None:
        self._source_url = source_url
        self._on_event = on_event
        self._current: ItemRef | None = None
        self._item_errors: dict[str, None] = {}
        self._orphan_errors: dict[str, None] = {}

    def start_item(self, item: ItemRef) -> None:
        if self._current is not None and self._current.item_id == item.item_id:
            self._current = item
            return
        self.finish()
        self._current = item

    def record_error(self, message: str) -> None:
        errors = self._orphan_errors if self._current is None else self._item_errors
        errors[message] = None

    def complete_item(self, file_path: Path) -> None:
        item = self._current or ItemRef("", file_path.stem)
        warnings = tuple(self._item_errors)
        self._on_event(ItemCompleted(self._source_url, item, file_path, warnings))
        self._close_current()

    def fail_item(self, file_path: Path, reason: str) -> None:
        self._report_failure(self._current or ItemRef("", file_path.stem), reason)
        self._close_current()

    def finish(self) -> None:
        self._report_orphan_errors()
        if self._current is not None:
            self._report_failure(self._current, NO_FILE_MESSAGE)
        self._close_current()

    def _report_failure(self, item: ItemRef, reason: str) -> None:
        message = "; ".join(self._item_errors) or reason
        self._on_event(ItemFailed(self._source_url, item, message))

    def _report_orphan_errors(self) -> None:
        if self._orphan_errors:
            self._on_event(ItemFailed(self._source_url, None, "; ".join(self._orphan_errors)))
            self._orphan_errors.clear()

    def _close_current(self) -> None:
        self._current = None
        self._item_errors.clear()
