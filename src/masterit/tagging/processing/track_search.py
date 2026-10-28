from dataclasses import replace
from pathlib import Path

from masterit.tagging.metadata.track_matching import (
    has_note_after_name,
    is_same_album,
    is_same_artist,
    is_same_name,
)
from masterit.tagging.metadata.track_metadata import fill_missing_fields, get_first_filled
from masterit.tagging.metadata.types import ExistingTags, TrackInfo, TrackMetadata, TrackSearch
from masterit.tagging.paths.library_path import infer_library_folder_terms, parse_library_path
from masterit.tagging.paths.readable_path import make_readable_path
from masterit.tagging.paths.terms import LibraryPathTerms
from masterit.tagging.paths.track_name import parse_track_filename


def build_track_search(path: Path, source_root: Path, existing: TrackInfo) -> TrackSearch:
    readable = make_readable_path(path)
    file_terms = parse_library_path(readable) or parse_track_filename(readable.name)
    folder_terms = infer_library_folder_terms(readable, make_readable_path(source_root))
    return TrackSearch(
        get_first_filled(existing.title, file_terms.title),
        get_first_filled(existing.artist, file_terms.artist, folder_terms.artist),
        get_first_filled(existing.album, folder_terms.album),
    )


# Spelled differently ("AC DC", "AC/DC"), both would run the same rate-limited searches.
def is_same_song_search(first: TrackSearch, second: TrackSearch) -> bool:
    return (
        is_same_name(first.title, second.title)
        and is_same_artist(first.artist, second.artist)
        and is_same_album(first.album, second.album)
        and is_same_album(second.album, first.album)
    )


def get_new_path_search(
    path_terms: LibraryPathTerms | None, tag_search: TrackSearch
) -> TrackSearch | None:
    if path_terms is None:
        return None
    path_search = TrackSearch(path_terms.title, path_terms.artist, path_terms.album)
    return None if is_same_song_search(path_search, tag_search) else path_search


# Tags naming another version ("Song (Live)") must not get its details.
def is_other_version(tagged_title: str, found_title: str) -> bool:
    return has_note_after_name(tagged_title, found_title) and not is_same_name(
        tagged_title, found_title
    )


def forget_identity(existing: ExistingTags) -> ExistingTags:
    return replace(existing, info=replace(existing.info, title="", artist=""))


def keep_existing_info(metadata: TrackMetadata, existing: ExistingTags) -> TrackMetadata:
    return replace(metadata, info=fill_missing_fields(existing.info, metadata.info))


# Best-ofs and compilations keep the album of their folder.
def pin_folder_album(existing: ExistingTags, path_terms: LibraryPathTerms | None) -> ExistingTags:
    album = get_first_filled(existing.info.album, path_terms.album if path_terms else "")
    return replace(existing, info=replace(existing.info, album=album))


def has_title_and_artist(metadata: TrackMetadata) -> bool:
    return bool(metadata.info.title.strip() and metadata.info.artist.strip())
