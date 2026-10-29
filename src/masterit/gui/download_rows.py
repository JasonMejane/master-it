from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import Enum, auto
from functools import singledispatchmethod

from masterit.download.events import (
    DownloadEvent,
    ItemCompleted,
    ItemFailed,
    ItemProgress,
    ItemQueued,
    ItemSkipped,
    LinkStarted,
)
from masterit.download.skip_list import SkipList

NOT_DOWNLOADED_MESSAGE = "Not downloaded"


class RowStatus(Enum):
    PENDING = auto()
    STARTED = auto()
    DOWNLOADING = auto()
    COMPLETED = auto()
    WARNING = auto()
    FAILED = auto()
    CANCELLED = auto()
    SKIP_REQUESTED = auto()
    SKIPPED = auto()


SKIP_TOGGLES = {
    RowStatus.PENDING: RowStatus.SKIP_REQUESTED,
    RowStatus.SKIP_REQUESTED: RowStatus.PENDING,
}
REPLACEABLE_LINK_STATUSES = (*SKIP_TOGGLES, RowStatus.STARTED)


@dataclass(frozen=True)
class DownloadRow:
    title: str
    status: RowStatus
    percent: float
    details: str


@dataclass(frozen=True)
class DownloadSummary:
    completed: int
    with_warnings: int
    failed: int
    skipped: int = 0


@dataclass(frozen=True)
class Placement:
    index: int
    is_new: bool


@dataclass(frozen=True)
class RowSlot:
    """Where a row comes from; no item id marks a pasted link or a failure without item."""

    source_url: str
    item_id: str | None


def get_slot(event: DownloadEvent) -> RowSlot:
    return RowSlot(event.source_url, None if event.item is None else event.item.item_id)


