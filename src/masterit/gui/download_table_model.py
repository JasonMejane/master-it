from collections.abc import Iterable, Sequence
from typing import Any, override

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QColor

from masterit.download.events import DownloadEvent
from masterit.download.skip_list import SkipList
from masterit.gui.download_rows import (
    DownloadRow,
    DownloadRows,
    DownloadSummary,
    Placement,
    RowStatus,
)

type Index = QModelIndex | QPersistentModelIndex

HEADERS = ("", "Title", "Status", "Details")
CHECK_COLUMN = 0
STATUS_COLUMN = 2
CHECK_ROLE = Qt.ItemDataRole.CheckStateRole
ROOT = QModelIndex()
STATUS_COLORS = {
    RowStatus.FAILED: QColor(Qt.GlobalColor.red),
    RowStatus.PENDING: QColor(Qt.GlobalColor.gray),
    RowStatus.SKIP_REQUESTED: QColor(Qt.GlobalColor.gray),
    RowStatus.SKIPPED: QColor(Qt.GlobalColor.gray),
}
STATUS_LABELS = {
    RowStatus.PENDING: "Pending",
    RowStatus.STARTED: "Starting",
    RowStatus.COMPLETED: "Done",
    RowStatus.WARNING: "Done with warnings",
    RowStatus.FAILED: "Failed",
    RowStatus.CANCELLED: "Cancelled",
    RowStatus.SKIP_REQUESTED: "Will skip",
    RowStatus.SKIPPED: "Skipped",
}


def get_status_label(row: DownloadRow) -> str:
    return STATUS_LABELS.get(row.status) or f"Downloading {row.percent:.0f}%"


def get_cell_text(row: DownloadRow, column: int) -> str:
    return ("", row.title, get_status_label(row), row.details)[column]


def is_checked(row: DownloadRow) -> bool:
    return row.status != RowStatus.SKIP_REQUESTED


def get_check_state(row: DownloadRow) -> Qt.CheckState:
    return Qt.CheckState.Checked if is_checked(row) else Qt.CheckState.Unchecked


class DownloadTableModel(QAbstractTableModel):
    # Emitted for user check changes only, so a view can spread them to its selection.
    check_changed = Signal(int, bool)

    def __init__(self) -> None:
        super().__init__()
        self._rows = DownloadRows()
        # Only set while a download runs: rows can be skipped then.
        self._skip_list: SkipList | None = None

    def add_links(self, urls: Sequence[str]) -> None:
        if not urls:
            return
        count = self._rows.count
        self.beginInsertRows(ROOT, count, count + len(urls) - 1)
        self._rows.add_links(urls)
        self.endInsertRows()

    def apply_event(self, event: DownloadEvent) -> None:
        placement = self._rows.find_placement(event)
        if placement.is_new:
            self._insert_row(event, placement)
            return
        self._rows.apply_at(event, placement)
        last_column = len(HEADERS) - 1
        self.dataChanged.emit(
            self.index(placement.index, 0), self.index(placement.index, last_column)
        )

    def _insert_row(self, event: DownloadEvent, placement: Placement) -> None:
        self.beginInsertRows(ROOT, placement.index, placement.index)
        self._rows.apply_at(event, placement)
        self.endInsertRows()

    def set_skip_list(self, skip_list: SkipList | None) -> None:
        self._skip_list = skip_list
        self._emit_all_changed()

    def set_rows_checked(self, rows: Iterable[int], checked: bool) -> None:
        for row in rows:
            self._set_checked(row, checked)

    def mark_unfinished_cancelled(self) -> None:
        self._rows.mark_unfinished_cancelled()
        self._emit_all_changed()

    def mark_pending_failed(self) -> None:
        self._rows.mark_pending_failed()
        self._emit_all_changed()

    def _emit_all_changed(self) -> None:
        if not self._rows.count:
            return
        last_index = self.index(self._rows.count - 1, len(HEADERS) - 1)
        self.dataChanged.emit(self.index(0, 0), last_index)

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def get_summary(self) -> DownloadSummary:
        return self._rows.get_summary()

    @override
    def rowCount(self, parent: Index = ROOT) -> int:
        return 0 if parent.isValid() else self._rows.count

    @override
    def columnCount(self, parent: Index = ROOT) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    @override
    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    @override
    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = self._rows.get_row(index.row())
        if role == CHECK_ROLE:
            return get_check_state(row) if self._is_checkable(index) else None
        return self._get_role_data(row, index.column(), role)

    @override
    def flags(self, index: Index) -> Qt.ItemFlag:
        if self._is_checkable(index):
            return super().flags(index) | Qt.ItemFlag.ItemIsUserCheckable
        return super().flags(index)

    @override
    def setData(self, index: Index, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != CHECK_ROLE or not self._is_checkable(index):
            return False
        checked = Qt.CheckState(value) == Qt.CheckState.Checked
        if self._set_checked(index.row(), checked):
            self.check_changed.emit(index.row(), checked)
        return True

    def _set_checked(self, row: int, checked: bool) -> bool:
        skip_list = self._find_toggle_skip_list(self.index(row, CHECK_COLUMN))
        if skip_list is None or checked == is_checked(self._rows.get_row(row)):
            return False
        self._rows.toggle_skip(row, skip_list)
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(HEADERS) - 1))
        return True

    def _is_checkable(self, index: Index) -> bool:
        return self._find_toggle_skip_list(index) is not None

    def _find_toggle_skip_list(self, index: Index) -> SkipList | None:
        is_check_cell = index.isValid() and index.column() == CHECK_COLUMN
        if not (is_check_cell and self._rows.can_toggle_skip(index.row())):
            return None
        return self._skip_list

    def _get_role_data(self, row: DownloadRow, column: int, role: int) -> Any:
        if role == Qt.ItemDataRole.ForegroundRole:
            return STATUS_COLORS.get(row.status)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return get_cell_text(row, column)
        return None
