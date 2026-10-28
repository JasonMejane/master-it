from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from masterit.tagging.native_setup import TaggerKeys

FIELD_LABELS = {
    "musicbrainz_user_agent": "MusicBrainz User-Agent",
    "listenbrainz_token": "ListenBrainz token",
    "discogs_key": "Discogs consumer key",
    "discogs_secret": "Discogs consumer secret",
    "lastfm_api_key": "Last.fm API key",
    "youtube_api_key": "YouTube Data API key",
}
SECRET_FIELDS = frozenset(FIELD_LABELS) - {"musicbrainz_user_agent"}
HINT = "Deezer and iTunes need no key; each other service is used once its key is set."


class SettingsDialog(QDialog):
    def __init__(self, keys: TaggerKeys, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.fields = {name: self._make_field(name, getattr(keys, name)) for name in FIELD_LABELS}
        self._build_layout()

    def get_keys(self) -> TaggerKeys:
        return TaggerKeys(**{name: field.text() for name, field in self.fields.items()})

    def _make_field(self, name: str, value: str) -> QLineEdit:
        field = QLineEdit(value)
        if name in SECRET_FIELDS:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        return field

    def _build_layout(self) -> None:
        form = QFormLayout()
        for name, field in self.fields.items():
            form.addRow(FIELD_LABELS[name], field)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(HINT))
        layout.addLayout(form)
        layout.addWidget(buttons)


def edit_tagger_keys(parent: QWidget | None, keys: TaggerKeys) -> TaggerKeys | None:
    dialog = SettingsDialog(keys, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.get_keys()
