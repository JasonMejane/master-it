from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QWidget
from pytestqt.qtbot import QtBot

from masterit.gui.move_dialog import MoveDialog, confirm_move
from masterit.library.relocation import Relocation, RelocationPlan, RelocationProblem

DEST = Path("/library")


def make_dialog(qtbot: QtBot, plan: RelocationPlan) -> MoveDialog:
    dialog = MoveDialog(plan, DEST)
    qtbot.addWidget(dialog)
    return dialog


def test_dialog_lists_moves_and_skipped_files(qtbot: QtBot):
    plan = RelocationPlan(
        (
            Relocation(Path("/music/A.mp3"), DEST / "A.mp3"),
            Relocation(Path("/music/B.mp3"), DEST / "B.mp3", RelocationProblem.TARGET_EXISTS),
        )
    )
    dialog = make_dialog(qtbot, plan)
    assert dialog.summary_label.text() == "Move 1 file(s) to /library? 1 will be skipped."
    assert dialog.details.toPlainText() == (
        "A.mp3\nB.mp3 \u2014 skipped: A file with this name already exists"
    )
    ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button.isEnabled()


def test_dialog_without_valid_moves_cannot_be_confirmed(qtbot: QtBot):
    plan = RelocationPlan(
        (Relocation(Path("/music/B.mp3"), DEST / "B.mp3", RelocationProblem.TARGET_EXISTS),)
    )
    dialog = make_dialog(qtbot, plan)
    assert dialog.summary_label.text() == "Nothing can be moved to /library."
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_dialog_ok_and_cancel_close_it(qtbot: QtBot):
    plan = RelocationPlan((Relocation(Path("/music/A.mp3"), DEST / "A.mp3"),))
    dialog = make_dialog(qtbot, plan)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.result() == MoveDialog.DialogCode.Accepted
    dialog = make_dialog(qtbot, plan)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert dialog.result() == MoveDialog.DialogCode.Rejected


def test_confirm_move_is_true_only_when_accepted(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    plan = RelocationPlan((Relocation(Path("/music/A.mp3"), DEST / "A.mp3"),))
    parent = QWidget()
    qtbot.addWidget(parent)
    for code, expected in (
        (QDialog.DialogCode.Accepted, True),
        (QDialog.DialogCode.Rejected, False),
    ):
        monkeypatch.setattr(MoveDialog, "exec", make_exec(code))
        assert confirm_move(parent, plan, DEST) == expected


def make_exec(code: QDialog.DialogCode) -> Callable[[MoveDialog], QDialog.DialogCode]:
    def exec_dialog(self: MoveDialog) -> QDialog.DialogCode:
        return code

    return exec_dialog
