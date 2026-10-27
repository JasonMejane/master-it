from pathlib import Path
from typing import Protocol, cast

import mutagen
from mutagen.easymp4 import EasyMP4
from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from masterit.tags.fields import TagField, Tags

# Formats whose tags use the shared easy keys; others (e.g. WAV's raw ID3) are refused.
SUPPORTED_AUDIO = (EasyMP3, EasyMP4, FLAC, OggFLAC, OggOpus, OggVorbis)
VALUE_SEPARATOR = "; "


class TagError(Exception):
    pass


class TagStore(Protocol):
    def read(self, path: Path) -> Tags: ...

    def write(self, path: Path, changes: Tags) -> None: ...


class MutagenTagStore:
    def read(self, path: Path) -> Tags:
        audio = open_audio(path)
        values = {field: audio.get(field.value) for field in TagField}
        return {field: VALUE_SEPARATOR.join(value) for field, value in values.items() if value}

    def write(self, path: Path, changes: Tags) -> None:
        audio = open_audio(path)
        try:
            for field, value in changes.items():
                set_tag(audio, field, value)
            audio.save()
        except (mutagen.MutagenError, OSError, ValueError) as error:
            raise TagError(str(error)) from error


class EasyAudio(Protocol):
    tags: object | None

    def add_tags(self) -> None: ...

    def get(self, key: str) -> list[str] | None: ...

    def __setitem__(self, key: str, value: list[str]) -> None: ...

    def pop(self, key: str, default: None) -> object: ...

    def save(self) -> None: ...


def open_audio(path: Path) -> EasyAudio:
    audio = load_audio(path)
    if audio.tags is None:
        audio.add_tags()
    return audio


def load_audio(path: Path) -> EasyAudio:
    try:
        audio = mutagen.File(path, easy=True)  # pyright: ignore[reportUnknownMemberType]
    except (mutagen.MutagenError, OSError) as error:
        raise TagError(str(error)) from error
    if not isinstance(audio, SUPPORTED_AUDIO):
        raise TagError(f"Tags not supported for {path.name}")
    return cast(EasyAudio, audio)


def set_tag(audio: EasyAudio, field: TagField, value: str) -> None:
    if value:
        audio[field.value] = [value]
    else:
        audio.pop(field.value, None)
