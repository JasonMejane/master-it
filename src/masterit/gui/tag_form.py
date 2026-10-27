from functools import partial
from pathlib import Path

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QWidget,
)

from masterit.gui.library_context import TagContext
from masterit.gui.tag_job import TagJob
from masterit.gui.tag_labels import TAG_LABELS
from masterit.tags.fields import TagField, Tags
from masterit.tags.tag_edits import TagOutcome, find_tag_problem, merge_tag_values
from masterit.tags.tag_store import TagStore

MIXED_PLACEHOLDER = "<multiple values>"
REMOVED_PLACEHOLDER = "<removed>"


def get_placeholder(shared_value: str | None, edit: str | None) -> str:
    if edit == "":
        return REMOVED_PLACEHOLDER
    return MIXED_PLACEHOLDER if shared_value is None else ""


class TagForm(QWidget):
    started = Signal()
    finished = Signal()

    def __init__(self, context: TagContext, store: TagStore, thread_pool: QThreadPool) -> None:
        super().__init__()
        self._context = context
        self._store = store
        self._thread_pool = thread_pool
        self._shared: dict[TagField, str | None] = merge_tag_values([])
        self._edits: Tags = {}
        self._cleared: set[TagField] = set()
        self._job: TagJob | None = None
        self._job_paths: list[Path] = []
        self._crash = ""
        self._build_widgets()
        self._build_layout()
        self._connect_signals()

    @property
    def is_tagging(self) -> bool:
        return self._job is not None

    def load_selection(self) -> None:
        paths = self._context.get_selected_paths()
        self._shared = merge_tag_values([self._context.get_tags(path) for path in paths])
        self._edits = {}
        self._cleared = set()
        for field, line in self.field_inputs.items():
            line.setText(self._shared[field] or "")
            line.setEnabled(bool(paths))
            self._show_field_state(field)
        self._update_preview()

    def apply_tags(self) -> None:
        if not self._can_apply():
            return
        self._job_paths = self._context.get_selected_paths()
        job = TagJob(self._job_paths, dict(self._edits), self._store)
        job.signals.progress.connect(self._show_progress)
        job.signals.crashed.connect(self._remember_crash)
        job.signals.finished.connect(self._finish)
        self._job = job
        self._crash = ""
        self.started.emit()
        self._show_progress(0, len(self._job_paths))
        self._thread_pool.start(job)

    def _edit_field(self, field: TagField, text: str) -> None:
        is_unchanged = text == (self._shared[field] or "") and field not in self._cleared
        if is_unchanged:
            self._edits.pop(field, None)
        else:
            self._edits[field] = text
        self._show_field_state(field)
        self._update_preview()

    def _clear_field(self, field: TagField) -> None:
        self.field_inputs[field].clear()
        self._cleared.add(field)
        self._edits[field] = ""
        self._show_field_state(field)
        self._update_preview()

    def _show_field_state(self, field: TagField) -> None:
        shared_value = self._shared[field]
        placeholder = get_placeholder(shared_value, self._edits.get(field))
        self.field_inputs[field].setPlaceholderText(placeholder)
        self.clear_actions[field].setVisible(shared_value != "")

    def _update_preview(self) -> None:
        self._context.show_tag_preview(self._context.get_selected_paths(), self._edits)
        self.apply_button.setEnabled(self._can_apply())
        self.reset_button.setEnabled(bool(self._edits))
        self.problem_label.setText(find_tag_problem(self._edits) or "")

    def _can_apply(self) -> bool:
        has_work = bool(self._edits) and bool(self._context.get_selected_paths())
        is_valid = find_tag_problem(self._edits) is None
        return has_work and is_valid and not self._context.is_busy

    def _show_progress(self, done: int, total: int) -> None:
        self._context.show_status(f"Tagging {done}/{total}…")

    def _remember_crash(self, message: str) -> None:
        self._crash = message

    def _finish(self, outcomes: list[TagOutcome]) -> None:
        self._job = None
        self._context.finish_tagging(self._job_paths, outcomes)
        if self._crash:
            self._context.show_status(f"Tagging stopped by an unexpected error: {self._crash}")
        self.finished.emit()

    def _build_widgets(self) -> None:
        clear_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton)
        self.field_inputs = {field: QLineEdit() for field in TagField}
        self.clear_actions: dict[TagField, QAction] = {}
        for field, line in self.field_inputs.items():
            action = QAction(clear_icon, "Remove from all selected files", line)
            line.addAction(action, QLineEdit.ActionPosition.TrailingPosition)
            self.clear_actions[field] = action
        self.apply_button = QPushButton("Apply tags")
        self.reset_button = QPushButton("Reset")
        self.problem_label = QLabel()
        self.problem_label.setWordWrap(True)

    def _build_layout(self) -> None:
        form = QFormLayout()
        for field, line in self.field_inputs.items():
            form.addRow(TAG_LABELS[field], line)
        buttons = QHBoxLayout()
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.apply_button)
        form.addRow(self.problem_label)
        form.addRow(buttons)
        form.setContentsMargins(0, 0, 0, 0)
        self.setLayout(form)

    def _connect_signals(self) -> None:
        for field, line in self.field_inputs.items():
            line.textEdited.connect(partial(self._edit_field, field))
            self.clear_actions[field].triggered.connect(partial(self._clear_field, field))
        self.apply_button.clicked.connect(self.apply_tags)
        self.reset_button.clicked.connect(self.load_selection)
