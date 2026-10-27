import contextlib
import re
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import mutagen
from mutagen.easymp4 import EasyMP4
from mutagen.mp3 import EasyMP3

from masterit.tagging.metadata.track_metadata import (
    extract_year,
    make_optional_count,
    make_optional_text,
)
from masterit.tagging.metadata.types import (
    ExistingTags,
    ExtraField,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
)
from masterit.tags.cover_store import MutagenCoverStore
from masterit.tags.tag_store import EasyAudio, TagError, open_audio

LEADING_NUMBER = re.compile(r"\s*([0-9]+)")
TEXT_KEYS = {"title": "title", "album": "album", "year": "date"}
# Each extra is written to its first key; the others are older spellings it replaces.
EXTRA_TEXT_KEYS: dict[ExtraField, tuple[str, ...]] = {
    "genre": ("genre",),
    "album_artist": ("albumartist", "album artist"),
}


# Fields are cleared before the found ones are written, as a group moves with its count.
@dataclass(frozen=True)
class TagWrite:
    metadata: TrackMetadata
    cleared_extras: tuple[ExtraField, ...] = ()


@dataclass(frozen=True)
class PositionGroup:
    number_field: ExtraField
    count_field: ExtraField
    number_key: str
    total_keys: tuple[str, ...]


POSITION_GROUPS = (
    PositionGroup("track_number", "track_count", "tracknumber", ("tracktotal", "totaltracks")),
    PositionGroup("disc_number", "disc_count", "discnumber", ("disctotal", "totaldiscs")),
)

type Position = tuple[int | None, int | None]


def read_first(audio: EasyAudio, key: str) -> str:
    values = audio.get(key) or [""]
    return str(values[0])


# Like JavaScript's parseInt, "3abc" reads as 3.
def parse_count(text: str) -> int | None:
    match = LEADING_NUMBER.match(text)
    return make_optional_count(int(match.group(1))) if match else None


def parse_position(text: str) -> Position:
    number, _, count = text.partition("/")
    return (parse_count(number), parse_count(count))


# ID3 and MP4 keep "number/count" in one field; like TagLib, a new number keeps the count.
# A count without a number stays on MP4 as "0/count" (TagLib) but not on ID3 (node-id3).
class SlashedPositions:
    def __init__(self, keeps_lone_count: bool) -> None:
        self._keeps_lone_count = keeps_lone_count

    def read(self, audio: EasyAudio, group: PositionGroup) -> Position:
        return parse_position(read_first(audio, group.number_key))

    def clear(
        self, audio: EasyAudio, group: PositionGroup, cleared: tuple[ExtraField, ...]
    ) -> None:
        if {group.number_field, group.count_field} & set(cleared):
            audio.pop(group.number_key, None)

    def write(self, audio: EasyAudio, group: PositionGroup, position: Position) -> None:
        number, count = position
        if number is None:
            self._write_lone_count(audio, group, count)
            return
        kept_count = count if count is not None else self.read(audio, group)[1]
        audio[group.number_key] = [f"{number}/{kept_count}" if kept_count else str(number)]

    def _write_lone_count(self, audio: EasyAudio, group: PositionGroup, count: int | None) -> None:
        if self._keeps_lone_count and count is not None:
            audio[group.number_key] = [f"0/{count}"]


# Vorbis comments keep the count in a key of its own, which TagLib reads before "number/count".
class VorbisPositions:
    def read(self, audio: EasyAudio, group: PositionGroup) -> Position:
        number, slashed_count = parse_position(read_first(audio, group.number_key))
        totals = (parse_count(read_first(audio, key)) for key in group.total_keys)
        return (number, next((total for total in totals if total), slashed_count))

    def clear(
        self, audio: EasyAudio, group: PositionGroup, cleared: tuple[ExtraField, ...]
    ) -> None:
        number = self.read(audio, group)[0]
        if group.count_field in cleared:
            remove_keys(audio, group.total_keys)
            self._write_number(audio, group, number)
        if group.number_field in cleared:
            audio.pop(group.number_key, None)

    def write(self, audio: EasyAudio, group: PositionGroup, position: Position) -> None:
        number, count = position
        kept_count = count if count is not None or number is None else self.read(audio, group)[1]
        self._write_number(audio, group, number)
        self._write_count(audio, group, kept_count)

    def _write_number(self, audio: EasyAudio, group: PositionGroup, number: int | None) -> None:
        if number is not None:
            audio[group.number_key] = [str(number)]

    def _write_count(self, audio: EasyAudio, group: PositionGroup, count: int | None) -> None:
        if count is not None:
            remove_keys(audio, group.total_keys)
            audio[group.total_keys[0]] = [str(count)]


class PositionStyle(Protocol):
    def read(self, audio: EasyAudio, group: PositionGroup) -> Position: ...

    def clear(
        self, audio: EasyAudio, group: PositionGroup, cleared: tuple[ExtraField, ...]
    ) -> None: ...

    def write(self, audio: EasyAudio, group: PositionGroup, position: Position) -> None: ...


