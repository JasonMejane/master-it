from collections import Counter
from dataclasses import dataclass

from masterit.tagging.metadata.track_matching import is_same_name
from masterit.tagging.metadata.types import AlbumTrackEntry


@dataclass(frozen=True)
class TrackPlace:
    title: str
    disc: int
    track: int
    artist: str = ""


# The titles a file goes by: its tag, its file name.
@dataclass(frozen=True)
class TrackNames:
    titles: list[str]
    disc: int | None


# Restarting numbers without discs ("CD1" and "CD2" headings) cannot be placed.
def has_shared_places(places: list[TrackPlace]) -> bool:
    return len({(place.disc, place.track) for place in places}) < len(places)


def build_tracklist(places: list[TrackPlace]) -> list[AlbumTrackEntry]:
    if has_shared_places(places):
        return []
    disc_count = max([0, *(place.disc for place in places)])
    disc_track_counts = Counter(place.disc for place in places)
    return [
        AlbumTrackEntry(
            place.title,
            place.track,
            disc_track_counts[place.disc],
            place.disc,
            disc_count,
            place.artist,
        )
        for place in places
    ]


def is_named(entry: AlbumTrackEntry, titles: list[str]) -> bool:
    return any(title and is_same_name(entry.title, title) for title in titles)


def find_tracklist_entry(
    entries: list[AlbumTrackEntry], names: TrackNames
) -> AlbumTrackEntry | None:
    named = [entry for entry in entries if is_named(entry, names.titles)]
    if names.disc is not None:
        named = [entry for entry in named if entry.disc_number == names.disc]
    return named[0] if named else None
