from pathlib import Path
from typing import Any, override

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor

from masterit.library.relocation import Relocation, RelocationPlan

type Index = QModelIndex | QPersistentModelIndex

HEADERS = ("Name", "New name", "Folder")
NAME_COLUMN = 0
PREVIEW_COLUMN = 1
ROOT = QModelIndex()
PROBLEM_COLOR = QColor(Qt.GlobalColor.red)


def get_preview_text(entry: Relocation | None) -> str:
    if entry is None:
        return ""
    return entry.target.name if entry.problem is None else f"⚠ {entry.problem}"


def describe_folder(path: Path, resolved_root: Path | None) -> str:
    if resolved_root is None:
        return str(path.parent)
    relative = path.parent.resolve().relative_to(resolved_root)
    return "" if relative == Path() else str(relative)


class LibraryTableModel(QAbstractTableModel):
    rename_requested = Signal(object, str)

    def __init__(self) -> None:
        super().__init__()
        self._files: list[Path] = []
        self._root: Path | None = None
        self._folder_texts: dict[Path, str] = {}
        self._preview: dict[Path, Relocation] = {}

    def set_files(self, files: list[Path], root: Path | None) -> None:
        self.beginResetModel()
        self._files = list(files)
        self._root = None if root is None else root.resolve()
        self._folder_texts = {path: describe_folder(path, self._root) for path in files}
        self._preview = {}
        self.endResetModel()

    def append_file(self, path: Path) -> None:
        row = len(self._files)
        self.beginInsertRows(ROOT, row, row)
        self._files.append(path)
        self._folder_texts[path] = describe_folder(path, self._root)
        self.endInsertRows()

    def get_files(self) -> list[Path]:
        return list(self._files)

    def get_path(self, row: int) -> Path:
        return self._files[row]

    def set_preview(self, plan: RelocationPlan) -> None:
        self._preview = {entry.source: entry for entry in plan.entries}
        if not self._files:
            return
        last_row = len(self._files) - 1
        self.dataChanged.emit(self.index(0, PREVIEW_COLUMN), self.index(last_row, PREVIEW_COLUMN))

    @override
    def rowCount(self, parent: Index = ROOT) -> int:
        return 0 if parent.isValid() else len(self._files)

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
    def flags(self, index: Index) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        editable = (
            Qt.ItemFlag.ItemIsEditable if index.column() == NAME_COLUMN else Qt.ItemFlag.NoItemFlags
        )
        return super().flags(index) | editable

    @override
    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        return self._get_role_data(self._files[index.row()], index.column(), role)

    @override
    def setData(self, index: Index, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if index.column() == NAME_COLUMN and role == Qt.ItemDataRole.EditRole:
            self.rename_requested.emit(self._files[index.row()], str(value))
        return False

    def _get_role_data(self, path: Path, column: int, role: int) -> Any:
        handlers = {
            Qt.ItemDataRole.DisplayRole: self._get_display_text,
            Qt.ItemDataRole.EditRole: self._get_edit_text,
            Qt.ItemDataRole.ForegroundRole: self._get_foreground,
        }
        handler = handlers.get(Qt.ItemDataRole(role))
        return None if handler is None else handler(path, column)

    def _get_display_text(self, path: Path, column: int) -> str:
        texts = (path.name, get_preview_text(self._preview.get(path)), self._folder_texts[path])
        return texts[column]

    def _get_edit_text(self, path: Path, column: int) -> str:
        return path.stem

    def _get_foreground(self, path: Path, column: int) -> QColor | None:
        entry = self._preview.get(path)
        has_problem = column == PREVIEW_COLUMN and entry is not None and not entry.is_valid
        return PROBLEM_COLOR if has_problem else None
