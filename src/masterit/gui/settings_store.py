from dataclasses import fields
from pathlib import Path
from typing import cast
from uuid import uuid4

from PySide6.QtCore import QByteArray, QSettings

from masterit.download.settings import AUDIO_QUALITIES, AudioCodec, DownloadSettings
from masterit.tagging.native_setup import TaggerKeys, get_default_user_agent

KEY_NAMES = tuple(field.name for field in fields(TaggerKeys))


def parse_codec(value: str) -> AudioCodec:
    return AudioCodec(value) if value in AudioCodec else AudioCodec.MP3


def parse_quality(value: str, default: str) -> str:
    return value if value in AUDIO_QUALITIES else default


class SettingsStore:
    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def load_download_settings(self, default_output_dir: Path) -> DownloadSettings:
        defaults = DownloadSettings(default_output_dir)
        return DownloadSettings(
            output_dir=Path(self._read("download/output_dir", str(defaults.output_dir))),
            codec=parse_codec(self._read("download/codec", defaults.codec)),
            quality=parse_quality(self._read("download/quality", ""), defaults.quality),
        )

    def save_download_settings(self, settings: DownloadSettings) -> None:
        self._settings.setValue("download/output_dir", str(settings.output_dir))
        self._settings.setValue("download/codec", str(settings.codec))
        self._settings.setValue("download/quality", settings.quality)

    def load_library_root(self, default_root: Path) -> Path:
        return Path(self._read("library/root", str(default_root)))

    def save_library_root(self, root: Path) -> None:
        self._settings.setValue("library/root", str(root))

    def load_tagger_keys(self) -> TaggerKeys:
        defaults = TaggerKeys(self._get_default_user_agent())
        values = {
            name: self._read(f"tagging/{name}", getattr(defaults, name)) for name in KEY_NAMES
        }
        return TaggerKeys(**values)

    def save_tagger_keys(self, keys: TaggerKeys) -> None:
        for name in KEY_NAMES:
            self._settings.setValue(f"tagging/{name}", getattr(keys, name))
        # Left unsaved, the default User-Agent keeps following the app version.
        if keys.musicbrainz_user_agent.strip() == self._get_default_user_agent():
            self._settings.remove("tagging/musicbrainz_user_agent")

    def load_window_geometry(self) -> QByteArray | None:
        geometry = self._settings.value("window/geometry")
        return geometry if isinstance(geometry, QByteArray) else None

    def save_window_geometry(self, geometry: QByteArray) -> None:
        self._settings.setValue("window/geometry", geometry)
        # Saved on close, possibly right before a forced exit that skips the deferred write.
        self._settings.sync()

    def load_library_layout(self) -> QByteArray | None:
        layout = self._settings.value("window/library_layout")
        return layout if isinstance(layout, QByteArray) else None

    def save_library_layout(self, layout: QByteArray) -> None:
        self._settings.setValue("window/library_layout", layout)

    def _get_default_user_agent(self) -> str:
        client_id = self._read("tagging/client_id", "")
        if not client_id:
            client_id = str(uuid4())
            self._settings.setValue("tagging/client_id", client_id)
        return get_default_user_agent(client_id)

    def _read(self, key: str, default: str) -> str:
        value = self._settings.value(key, default)
        if isinstance(value, list):
            # QSettings splits unquoted INI values on commas.
            return ",".join(str(part) for part in cast(list[object], value))
        return str(value)
