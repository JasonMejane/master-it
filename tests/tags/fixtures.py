import base64
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import mutagen
from mutagen.flac import Picture
from mutagen.id3 import APIC, COMM, TXXX
from mutagen.mp4 import MP4Cover

FIXTURES = Path(__file__).parent.parent / "fixtures"
FORMATS = ("mp3", "flac", "opus", "ogg", "m4a")
FRONT_COVER = 3
BACK_COVER = 4


def copy_fixture(
    folder: Path, extension: str, name: str = "song", fixture: str = "silence"
) -> Path:
    target = folder / f"{name}.{extension}"
    shutil.copyfile(FIXTURES / f"{fixture}.{extension}", target)
    return target


def open_raw(path: Path) -> Any:
    return cast(Any, mutagen.File(path))  # pyright: ignore[reportUnknownMemberType]


def add_yt_dlp_comments(path: Path) -> None:
    """Writes the URL and description keys ffmpeg leaves after a yt-dlp download."""
    audio = open_raw(path)
    if audio.tags is None:
        audio.add_tags()
    YT_DLP_COMMENT_WRITERS[path.suffix](audio.tags)
    audio.save()


def add_id3_comments(tags: Any) -> None:
    for key in ("comment", "purl"):
        tags.add(TXXX(encoding=3, desc=key, text=["URL"]))
    for key in ("description", "synopsis"):
        tags.add(TXXX(encoding=3, desc=key, text=["DESC"]))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["Old"]))


def add_mp4_comments(tags: Any) -> None:
    tags["©cmt"] = ["URL"]
    tags["desc"] = ["DESC"]
    tags["ldes"] = ["DESC"]


def add_vorbis_comments(tags: Any) -> None:
    tags["description"] = ["URL", "DESC"]
    tags["synopsis"] = ["DESC"]
    tags["purl"] = ["URL"]


YT_DLP_COMMENT_WRITERS: dict[str, Callable[[Any], None]] = {
    ".mp3": add_id3_comments,
    ".m4a": add_mp4_comments,
    ".flac": add_vorbis_comments,
    ".ogg": add_vorbis_comments,
    ".opus": add_vorbis_comments,
}


def embed_cover(path: Path, data: bytes, picture_type: int = FRONT_COVER) -> None:
    audio = open_raw(path)
    if audio.tags is None:
        audio.add_tags()
    COVER_WRITERS[path.suffix](audio, data, picture_type)
    audio.save()


def make_picture(data: bytes, picture_type: int) -> Picture:
    picture = Picture()
    picture.type = picture_type
    picture.mime = "image/png"
    picture.data = data
    return picture


def embed_id3_cover(audio: Any, data: bytes, picture_type: int) -> None:
    audio.tags.add(
        APIC(encoding=3, mime="image/png", type=picture_type, desc=str(picture_type), data=data)
    )


def embed_mp4_cover(audio: Any, data: bytes, picture_type: int) -> None:
    covers = list(audio.tags.get("covr", []))
    audio.tags["covr"] = [*covers, MP4Cover(data, imageformat=MP4Cover.FORMAT_PNG)]


def embed_flac_cover(audio: Any, data: bytes, picture_type: int) -> None:
    audio.add_picture(make_picture(data, picture_type))


def embed_ogg_cover(audio: Any, data: bytes, picture_type: int) -> None:
    encoded = base64.b64encode(make_picture(data, picture_type).write()).decode("ascii")
    audio["metadata_block_picture"] = [*audio.get("metadata_block_picture", []), encoded]


COVER_WRITERS: dict[str, Callable[[Any, bytes, int], None]] = {
    ".mp3": embed_id3_cover,
    ".wav": embed_id3_cover,
    ".m4a": embed_mp4_cover,
    ".flac": embed_flac_cover,
    ".ogg": embed_ogg_cover,
    ".opus": embed_ogg_cover,
}
