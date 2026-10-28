from collections.abc import Iterable, Mapping
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

from masterit.gui.tag_labels import TAG_LABELS
from masterit.library.relocation import Relocation, RelocationPlan
from masterit.tagging.run_tracker import AutoTagCell
from masterit.tags.fields import TagField, Tags
from masterit.tags.tag_cache import TagCache

type Index = QModelIndex | QPersistentModelIndex

FILE_HEADERS = ("Name", "New name", "Folder")
TAG_COLUMNS = tuple(TagField)
TAG_HEADERS = tuple(TAG_LABELS[field] for field in TAG_COLUMNS)
HEADERS = (*FILE_HEADERS, *TAG_HEADERS, "Auto-tag")
NAME_COLUMN = 0
PREVIEW_COLUMN = 1
FIRST_TAG_COLUMN = len(FILE_HEADERS)
AUTO_TAG_COLUMN = FIRST_TAG_COLUMN + len(TAG_COLUMNS)
NO_AUTO_TAG = AutoTagCell("")
ROOT = QModelIndex()
PROBLEM_COLOR = QColor(Qt.GlobalColor.red)
PENDING_COLOR = QColor(Qt.GlobalColor.blue)


def get_preview_text(entry: Relocation | None) -> str:
    if entry is None:
        return ""
    return entry.target.name if entry.problem is None else f"⚠ {entry.problem}"


def get_tag_field(column: int) -> TagField | None:
    is_tag_column = FIRST_TAG_COLUMN <= column < AUTO_TAG_COLUMN
    return TAG_COLUMNS[column - FIRST_TAG_COLUMN] if is_tag_column else None


def describe_folder(path: Path, resolved_root: Path | None) -> str:
    if resolved_root is None:
        return str(path.parent)
    relative = path.parent.resolve().relative_to(resolved_root)
    return "" if relative == Path() else str(relative)


class LibraryTableModel(QAbstractTableModel):
    rename_requested = Signal(object, str)

    def __init__(self, tag_cache: TagCache) -> None:
        super().__init__()
        self._tag_cache = tag_cache
        self._tag_preview_paths: set[Path] = set()
        self._tag_edits: Tags = {}
        # Kept across reloads: it reports this session's runs, keyed by the files' final paths.
        self._auto_tag_statuses: dict[Path, AutoTagCell] = {}
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
        self._tag_cache.clear()
        self._tag_preview_paths = set()
        self._tag_edits = {}
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

    def get_tags(self, path: Path) -> Tags:
        return self._tag_cache.get(path)

    def set_tag_preview(self, paths: Iterable[Path], edits: Tags) -> None:
        self._tag_preview_paths = set(paths)
        self._tag_edits = dict(edits)
        self._emit_tags_changed()

    def refresh_tags(self, paths: Iterable[Path]) -> None:
        self._tag_cache.forget(paths)
        self._emit_tags_changed()

    def set_auto_tag_statuses(self, statuses: Mapping[Path, AutoTagCell]) -> None:
        self._auto_tag_statuses.update(statuses)
        self._emit_tags_changed()

    def _emit_tags_changed(self) -> None:
        if not self._files:
            return
        last_row = len(self._files) - 1
        last_column = len(HEADERS) - 1
        self.dataChanged.emit(self.index(0, FIRST_TAG_COLUMN), self.index(last_row, last_column))

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
            Qt.ItemDataRole.ToolTipRole: self._get_tool_tip,
        }
        handler = handlers.get(Qt.ItemDataRole(role))
        return None if handler is None else handler(path, column)

    def _get_display_text(self, path: Path, column: int) -> str:
        field = get_tag_field(column)
        if field is not None:
            return self._get_tag_text(path, field)
        if column == AUTO_TAG_COLUMN:
            return self._auto_tag_statuses.get(path, NO_AUTO_TAG).status
        texts = (path.name, get_preview_text(self._preview.get(path)), self._folder_texts[path])
        return texts[column]

    def _get_tag_text(self, path: Path, field: TagField) -> str:
        if self._is_tag_pending(path, field):
            return self._tag_edits[field]
        return self._tag_cache.get(path).get(field, "")

    def _is_tag_pending(self, path: Path, field: TagField) -> bool:
        return path in self._tag_preview_paths and field in self._tag_edits

    def _get_tool_tip(self, path: Path, column: int) -> str | None:
        if column != AUTO_TAG_COLUMN:
            return None
        return self._auto_tag_statuses.get(path, NO_AUTO_TAG).reason or None

    def _get_edit_text(self, path: Path, column: int) -> str:
        return path.stem

    def _get_foreground(self, path: Path, column: int) -> QColor | None:
        field = get_tag_field(column)
        if field is not None:
            return PENDING_COLOR if self._is_tag_pending(path, field) else None
        entry = self._preview.get(path)
        has_problem = column == PREVIEW_COLUMN and entry is not None and not entry.is_valid
        return PROBLEM_COLOR if has_problem else None
