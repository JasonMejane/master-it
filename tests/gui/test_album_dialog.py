import pytest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QWidget
from pytestqt.qtbot import QtBot

from masterit.gui.album_dialog import AlbumDialog, ask_album
from masterit.library.library_layout import AlbumTarget

JAZZ = AlbumTarget("Queen", "Jazz")


def make_dialog(qtbot: QtBot, suggestion: AlbumTarget) -> AlbumDialog:
    dialog = AlbumDialog(suggestion)
    qtbot.addWidget(dialog)
    return dialog


def get_ok_button(dialog: AlbumDialog) -> QWidget:
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)


def test_dialog_is_prefilled_with_suggestion(qtbot: QtBot):
    dialog = make_dialog(qtbot, JAZZ)
    assert dialog.artist_edit.text() == "Queen"
    assert dialog.album_edit.text() == "Jazz"
    assert get_ok_button(dialog).isEnabled()
    assert dialog.problem_label.text() == ""


def test_ok_needs_usable_artist_and_album(qtbot: QtBot):
    dialog = make_dialog(qtbot, AlbumTarget("", ""))
    assert not get_ok_button(dialog).isEnabled()
    dialog.artist_edit.setText("Queen")
    assert not get_ok_button(dialog).isEnabled()
    dialog.album_edit.setText("...")
    assert not get_ok_button(dialog).isEnabled()
    dialog.album_edit.setText("Jazz")
    assert get_ok_button(dialog).isEnabled()


def test_artist_with_separator_shows_a_hint(qtbot: QtBot):
    dialog = make_dialog(qtbot, AlbumTarget("A - B", "Jazz"))
    assert not get_ok_button(dialog).isEnabled()
    assert dialog.problem_label.text() == ('The artist cannot contain " - ", "\u2013" or "\u2014".')


def test_target_is_the_entered_text_trimmed(qtbot: QtBot):
    dialog = make_dialog(qtbot, AlbumTarget("", ""))
    dialog.artist_edit.setText(" Queen ")
    dialog.album_edit.setText(" Jazz")
    assert dialog.target == JAZZ


@pytest.mark.parametrize(
    ("code", "expected"),
    [(QDialog.DialogCode.Accepted, JAZZ), (QDialog.DialogCode.Rejected, None)],
)
def test_ask_album_returns_target_only_when_accepted(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    code: QDialog.DialogCode,
    expected: AlbumTarget | None,
):
    def answer(dialog: AlbumDialog) -> QDialog.DialogCode:
        return code

    monkeypatch.setattr(AlbumDialog, "exec", answer)
    parent = QWidget()
    qtbot.addWidget(parent)
    assert ask_album(parent, JAZZ) == expected
