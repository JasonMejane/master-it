from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from masterit.tagging.metadata.album_tracklist import TrackNames, find_tracklist_entry
from masterit.tagging.metadata.track_metadata import get_first_filled, make_optional_text
from masterit.tagging.metadata.types import (
    AlbumData,
    AlbumTrackEntry,
    ExistingTags,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
)
from masterit.tagging.paths.library_path import parse_library_path
from masterit.tagging.paths.readable_path import make_readable_path
from masterit.tagging.paths.terms import AlbumTrack
from masterit.tagging.paths.track_name import parse_track_filename
from masterit.tagging.processing.track_write import TagFiles, TrackOutcome, write_found_metadata

# Looked up for the first track that needs it, so a run stopped before costs nothing.
type AlbumSupply = Callable[[], AlbumData]


def get_file_title(path: Path) -> str:
    readable = make_readable_path(path)
    terms = parse_library_path(readable)
    return terms.title if terms else parse_track_filename(readable.name).title


def get_position_extras(entry: AlbumTrackEntry | None, disc: int | None) -> TrackExtras:
    if entry is None:
        return TrackExtras(disc_number=disc)
    return TrackExtras(
        track_number=entry.track_number,
        track_count=entry.track_count,
        disc_number=entry.disc_number,
        disc_count=entry.disc_count,
    )


# Every track takes the album's fields; only its title and place are its own.
def build_album_track(album: AlbumData, track: AlbumTrack, stored: ExistingTags) -> TrackMetadata:
    file_title = get_file_title(track.path)
    title = get_first_filled(stored.info.title, file_title)
    entry = find_tracklist_entry(album.tracks, TrackNames([title, file_title], track.disc))
    extras = replace(
        get_position_extras(entry, track.disc),
        genre=make_optional_text(album.genre),
        album_artist=make_optional_text(album.artist),
    )
    info = TrackInfo(entry.title if entry else title, album.artist, album.album, album.year)
    return TrackMetadata(info, extras, album.cover)


class AlbumTrackTagger:
    def __init__(self, files: TagFiles) -> None:
        self._files = files

    def tag(self, track: AlbumTrack, get_album: AlbumSupply) -> TrackOutcome:
        stored = self._files.read(track.path)
        found = build_album_track(get_album(), track, stored)
        return write_found_metadata(self._files, track.path, stored, found)
