from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QWidget
from pytestqt.qtbot import QtBot

from masterit.gui.repack_dialog import RepackDialog, confirm_repack
from masterit.library.relocation import Relocation, RelocationPlan, RelocationProblem
from masterit.repack.pipeline import RepackPlan

ROOT = Path("/library")
MOVE = Relocation(Path("/dl/a.mp3"), ROOT / "Queen" / "Queen - A.mp3")
SKIP = Relocation(Path("/dl/b.mp3"), Path("/dl/b.mp3"), RelocationProblem.MISSING_TAGS)
IN_PLACE = ROOT / "ABBA" / "ABBA - SOS.opus"


def make_dialog(qtbot: QtBot, plan: RepackPlan) -> RepackDialog:
    dialog = RepackDialog(plan, ROOT)
    qtbot.addWidget(dialog)
    return dialog


def get_ok_button(dialog: RepackDialog) -> QWidget:
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)


def test_dialog_lists_moves_files_in_place_and_skipped_files(qtbot: QtBot):
    dialog = make_dialog(qtbot, RepackPlan(RelocationPlan((MOVE, SKIP)), (IN_PLACE,)))
    assert dialog.summary_label.text() == (
        "Move 1 file(s) into /library, then auto-tag 2"
        " (existing tags are replaced)? 1 will be skipped."
    )
    assert dialog.details.toPlainText() == (
        "a.mp3 → Queen/Queen - A.mp3\n"
        "b.mp3 — skipped: No artist or title tag\n"
        "ABBA - SOS.opus — already in place"
    )
    assert get_ok_button(dialog).isEnabled()


def test_dialog_without_files_to_tag_cannot_be_confirmed(qtbot: QtBot):
    dialog = make_dialog(qtbot, RepackPlan(RelocationPlan((SKIP,)), ()))
    assert dialog.summary_label.text() == "Nothing can be repacked into /library."
    assert not get_ok_button(dialog).isEnabled()


def test_dialog_with_files_in_place_only_offers_tagging(qtbot: QtBot):
    dialog = make_dialog(qtbot, RepackPlan(RelocationPlan(()), (IN_PLACE,)))
    assert dialog.summary_label.text() == (
        "Move 0 file(s) into /library, then auto-tag 1 (existing tags are replaced)?"
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [(QDialog.DialogCode.Accepted, True), (QDialog.DialogCode.Rejected, False)],
)
def test_confirm_repack_returns_dialog_answer(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, code: QDialog.DialogCode, expected: bool
):
    def answer(dialog: RepackDialog) -> QDialog.DialogCode:
        return code

    monkeypatch.setattr(RepackDialog, "exec", answer)
    parent = QWidget()
    qtbot.addWidget(parent)
    assert confirm_repack(parent, RepackPlan(RelocationPlan((MOVE,)), ()), ROOT) is expected
