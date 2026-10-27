import base64
import struct
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, PictureType
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover, MP4Tags
from mutagen.oggflac import OggFLAC, OggFLACVComment
from mutagen.oggopus import OggOpus, OggOpusVComment
from mutagen.oggvorbis import OggVCommentDict, OggVorbis

from masterit.tags.image_type import get_image_mime_type
from masterit.tags.tag_store import TagError

COVER_ERRORS = (mutagen.MutagenError, OSError, ValueError, struct.error)


class CoverStore(Protocol):
    def read(self, path: Path) -> bytes | None: ...


class EmbeddedPicture(Protocol):
    type: int
    data: bytes


class MutagenCoverStore:
    def read(self, path: Path) -> bytes | None:
        try:
            return read_cover(mutagen.File(path))  # pyright: ignore[reportUnknownMemberType]
        except COVER_ERRORS as error:
            raise TagError(str(error)) from error

    def write(self, path: Path, data: bytes) -> None:
        try:
            audio = mutagen.File(path)  # pyright: ignore[reportUnknownMemberType]
            write_cover(path, audio, data)
            cast(Any, audio).save()
        except COVER_ERRORS as error:
            raise TagError(str(error)) from error


def read_cover(audio: object) -> bytes | None:
    if isinstance(audio, FLAC):
        return pick_front_cover(cast(Any, audio).pictures)
    tags = getattr(audio, "tags", None)
    reader = next((read for kind, read in TAG_COVER_READERS if isinstance(tags, kind)), None)
    return None if reader is None else reader(tags)


def pick_front_cover(pictures: Sequence[EmbeddedPicture]) -> bytes | None:
    fronts = [picture for picture in pictures if picture.type == PictureType.COVER_FRONT]
    candidates = [*fronts, *pictures]
    return bytes(candidates[0].data) if candidates else None


def read_id3_cover(tags: Any) -> bytes | None:
    return pick_front_cover(tags.getall("APIC"))


def read_mp4_cover(tags: Any) -> bytes | None:
    covers: list[bytes] = tags.get("covr", [])
    return bytes(covers[0]) if covers else None


def read_ogg_cover(tags: Any) -> bytes | None:
    encoded: list[str] = tags.get("metadata_block_picture", [])
    pictures = (decode_ogg_picture(value) for value in encoded)
    return pick_front_cover([picture for picture in pictures if picture is not None])


def decode_ogg_picture(encoded: str) -> Picture | None:
    try:
        return Picture(base64.b64decode(encoded))
    except COVER_ERRORS:
        return None


TAG_COVER_READERS: tuple[tuple[type | tuple[type, ...], Callable[[Any], bytes | None]], ...] = (
    (ID3, read_id3_cover),
    (MP4Tags, read_mp4_cover),
    ((OggVCommentDict, OggOpusVComment, OggFLACVComment), read_ogg_cover),
)


def write_cover(path: Path, audio: object, data: bytes) -> None:
    writer = next((write for kind, write in COVER_WRITERS if isinstance(audio, kind)), None)
    if writer is None:
        raise TagError(f"Covers not supported for {path.name}")
    if cast(Any, audio).tags is None:
        cast(Any, audio).add_tags()
    writer(cast(Any, audio), data)


def make_front_picture(data: bytes) -> Picture:
    picture = Picture()
    picture.type = PictureType.COVER_FRONT
    picture.mime = get_image_mime_type(data)
    picture.desc = "Cover"
    picture.data = data
    return picture


def write_id3_cover(audio: Any, data: bytes) -> None:
    audio.tags.delall("APIC")
    audio.tags.add(
        APIC(
            encoding=3,
            mime=get_image_mime_type(data),
            type=PictureType.COVER_FRONT,
            desc="Cover",
            data=data,
        )
    )


def write_mp4_cover(audio: Any, data: bytes) -> None:
    is_png = get_image_mime_type(data) == "image/png"
    audio.tags["covr"] = [MP4Cover(data, MP4Cover.FORMAT_PNG if is_png else MP4Cover.FORMAT_JPEG)]


def write_flac_cover(audio: Any, data: bytes) -> None:
    audio.clear_pictures()
    audio.add_picture(make_front_picture(data))


def write_ogg_cover(audio: Any, data: bytes) -> None:
    encoded = base64.b64encode(make_front_picture(data).write()).decode("ascii")
    if "coverart" in audio.tags:
        del audio.tags["coverart"]
    audio.tags["metadata_block_picture"] = [encoded]


COVER_WRITERS: tuple[tuple[type | tuple[type, ...], Callable[[Any, bytes], None]], ...] = (
    (MP3, write_id3_cover),
    (MP4, write_mp4_cover),
    (FLAC, write_flac_cover),
    ((OggVorbis, OggOpus, OggFLAC), write_ogg_cover),
)
