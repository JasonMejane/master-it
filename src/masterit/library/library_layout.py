import re
from collections.abc import Callable
from pathlib import Path

from masterit.library.destinations import Destination, DestinationMaker
from masterit.library.relocation_problems import RelocationProblem
from masterit.tags.fields import TagField, Tags

FORBIDDEN_CHARACTERS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"{port}{digit}" for port in ("COM", "LPT") for digit in "123456789"]
)
MAX_NAME_BYTES = 255
# Leaves room for the title in "<Artist> - <Title>" when the artist is very long.
MAX_ARTIST_STEM_BYTES = 120

type TagReader = Callable[[Path], Tags]


def make_safe_name(text: str) -> str:
    # Windows refuses these characters, reserved device names, and trailing dots or spaces.
    replaced = FORBIDDEN_CHARACTERS.sub("-", text.strip())
    return avoid_reserved_name(trim_name(replaced))


def trim_name(name: str) -> str:
    return name.lstrip(". ").rstrip(". ")


def avoid_reserved_name(name: str) -> str:
    device = name.split(".")[0].strip().upper()
    return f"{name}_" if device in RESERVED_NAMES else name


def fit_bytes(name: str, max_bytes: int) -> str:
    fitted = name.encode()[:max_bytes].decode(errors="ignore")
    return trim_name(fitted)


def make_layout_destination(root: Path, read_tags: TagReader) -> DestinationMaker:
    def make_destination(source: Path) -> Destination:
        tags = read_tags(source)
        artist = fit_bytes(make_safe_name(tags.get(TagField.ARTIST, "")), MAX_NAME_BYTES)
        title = make_safe_name(tags.get(TagField.TITLE, ""))
        if not (artist and title):
            return Destination(source.parent, source.name, RelocationProblem.MISSING_TAGS)
        stem_bytes = MAX_NAME_BYTES - len(source.suffix.encode())
        stem_artist = fit_bytes(artist, MAX_ARTIST_STEM_BYTES)
        stem = fit_bytes(f"{stem_artist} - {title}", stem_bytes)
        return Destination(root / artist, f"{stem}{source.suffix}")

    return make_destination