class DownloadRows:
    def __init__(self) -> None:
        self._rows: list[DownloadRow] = []
        self._slots: list[RowSlot] = []

    @property
    def count(self) -> int:
        return len(self._rows)

    def get_row(self, index: int) -> DownloadRow:
        return self._rows[index]

    def add_links(self, urls: Iterable[str]) -> None:
        for url in urls:
            self._rows.append(DownloadRow(url, RowStatus.PENDING, 0.0, ""))
            self._slots.append(RowSlot(url, None))

    def find_placement(self, event: DownloadEvent) -> Placement:
        index = self._find_item_row(get_slot(event))
        if index is None:
            index = self._find_link_row(event.source_url)
        if index is None:
            return Placement(self._get_insert_index(event.source_url), is_new=True)
        return Placement(index, is_new=False)

    def apply(self, event: DownloadEvent) -> int:
        return self.apply_at(event, self.find_placement(event))

    def apply_at(self, event: DownloadEvent, placement: Placement) -> int:
        previous = None if placement.is_new else self._get_item_row(placement.index)
        row = self._make_row(event, previous)
        if placement.is_new:
            self._rows.insert(placement.index, row)
            self._slots.insert(placement.index, get_slot(event))
        else:
            self._rows[placement.index] = row
            self._slots[placement.index] = get_slot(event)
        return placement.index

    def can_toggle_skip(self, index: int) -> bool:
        return self._rows[index].status in SKIP_TOGGLES

    def toggle_skip(self, index: int, skip_list: SkipList) -> None:
        new_status = SKIP_TOGGLES.get(self._rows[index].status)
        if new_status is None:
            return
        slot = self._slots[index]
        is_skipped = new_status == RowStatus.SKIP_REQUESTED
        skip_list.set_skipped(slot.source_url, slot.item_id, is_skipped)
        self._rows[index] = replace(self._rows[index], status=new_status)

    def mark_unfinished_cancelled(self) -> None:
        self._settle_skip_requests()
        unfinished = (RowStatus.PENDING, RowStatus.STARTED, RowStatus.DOWNLOADING)
        self._replace_rows(unfinished, lambda row: replace(row, status=RowStatus.CANCELLED))

    def mark_pending_failed(self) -> None:
        def fail(row: DownloadRow) -> DownloadRow:
            return replace(row, status=RowStatus.FAILED, details=NOT_DOWNLOADED_MESSAGE)

        self._settle_skip_requests()
        self._replace_rows((RowStatus.PENDING, RowStatus.STARTED), fail)

    def clear(self) -> None:
        self._rows.clear()
        self._slots.clear()

    def get_summary(self) -> DownloadSummary:
        statuses = [row.status for row in self._rows]
        return DownloadSummary(
            completed=statuses.count(RowStatus.COMPLETED) + statuses.count(RowStatus.WARNING),
            with_warnings=statuses.count(RowStatus.WARNING),
            failed=statuses.count(RowStatus.FAILED),
            skipped=statuses.count(RowStatus.SKIPPED),
        )

    @singledispatchmethod
    def _make_row(self, event: DownloadEvent, previous: DownloadRow | None) -> DownloadRow:
        raise NotImplementedError(type(event))

    @_make_row.register
    def _make_queued_row(self, event: ItemQueued, previous: DownloadRow | None) -> DownloadRow:
        return previous or DownloadRow(event.item.title, RowStatus.PENDING, 0.0, "")

    @_make_row.register
    def _make_progress_row(self, event: ItemProgress, previous: DownloadRow | None) -> DownloadRow:
        return DownloadRow(event.item.title, RowStatus.DOWNLOADING, event.percent, "")

    @_make_row.register
    def _make_completed_row(
        self, event: ItemCompleted, previous: DownloadRow | None
    ) -> DownloadRow:
        status = RowStatus.WARNING if event.warnings else RowStatus.COMPLETED
        details = "; ".join(event.warnings) or str(event.file_path)
        return DownloadRow(event.item.title, status, 100.0, details)

    @_make_row.register
    def _make_failed_row(self, event: ItemFailed, previous: DownloadRow | None) -> DownloadRow:
        title = event.source_url if event.item is None else event.item.title
        percent = 0.0 if previous is None else previous.percent
        return DownloadRow(title, RowStatus.FAILED, percent, event.message)

    @_make_row.register
    def _make_skipped_row(self, event: ItemSkipped, previous: DownloadRow | None) -> DownloadRow:
        title = event.source_url if event.item is None else event.item.title
        return DownloadRow(title, RowStatus.SKIPPED, 0.0, "")

    @_make_row.register
    def _make_started_row(self, event: LinkStarted, previous: DownloadRow | None) -> DownloadRow:
        return DownloadRow(event.source_url, RowStatus.STARTED, 0.0, "")

    def _find_item_row(self, slot: RowSlot) -> int | None:
        if slot.item_id is None:
            return None
        return next((index for index, known in enumerate(self._slots) if known == slot), None)

    def _find_link_row(self, url: str) -> int | None:
        link = RowSlot(url, None)
        pending_links = (
            index
            for index, (slot, row) in enumerate(zip(self._slots, self._rows, strict=True))
            if slot == link and row.status in REPLACEABLE_LINK_STATUSES
        )
        return next(pending_links, None)

    def _get_item_row(self, index: int) -> DownloadRow | None:
        """Row an event updates; a pasted link's row is replaced, not updated."""
        return None if self._slots[index].item_id is None else self._rows[index]

    def _get_insert_index(self, url: str) -> int:
        indexes = [index for index, slot in enumerate(self._slots) if slot.source_url == url]
        return indexes[-1] + 1 if indexes else len(self._slots)

    def _settle_skip_requests(self) -> None:
        # The download is over, so a requested skip can no longer be undone.
        skipped = (RowStatus.SKIP_REQUESTED,)
        self._replace_rows(skipped, lambda row: replace(row, status=RowStatus.SKIPPED))

    def _replace_rows(
        self, statuses: tuple[RowStatus, ...], change: Callable[[DownloadRow], DownloadRow]
    ) -> None:
        self._rows = [change(row) if row.status in statuses else row for row in self._rows]
