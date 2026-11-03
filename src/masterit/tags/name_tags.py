import re
from collections.abc import Iterable
from pathlib import Path

from masterit.tags.fields import TagField, Tags

# Spaces around the dash keep hyphenated names such as "Jay-Z" whole.
NAME_SEPARATOR = re.compile(r"\s+[-\u2013\u2014]\s+")


def parse_name_tags(stem: str) -> Tags | None:
    parts = NAME_SEPARATOR.split(stem.strip(), maxsplit=1)
    if len(parts) != 2 or not all(parts):
        return None
    artist, title = (part.strip() for part in parts)
    return {TagField.ARTIST: artist, TagField.TITLE: title}


def make_name_tag_edits(paths: Iterable[Path]) -> dict[Path, Tags]:
    parsed = {path: parse_name_tags(path.stem) for path in paths}
    return {path: tags for path, tags in parsed.items() if tags is not None}
