from collections.abc import Iterable, Mapping
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from masterit.gui.auto_tag_action import AutoTagAction
from masterit.gui.cover_view import CoverView
from masterit.gui.library_services import LibraryServices
from masterit.gui.library_source import LibrarySource
from masterit.gui.library_table_model import LibraryTableModel
from masterit.gui.move_action import MoveAction
from masterit.gui.rename_bar import RenameBar
from masterit.gui.source_bar import SourceBar
from masterit.gui.styling import make_card, make_section, mark_muted
from masterit.gui.summaries import format_relocation_summary, format_tag_summary
from masterit.gui.tag_form import TagForm
from masterit.library.relocation import (
    RelocationOutcome,
    RelocationPlan,
    replace_relocated_paths,
)
from masterit.tagging.run_tracker import AutoTagCell
from masterit.tags.fields import Tags
from masterit.tags.tag_cache import TagCache, make_tag_cache
from masterit.tags.tag_edits import TagOutcome


class LibraryPanel(QWidget):
    work_finished = Signal()

    def __init__(self, services: LibraryServices) -> None:
        super().__init__()
        self._source = LibrarySource()
        self._build_table(make_tag_cache(services.tag_store))
        self.status_label = QLabel()
        mark_muted(self.status_label)
        self.source_bar = SourceBar()
        self.rename_bar = RenameBar(self)
        self.move_action = MoveAction(
            self,
            services.get_download_folder,
            services.is_downloading,
            services.thread_pool,
            services.confirm_move,
        )
        self.tag_form = TagForm(self, services.tag_store, services.thread_pool)
        self.cover_view = CoverView(self, services.cover_store)
        self.auto_tag_action = AutoTagAction(self, services)
        self._build_layout()
        self._connect_signals()
        self._refresh_selection_views()

    @property
    def is_busy(self) -> bool:
        jobs = (self.move_action.is_moving, self.tag_form.is_tagging)
        return any(jobs) or self.auto_tag_action.is_running

    def stop_work(self) -> None:
        self.auto_tag_action.cancel()

    @property
    def opened_folder(self) -> Path | None:
        return self._source.folder

    def add_downloaded_file(self, path: Path) -> None:
        if self._source.add_download(path):
            self.table_model.append_file(path)
            return
        # A download may overwrite a listed file; refreshing the form would drop pending edits.
        self.table_model.refresh_tags([path])
        self.cover_view.forget([path])
        self.cover_view.load_selection()
        self.rename_bar.refresh_preview()

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

    def show_tag_preview(self, edits_by_path: Mapping[Path, Tags]) -> None:
        self.table_model.set_tag_preview(edits_by_path)

    def finish_tagging(self, paths: list[Path], outcomes: list[TagOutcome]) -> None:
        self.table_model.refresh_tags(paths)
        self.tag_form.load_selection()
        self.show_status(format_tag_summary(outcomes))

    def show_auto_tag_statuses(self, statuses: Mapping[Path, AutoTagCell]) -> None:
        self.table_model.set_auto_tag_statuses(statuses)

    def refresh_tags(self, paths: Iterable[Path]) -> None:
        refreshed = list(paths)
        self.table_model.refresh_tags(refreshed)
        self.cover_view.forget(refreshed)
        self.tag_form.load_selection()
        self.cover_view.load_selection()

    def _refresh_selection_views(self) -> None:
        self.rename_bar.refresh_preview()
        self.tag_form.load_selection()
        self.cover_view.load_selection()

    def _set_busy(self, busy: bool) -> None:
        widgets = (self.source_bar, self.move_action, self.rename_bar, self.tag_form)
        for widget in (*widgets, self.table_view):
            widget.setEnabled(not busy)
        self.auto_tag_action.set_busy(busy)
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
        self.table_view.setAlternatingRowColors(True)
        self.table_view.verticalHeader().hide()
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(make_card(self._build_toolbar_form()))
        layout.addWidget(self._build_content_splitter(), stretch=1)
        layout.addWidget(self.status_label)

    def _build_toolbar_form(self) -> QFormLayout:
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_bar, stretch=1)
        source_row.addWidget(self.move_action)
        form = QFormLayout()
        form.addRow("Source", source_row)
        form.addRow("Library", self.auto_tag_action)
        return form

    def _build_files_part(self) -> QFrame:
        files_column = QVBoxLayout()
        files_column.addWidget(self.table_view, stretch=1)
        files_column.addWidget(self.rename_bar)
        return make_section("Files", files_column)

    def _build_content_splitter(self) -> QSplitter:
        side_panel = QWidget()
        side_column = QVBoxLayout(side_panel)
        side_column.setContentsMargins(0, 0, 0, 0)
        side_column.addWidget(self.cover_view, stretch=1)
        side_column.addWidget(self.tag_form)
        side_column.addStretch()
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.addWidget(self._build_files_part())
        self.content_splitter.addWidget(make_section("Tag editor", side_panel))
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setStretchFactor(0, 7)
        self.content_splitter.setStretchFactor(1, 3)
        # Size hints alone would skew the default split, the rename bar being wide.
        self.content_splitter.setSizes([7000, 3000])
        return self.content_splitter

    def _connect_signals(self) -> None:
        self.source_bar.folder_chosen.connect(self.open_folder)
        self.source_bar.session_requested.connect(self.show_session)
        self.table_view.selectionModel().selectionChanged.connect(self._refresh_selection_views)
        self.table_model.modelReset.connect(self.cover_view.clear_cache)
        for action in (self.move_action, self.tag_form, self.auto_tag_action):
            action.started.connect(lambda: self._set_busy(True))
            action.finished.connect(lambda: self._set_busy(False))
            action.finished.connect(self.work_finished)
        # Queued: renaming reloads the model, which must not happen inside the editor commit.
        self.tag_form.name_from_tags_requested.connect(self.rename_bar.use_name_from_tags)
        self.table_model.rename_requested.connect(
            self.rename_bar.rename_single_file, Qt.ConnectionType.QueuedConnection
        )
