from collections.abc import Sequence
from typing import Any, override

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from masterit.download.events import DownloadEvent
from masterit.gui.download_rows import (
    DownloadRow,
    DownloadRows,
    DownloadSummary,
    Placement,
    RowStatus,
)

type Index = QModelIndex | QPersistentModelIndex

HEADERS = ("Title", "Status", "Details")
ROOT = QModelIndex()
STATUS_COLORS = {
    RowStatus.FAILED: QColor(Qt.GlobalColor.red),
    RowStatus.PENDING: QColor(Qt.GlobalColor.gray),
}
STATUS_LABELS = {
    RowStatus.PENDING: "Pending",
    RowStatus.COMPLETED: "Done",
    RowStatus.WARNING: "Done with warnings",
    RowStatus.FAILED: "Failed",
    RowStatus.CANCELLED: "Cancelled",
}


def get_status_label(row: DownloadRow) -> str:
    return STATUS_LABELS.get(row.status) or f"Downloading {row.percent:.0f}%"


def get_cell_text(row: DownloadRow, column: int) -> str:
    return (row.title, get_status_label(row), row.details)[column]


class DownloadTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._rows = DownloadRows()

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
        return self._get_role_data(row, index.column(), role)

    def _get_role_data(self, row: DownloadRow, column: int, role: int) -> Any:
        if role == Qt.ItemDataRole.ForegroundRole:
            return STATUS_COLORS.get(row.status)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return get_cell_text(row, column)
        return None
