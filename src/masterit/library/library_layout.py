import re
from collections.abc import Callable
from dataclasses import dataclass
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
# Leaves room for the album or title after "<Artist> - " when the artist is very long.
MAX_ARTIST_STEM_BYTES = 120

type TagReader = Callable[[Path], Tags]


def make_safe_name(text: str) -> str:
    # Windows refuses these characters, reserved device names, and trailing dots or spaces.
    replaced = FORBIDDEN_CHARACTERS.sub("-", text.strip().replace("?", "_"))
    return avoid_reserved_name(trim_name(replaced))


def trim_name(name: str) -> str:
    return name.lstrip(". ").rstrip(". ")


def avoid_reserved_name(name: str) -> str:
    device = name.split(".")[0].strip().upper()
    return f"{name}_" if device in RESERVED_NAMES else name


def fit_bytes(name: str, max_bytes: int) -> str:
    fitted = name.encode()[:max_bytes].decode(errors="ignore")
    return trim_name(fitted)


@dataclass(frozen=True)
class AlbumTarget:
    artist: str
    album: str


def make_folder_artist(artist: str) -> str:
    return fit_bytes(make_safe_name(artist), MAX_ARTIST_STEM_BYTES)


def make_album_folder(root: Path, target: AlbumTarget) -> Path:
    artist = make_folder_artist(target.artist)
    album_folder = fit_bytes(f"{artist} - {make_safe_name(target.album)}", MAX_NAME_BYTES)
    return root / artist / album_folder


def make_album_destination(
    root: Path, target: AlbumTarget, read_tags: TagReader
) -> DestinationMaker:
    folder = make_album_folder(root, target)

    def make_destination(source: Path) -> Destination:
        title = make_safe_name(read_tags(source).get(TagField.TITLE, ""))
        if not title:
            return Destination(source.parent, source.name, RelocationProblem.MISSING_TITLE)
        stem_bytes = MAX_NAME_BYTES - len(source.suffix.encode())
        stem = fit_bytes(f"{folder.parent.name} - {title}", stem_bytes)
        return Destination(folder, f"{stem}{source.suffix}")

    return make_destination
