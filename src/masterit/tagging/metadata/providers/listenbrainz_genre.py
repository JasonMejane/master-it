import re

from masterit.tagging.web.json_fields import read_int, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject

# The most specific level with a genre wins: an album's genre can be wrong for one track.
TAG_LEVELS = ("recording", "release_group", "artist")
WORD_START = re.compile(r"(^|[\s\-&/])([^\W\d_])")
WORD = re.compile(r"[^\W_]+")
ACRONYMS = frozenset({"uk", "us", "edm", "idm", "ebm", "dj", "mc"})


def get_genre_tags(tags: list[JsonObject]) -> list[JsonObject]:
    return [tag for tag in tags if read_text(tag, "genre_mbid") and read_text(tag, "tag")]


def get_most_specific_genres(tags: JsonObject) -> list[JsonObject]:
    levels = (get_genre_tags(read_objects(tags, level)) for level in TAG_LEVELS)
    no_genres: list[JsonObject] = []
    return next((genres for genres in levels if genres), no_genres)


def get_votes(tag: JsonObject) -> int:
    return read_int(tag, "count") or 0


def capitalize_acronym(word: re.Match[str]) -> str:
    text = word.group()
    return text.upper() if text.lower() in ACRONYMS else text


def make_title_case(text: str) -> str:
    capitalized = WORD_START.sub(lambda match: match.group(1) + match.group(2).upper(), text)
    return WORD.sub(capitalize_acronym, capitalized)


def pick_genre(tags: JsonObject) -> str | None:
    genres = get_most_specific_genres(tags)
    if not genres:
        return None
    return make_title_case(read_text(max(genres, key=get_votes), "tag") or "")
