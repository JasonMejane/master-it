from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from masterit.library.destinations import Destination
from masterit.library.library_layout import (
    AlbumTarget,
    TagReader,
    make_album_destination,
    make_folder_artist,
    make_safe_name,
)
from masterit.library.relocation import RelocationOutcome, RelocationPlan, make_relocation_plan
from masterit.tagging.paths.track_name import split_label
from masterit.tags.fields import TagField, Tags

MISSING_NAMES = "Enter an artist and an album."
# The tagger splits album folders at the first of these, so it would cut the artist.
ARTIST_SEPARATORS = 'The artist cannot contain " - ", "\u2013" or "\u2014".'


@dataclass(frozen=True)
class RepackPlan:
    moves: RelocationPlan
    # Already where the layout wants them: tagged without moving.
    in_place: tuple[Path, ...]

    def get_files_to_tag(self, outcomes: Iterable[RelocationOutcome]) -> list[Path]:
        moved = [outcome.target for outcome in outcomes if outcome.succeeded]
        return [*self.in_place, *moved]


def make_repack_plan(
    paths: list[Path], root: Path, target: AlbumTarget, read_tags: TagReader
) -> RepackPlan:
    make_destination = make_album_destination(root, target, read_tags)
    in_place = tuple(path for path in paths if is_in_place(path, make_destination(path)))
    return RepackPlan(make_relocation_plan(paths, make_destination), in_place)


def is_in_place(path: Path, destination: Destination) -> bool:
    return destination.problem is None and destination.path == path


def make_suggested_album(paths: list[Path], read_tags: TagReader) -> AlbumTarget:
    tags = [read_tags(path) for path in paths]
    artists = [get_album_artist(file_tags) for file_tags in tags]
    albums = [file_tags.get(TagField.ALBUM, "") for file_tags in tags]
    return AlbumTarget(find_shared_value(artists), find_shared_value(albums))


def get_album_artist(tags: Tags) -> str:
    return tags.get(TagField.ALBUM_ARTIST, "").strip() or tags.get(TagField.ARTIST, "")


def find_shared_value(values: list[str]) -> str:
    unique = {value.strip() for value in values}
    return unique.pop() if len(unique) == 1 else ""


def find_album_problem(target: AlbumTarget) -> str:
    artist = make_folder_artist(target.artist)
    if not (artist and make_safe_name(target.album)):
        return MISSING_NAMES
    return "" if is_whole_label_artist(artist) else ARTIST_SEPARATORS


def is_whole_label_artist(artist: str) -> bool:
    return split_label(f"{artist} - album")[0] == artist
