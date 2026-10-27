from typing import Any, cast

from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4Tags
from mutagen.id3 import COMM

# COMM frames with another description hold player data (e.g. iTunNORM), not the comment.
COMMENT_PREFIXES = ("COMM::", "COMM:ID3v1 Comment:")
FFMPEG_COMMENT_KEY = "TXXX:comment"
UTF8 = 3


def register_easy_keys() -> None:
    easy_id3 = cast(Any, EasyID3)
    easy_id3.RegisterKey("comment", get_id3_comment, set_id3_comment, delete_id3_comment)
    for key in ("description", "synopsis", "purl"):
        easy_id3.RegisterTXXXKey(key, key)
    cast(Any, EasyMP4Tags).RegisterTextKey("synopsis", "ldes")


def get_comment_keys(id3: Any) -> list[str]:
    keys: list[str] = list(id3.keys())
    return [key for key in keys if key.startswith(COMMENT_PREFIXES) or key == FFMPEG_COMMENT_KEY]


def get_id3_comment(id3: Any, key: str) -> list[str]:
    found: list[str] = [text for key in get_comment_keys(id3) for text in id3[key].text]
    texts = list(dict.fromkeys(found))
    if not texts:
        raise KeyError(key)
    return texts


def set_id3_comment(id3: Any, key: str, value: list[str]) -> None:
    delete_id3_comment(id3, key)
    id3.add(COMM(encoding=UTF8, lang="eng", desc="", text=value))


def delete_id3_comment(id3: Any, key: str) -> None:
    for frame_key in get_comment_keys(id3):
        del id3[frame_key]
