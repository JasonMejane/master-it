from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from masterit.library.relocation import Relocation
from masterit.repack.pipeline import RepackPlan


def format_repack_move(entry: Relocation, root: Path) -> str:
    if entry.problem is not None:
        return f"{entry.source.name} — skipped: {entry.problem}"
    return f"{entry.source.name} → {entry.target.relative_to(root).as_posix()}"


def format_repack_lines(plan: RepackPlan, root: Path) -> list[str]:
    moves = [format_repack_move(entry, root) for entry in plan.moves.entries]
    in_place = [f"{path.name} — already in place" for path in plan.in_place]
    return [*moves, *in_place]


def format_repack_summary(plan: RepackPlan, root: Path) -> str:
    move_count = len(plan.moves.valid_entries)
    tag_count = move_count + len(plan.in_place)
    if not tag_count:
        return f"Nothing can be repacked into {root}."
    skipped_count = len(plan.moves.entries) - move_count
    skipped = f" {skipped_count} will be skipped." if skipped_count else ""
    question = f"Move {move_count} file(s) into {root}, then auto-tag {tag_count}"
    return f"{question} (existing tags are replaced)?{skipped}"


class RepackDialog(QDialog):
    def __init__(self, plan: RepackPlan, root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Repack files")
        self.summary_label = QLabel(format_repack_summary(plan, root))
        self.summary_label.setWordWrap(True)
        self.details = QPlainTextEdit("\n".join(format_repack_lines(plan, root)))
        self.details.setReadOnly(True)
        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.buttons = QDialogButtonBox(buttons)
        has_work = bool(plan.moves.valid_entries or plan.in_place)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(has_work)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.details)
        layout.addWidget(self.buttons)


def confirm_repack(parent: QWidget, plan: RepackPlan, root: Path) -> bool:
    return RepackDialog(plan, root, parent).exec() == QDialog.DialogCode.Accepted
