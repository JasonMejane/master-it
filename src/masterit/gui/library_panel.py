from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from masterit.gui.library_source import LibrarySource
from masterit.gui.library_table_model import LibraryTableModel
from masterit.gui.move_action import MoveAction, MoveConfirmation
from masterit.gui.move_dialog import confirm_move
from masterit.gui.rename_bar import RenameBar
from masterit.gui.source_bar import SourceBar
from masterit.gui.summaries import format_relocation_summary, format_tag_summary
from masterit.gui.tag_form import TagForm
from masterit.library.relocation import (
    RelocationOutcome,
    RelocationPlan,
    replace_relocated_paths,
)
from masterit.tags.fields import Tags
from masterit.tags.tag_cache import TagCache
from masterit.tags.tag_edits import TagOutcome
from masterit.tags.tag_store import TagStore


class LibraryPanel(QWidget):
    work_finished = Signal()

    def __init__(
        self,
        get_download_folder: Callable[[], Path],
        is_downloading: Callable[[], bool],
        thread_pool: QThreadPool,
        tag_store: TagStore,
        confirm: MoveConfirmation = confirm_move,
    ) -> None:
        super().__init__()
        self._source = LibrarySource()
        self._build_table(TagCache(tag_store))
        self.status_label = QLabel()
        self.source_bar = SourceBar()
        self.rename_bar = RenameBar(self)
        self.move_action = MoveAction(
            self, get_download_folder, is_downloading, thread_pool, confirm
        )
        self.tag_form = TagForm(self, tag_store, thread_pool)
        self._build_layout()
        self._connect_signals()
        self._refresh_selection_views()

    @property
    def is_busy(self) -> bool:
        return self.move_action.is_moving or self.tag_form.is_tagging

    @property
    def opened_folder(self) -> Path | None:
        return self._source.folder

    def add_downloaded_file(self, path: Path) -> None:
        if self._source.add_download(path):
            self.table_model.append_file(path)

    def open_folder(self, folder: Path) -> None:
        self._source.open_folder(folder)
        self._reload_files()

    def show_session(self) -> None:
        self._source.show_session()
        self._reload_files()

    def get_selected_paths(self) -> list[Path]:
        rows = sorted(index.row() for index in self.table_view.selectionModel().selectedRows())
        return [self.table_model.get_path(row) for row in rows]

    def show_status(self, text: str) -> None:
        self.status_label.setText(text)

    def show_preview(self, plan: RelocationPlan) -> None:
        self.table_model.set_preview(plan)

    def finish_relocation(self, verb: str, outcomes: list[RelocationOutcome], skipped: int) -> None:
        self._source.replace_relocated(outcomes)
        listed_files = replace_relocated_paths(self.table_model.get_files(), outcomes)
        self.table_model.set_files(self._source.keep_visible(listed_files), self._source.folder)
        self._refresh_selection_views()
        self.show_status(format_relocation_summary(verb, outcomes, skipped))

    def get_tags(self, path: Path) -> Tags:
        return self.table_model.get_tags(path)

    def show_tag_preview(self, paths: Iterable[Path], edits: Tags) -> None:
        self.table_model.set_tag_preview(paths, edits)

    def finish_tagging(self, paths: list[Path], outcomes: list[TagOutcome]) -> None:
        self.table_model.refresh_tags(paths)
        self.tag_form.load_selection()
        self.show_status(format_tag_summary(outcomes))

    def _refresh_selection_views(self) -> None:
        self.rename_bar.refresh_preview()
        self.tag_form.load_selection()

    def _set_busy(self, busy: bool) -> None:
        widgets = (self.source_bar, self.move_action, self.rename_bar, self.tag_form)
        for widget in (*widgets, self.table_view):
            widget.setEnabled(not busy)
        self.rename_bar.refresh_preview()

    def _reload_files(self) -> None:
        self.table_model.set_files(self._source.list_files(), self._source.folder)
        self.source_bar.source_label.setText(self._source.describe())
        self._refresh_selection_views()

    def _build_table(self, tag_cache: TagCache) -> None:
        self.table_model = LibraryTableModel(tag_cache)
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    def _build_layout(self) -> None:
        top_row = QHBoxLayout()
        top_row.addWidget(self.source_bar, stretch=1)
        top_row.addWidget(self.move_action)
        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        content_row = QHBoxLayout()
        content_row.addWidget(self.table_view, stretch=1)
        content_row.addWidget(self.tag_form)
        layout.addLayout(content_row, stretch=1)
        layout.addWidget(self.rename_bar)
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.source_bar.folder_chosen.connect(self.open_folder)
        self.source_bar.session_requested.connect(self.show_session)
        self.table_view.selectionModel().selectionChanged.connect(self._refresh_selection_views)
        for action in (self.move_action, self.tag_form):
            action.started.connect(lambda: self._set_busy(True))
            action.finished.connect(lambda: self._set_busy(False))
            action.finished.connect(self.work_finished)
        # Queued: renaming reloads the model, which must not happen inside the editor commit.
        self.table_model.rename_requested.connect(
            self.rename_bar.rename_single_file, Qt.ConnectionType.QueuedConnection
        )
