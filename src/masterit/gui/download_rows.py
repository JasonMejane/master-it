from dataclasses import dataclass, replace
from enum import Enum, auto
from functools import singledispatchmethod

from masterit.download.events import DownloadEvent, ItemCompleted, ItemFailed, ItemProgress


class RowStatus(Enum):
    DOWNLOADING = auto()
    COMPLETED = auto()
    WARNING = auto()
    FAILED = auto()
    CANCELLED = auto()


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


type RowKey = tuple[str, str]


def get_row_key(event: DownloadEvent) -> RowKey | None:
    return None if event.item is None else (event.source_url, event.item.item_id)


class DownloadRows:
    def __init__(self) -> None:
        self._rows: list[DownloadRow] = []
        self._index_by_key: dict[RowKey, int] = {}

    @property
    def count(self) -> int:
        return len(self._rows)

    def get_row(self, index: int) -> DownloadRow:
        return self._rows[index]

    def is_new_row(self, event: DownloadEvent) -> bool:
        key = get_row_key(event)
        return key is None or key not in self._index_by_key

    def mark_unfinished_cancelled(self) -> None:
        self._rows = [
            replace(row, status=RowStatus.CANCELLED) if row.status == RowStatus.DOWNLOADING else row
            for row in self._rows
        ]

    def clear(self) -> None:
        self._rows.clear()
        self._index_by_key.clear()

    def get_summary(self) -> DownloadSummary:
        statuses = [row.status for row in self._rows]
        return DownloadSummary(
            completed=statuses.count(RowStatus.COMPLETED) + statuses.count(RowStatus.WARNING),
            with_warnings=statuses.count(RowStatus.WARNING),
            failed=statuses.count(RowStatus.FAILED),
        )

    @singledispatchmethod
    def apply(self, event: DownloadEvent) -> int:
        raise NotImplementedError(type(event))

    @apply.register
    def _apply_progress(self, event: ItemProgress) -> int:
        row = DownloadRow(event.item.title, RowStatus.DOWNLOADING, event.percent, "")
        return self._upsert((event.source_url, event.item.item_id), row)

    @apply.register
    def _apply_completed(self, event: ItemCompleted) -> int:
        status = RowStatus.WARNING if event.warnings else RowStatus.COMPLETED
        details = "; ".join(event.warnings) or str(event.file_path)
        row = DownloadRow(event.item.title, status, 100.0, details)
        return self._upsert((event.source_url, event.item.item_id), row)

    @apply.register
    def _apply_failed(self, event: ItemFailed) -> int:
        if event.item is None:
            return self._append(DownloadRow(event.source_url, RowStatus.FAILED, 0.0, event.message))
        key = (event.source_url, event.item.item_id)
        percent = self._get_percent(key)
        row = DownloadRow(event.item.title, RowStatus.FAILED, percent, event.message)
        return self._upsert(key, row)

    def _get_percent(self, key: RowKey) -> float:
        index = self._index_by_key.get(key)
        return 0.0 if index is None else self._rows[index].percent

    def _upsert(self, key: RowKey, row: DownloadRow) -> int:
        index = self._index_by_key.get(key)
        if index is None:
            self._index_by_key[key] = self._append(row)
            return self._index_by_key[key]
        self._rows[index] = row
        return index

    def _append(self, row: DownloadRow) -> int:
        self._rows.append(row)
        return len(self._rows) - 1
