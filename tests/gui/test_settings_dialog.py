import pytest
from PySide6.QtWidgets import QDialog, QLineEdit
from pytestqt.qtbot import QtBot

from masterit.gui import settings_dialog
from masterit.gui.settings_dialog import SettingsDialog, edit_tagger_keys
from masterit.tagging.native_setup import TaggerKeys

KEYS = TaggerKeys("Agent", "token", "key", "secret", "lastfm", "youtube")


def test_shows_each_key_and_hides_secrets(qtbot: QtBot):
    dialog = SettingsDialog(KEYS)
    qtbot.addWidget(dialog)
    assert dialog.fields["musicbrainz_user_agent"].text() == "Agent"
    assert dialog.fields["musicbrainz_user_agent"].echoMode() == QLineEdit.EchoMode.Normal
    assert dialog.fields["discogs_secret"].echoMode() == QLineEdit.EchoMode.Password
    assert dialog.get_keys() == KEYS


def test_returns_the_edited_keys_once_accepted(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    def accept_with_new_token(dialog: SettingsDialog) -> int:
        qtbot.addWidget(dialog)
        dialog.fields["listenbrainz_token"].setText(" new ")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(settings_dialog.SettingsDialog, "exec", accept_with_new_token)
    edited = edit_tagger_keys(None, KEYS)
    assert edited == TaggerKeys("Agent", " new ", "key", "secret", "lastfm", "youtube")


def test_returns_nothing_once_cancelled(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    def cancel(dialog: SettingsDialog) -> int:
        qtbot.addWidget(dialog)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(settings_dialog.SettingsDialog, "exec", cancel)
    assert edit_tagger_keys(None, KEYS) is None