def remove_keys(audio: EasyAudio, keys: tuple[str, ...]) -> None:
    for key in keys:
        audio.pop(key, None)


def get_position_style(audio: EasyAudio) -> PositionStyle:
    if isinstance(audio, EasyMP3 | EasyMP4):
        return SlashedPositions(keeps_lone_count=isinstance(audio, EasyMP4))
    return VorbisPositions()


def read_info(audio: EasyAudio) -> TrackInfo:
    artists = (artist.strip() for artist in audio.get("artist") or [])
    return TrackInfo(
        read_first(audio, "title").strip(),
        next((artist for artist in artists if artist), ""),
        read_first(audio, "album").strip(),
        extract_year(read_first(audio, "date")),
    )


def read_extra_text(audio: EasyAudio, field: ExtraField) -> str | None:
    texts = (make_optional_text(read_first(audio, key)) for key in EXTRA_TEXT_KEYS[field])
    return next((text for text in texts if text), None)


def read_extras(audio: EasyAudio, style: PositionStyle) -> TrackExtras:
    track, disc = (style.read(audio, group) for group in POSITION_GROUPS)
    return TrackExtras(
        read_extra_text(audio, "genre"), read_extra_text(audio, "album_artist"), *track, *disc
    )


def write_info(audio: EasyAudio, info: TrackInfo) -> None:
    filled = {key: getattr(info, field) for field, key in TEXT_KEYS.items()}
    for key, value in filled.items():
        if value.strip():
            audio[key] = [value]
    write_lead_artist(audio, info.artist)


# Only the first filled artist is read, so it alone is replaced.
def write_lead_artist(audio: EasyAudio, artist: str) -> None:
    if not artist.strip():
        return
    others = [other for other in audio.get("artist") or [] if other.strip()]
    audio["artist"] = [artist, *others[1:]]


def clear_extras(audio: EasyAudio, style: PositionStyle, cleared: tuple[ExtraField, ...]) -> None:
    for field in cleared:
        remove_keys(audio, EXTRA_TEXT_KEYS.get(field, ()))
    for group in POSITION_GROUPS:
        style.clear(audio, group, cleared)


def write_extras(audio: EasyAudio, style: PositionStyle, extras: TrackExtras) -> None:
    known = {keys: getattr(extras, field) for field, keys in EXTRA_TEXT_KEYS.items()}
    for keys, value in known.items():
        if value is not None:
            remove_keys(audio, keys)
            audio[keys[0]] = [value]
    write_positions(audio, style, extras)


def write_positions(audio: EasyAudio, style: PositionStyle, extras: TrackExtras) -> None:
    for group in POSITION_GROUPS:
        position = (getattr(extras, group.number_field), getattr(extras, group.count_field))
        style.write(audio, group, position)


class CoverFiles(Protocol):
    def read(self, path: Path) -> bytes | None: ...

    def write(self, path: Path, data: bytes) -> None: ...


class TrackTagStore:
    def __init__(self, covers: CoverFiles | None = None) -> None:
        self._covers = covers or MutagenCoverStore()

    def read(self, path: Path) -> ExistingTags:
        audio = open_audio(path)
        extras = read_extras(audio, get_position_style(audio))
        return ExistingTags(read_info(audio), extras, self._covers.read(path) is not None)

    def read_cover(self, path: Path) -> bytes | None:
        return self._covers.read(path)

    # Through a hidden copy, so a failed write leaves the file as it was.
    def write(self, path: Path, tag_write: TagWrite) -> None:
        target = path.resolve()
        temporary = target.with_name(f".{uuid.uuid4().hex}{target.suffix}")
        try:
            run_file_step(lambda: shutil.copyfile(target, temporary))
            self._write_copy(temporary, tag_write)
            run_file_step(lambda: replace_keeping_mode(temporary, target))
        finally:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)

    def _write_copy(self, temporary: Path, tag_write: TagWrite) -> None:
        metadata = tag_write.metadata
        write_tags(temporary, metadata, tag_write.cleared_extras)
        if metadata.cover_data is not None:
            self._covers.write(temporary, metadata.cover_data)


def run_file_step(step: Callable[[], object]) -> None:
    try:
        step()
    except OSError as error:
        raise TagError(str(error)) from error


def replace_keeping_mode(temporary: Path, target: Path) -> None:
    shutil.copymode(target, temporary)
    temporary.replace(target)


def write_tags(path: Path, metadata: TrackMetadata, cleared: tuple[ExtraField, ...]) -> None:
    audio = open_audio(path)
    style = get_position_style(audio)
    try:
        write_info(audio, metadata.info)
        clear_extras(audio, style, cleared)
        write_extras(audio, style, metadata.extras)
        audio.save()
    except (mutagen.MutagenError, OSError, ValueError) as error:
        raise TagError(str(error)) from error
