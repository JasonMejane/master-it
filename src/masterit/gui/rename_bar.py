from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from masterit.gui.library_context import RenameContext
from masterit.gui.styling import make_primary_button, mark_muted
from masterit.library.destinations import DestinationMaker, make_rename_destination
from masterit.library.library_layout import TagReader, make_tag_name_destination
from masterit.library.relocation import (
    RelocationPlan,
    apply_relocation_plan,
    make_relocation_plan,
)
from masterit.library.rename_rules import AddPrefix, AddSuffix, RemoveText, RenameRule, SetName

type DestinationFactory = Callable[[str, TagReader], DestinationMaker]


@dataclass(frozen=True)
class RenameOperation:
    label: str
    make_destination: DestinationFactory
    uses_text: bool = True
    no_change_hint: str = ""


def make_rule_operation(
    label: str, rule: Callable[[str], RenameRule], no_change_hint: str = ""
) -> RenameOperation:
    def make_destination(text: str, read_tags: TagReader) -> DestinationMaker:
        return make_rename_destination(rule(text))

    return RenameOperation(label, make_destination, no_change_hint=no_change_hint)


NAME_FROM_TAGS = RenameOperation(
    "Name from tags", lambda _, read_tags: make_tag_name_destination(read_tags), uses_text=False
)
OPERATIONS = (
    make_rule_operation(
        "Remove text", RemoveText, "No selected file name (without extension) contains this text."
    ),
    make_rule_operation("Add prefix", AddPrefix),
    make_rule_operation("Add suffix", AddSuffix),
    NAME_FROM_TAGS,
)


def remove_extension(name: str, suffix: str) -> str:
    return name[: -len(suffix)] if name.lower().endswith(suffix.lower()) else name


class RenameBar(QWidget):
    def __init__(self, context: RenameContext) -> None:
        super().__init__()
        self._context = context
        self._plan = RelocationPlan(())
        self._build_widgets()
        self._build_layout()
        self.operation_input.currentIndexChanged.connect(self.refresh_preview)
        self.rename_text_input.textChanged.connect(self.refresh_preview)
        self.apply_button.clicked.connect(self.apply_rename)

    def refresh_preview(self) -> None:
        operation = self._get_operation()
        self.rename_text_input.setEnabled(operation.uses_text)
        destination = operation.make_destination(
            self.rename_text_input.text(), self._context.get_tags
        )
        self._plan = make_relocation_plan(self._context.get_selected_paths(), destination)
        self._context.show_preview(self._plan)
        self.apply_button.setEnabled(bool(self._plan.valid_entries) and not self._context.is_busy)
        self.hint_label.setText(self._get_hint(operation))

    def _get_hint(self, operation: RenameOperation) -> str:
        has_text = bool(self.rename_text_input.text().strip())
        is_unchanged = bool(self._context.get_selected_paths()) and not self._plan.entries
        return operation.no_change_hint if has_text and is_unchanged else ""

    def use_name_from_tags(self) -> None:
        self.operation_input.setCurrentIndex(self.operation_input.findText(NAME_FROM_TAGS.label))

    def apply_rename(self) -> None:
        if self._context.is_busy:
            return
        skipped = len(self._plan.entries) - len(self._plan.valid_entries)
        self._context.finish_relocation("renamed", apply_relocation_plan(self._plan), skipped)
        self.rename_text_input.clear()

    def rename_single_file(self, path: Path, name: str) -> None:
        # Queued after the editor commit, so a job may have started in between.
        if self._context.is_busy:
            self._context.show_status("Busy: rename ignored.")
            return
        self._rename_single_file(path, name)

    def _rename_single_file(self, path: Path, name: str) -> None:
        plan = make_relocation_plan(
            [path], make_rename_destination(SetName(remove_extension(name, path.suffix)))
        )
        problems = [str(entry.problem) for entry in plan.entries if not entry.is_valid]
        if problems:
            self._context.show_status(problems[0])
            return
        if plan.entries:
            self._context.finish_relocation("renamed", apply_relocation_plan(plan), skipped=0)

    def _get_operation(self) -> RenameOperation:
        return OPERATIONS[self.operation_input.currentIndex()]

    def _build_widgets(self) -> None:
        self.operation_input = QComboBox()
        for operation in OPERATIONS:
            self.operation_input.addItem(operation.label)
        self.rename_text_input = QLineEdit()
        self.rename_text_input.setPlaceholderText("Text")
        self.apply_button = make_primary_button("Rename selected", "pencil-line")
        self.apply_button.setEnabled(False)
        self.hint_label = QLabel()
        mark_muted(self.hint_label)
        # A line is kept for the hint so the bar does not jump while typing.
        self.hint_label.setMinimumHeight(self.hint_label.fontMetrics().height())
        self.hint_label.setWordWrap(True)

    def _build_layout(self) -> None:
        row = QHBoxLayout()
        row.addWidget(self.operation_input)
        row.addWidget(self.rename_text_input, stretch=1)
        row.addWidget(self.apply_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(row)
        layout.addWidget(self.hint_label)
