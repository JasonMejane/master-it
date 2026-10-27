from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

AUDIO_QUALITIES = ("128", "192", "256", "320")


class AudioCodec(StrEnum):
    MP3 = "mp3"
    OPUS = "opus"
    M4A = "m4a"
    FLAC = "flac"


@dataclass(frozen=True)
class DownloadSettings:
    output_dir: Path
    codec: AudioCodec = AudioCodec.MP3
    quality: str = "192"
