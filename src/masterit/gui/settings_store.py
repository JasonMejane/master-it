from pathlib import Path
from typing import cast

from PySide6.QtCore import QByteArray, QSettings

from masterit.download.settings import AUDIO_QUALITIES, AudioCodec, DownloadSettings


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

    def load_library_root(self) -> Path | None:
        root = self._read("library/root", "")
        return Path(root) if root else None

    def save_library_root(self, root: Path) -> None:
        self._settings.setValue("library/root", str(root))

    def load_window_geometry(self) -> QByteArray | None:
        geometry = self._settings.value("window/geometry")
        return geometry if isinstance(geometry, QByteArray) else None

    def save_window_geometry(self, geometry: QByteArray) -> None:
        self._settings.setValue("window/geometry", geometry)
        # Saved on close, possibly right before a forced exit that skips the deferred write.
        self._settings.sync()

    def _read(self, key: str, default: str) -> str:
        value = self._settings.value(key, default)
        if isinstance(value, list):
            # QSettings splits unquoted INI values on commas.
            return ",".join(str(part) for part in cast(list[object], value))
        return str(value)
