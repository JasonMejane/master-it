import base64
import struct
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, PictureType
from mutagen.mp4 import MP4Tags
from mutagen.oggflac import OggFLACVComment
from mutagen.oggopus import OggOpusVComment
from mutagen.oggvorbis import OggVCommentDict

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
