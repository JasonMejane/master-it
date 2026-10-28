from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from masterit.tagging.events import AutoTagStatus
from masterit.tagging.metadata.types import ExistingTags, TrackInfo, TrackMetadata, TrackSearch
from masterit.tagging.paths.album_plan import get_file_root
from masterit.tagging.paths.library_path import parse_library_path
from masterit.tagging.paths.readable_path import make_readable_path
from masterit.tagging.paths.terms import LibraryPathTerms
from masterit.tagging.processing.track_search import (
    build_track_search,
    forget_identity,
    get_new_path_search,
    has_title_and_artist,
    is_other_version,
    keep_existing_info,
    pin_folder_album,
)
from masterit.tagging.processing.track_write import TagFiles, TrackOutcome, write_found_metadata
from masterit.tagging.processing.write_policy import get_searched_tags


class TrackFinder(Protocol):
    def find(
        self, search: TrackSearch, existing: ExistingTags, replace_cover: bool = False
    ) -> TrackMetadata | None: ...


# hints: the stored tags, which name the song even though overwriting searches from none.
@dataclass(frozen=True)
class TrackLookup:
    path: Path
    existing: ExistingTags
    hints: TrackInfo


def get_unwritable_reason(found: TrackMetadata | None) -> str:
    if found is None:
        return "not found"
    return "" if has_title_and_artist(found) else "no title or artist found"


class SingleTrackTagger:
    def __init__(self, finder: TrackFinder, files: TagFiles) -> None:
        self._finder = finder
        self._files = files

    def tag(self, path: Path) -> TrackOutcome:
        stored = self._files.read(path)
        found = self._find(TrackLookup(path, get_searched_tags(stored), stored.info))
        reason = get_unwritable_reason(found)
        if found is None or reason:
            return TrackOutcome(AutoTagStatus.SKIPPED, reason)
        return write_found_metadata(self._files, path, stored, found)

    def _find(self, lookup: TrackLookup) -> TrackMetadata | None:
        path_terms = parse_library_path(make_readable_path(lookup.path))
        pinned = TrackLookup(
            lookup.path, pin_folder_album(lookup.existing, path_terms), lookup.hints
        )
        tag_search = build_track_search(lookup.path, get_file_root(lookup.path), lookup.hints)
        found = self._find_from_path(pinned, path_terms, tag_search)
        return found if found is not None else self._search(tag_search, pinned.existing)

    # The path names the song better than tags do; its terms must lead the search.
    def _find_from_path(
        self, lookup: TrackLookup, path_terms: LibraryPathTerms | None, tag_search: TrackSearch
    ) -> TrackMetadata | None:
        search = get_new_path_search(path_terms, tag_search)
        if search is None:
            return None
        found = self._search(search, forget_identity(lookup.existing))
        if found is None or is_other_version(lookup.hints.title, found.info.title):
            return None
        return keep_existing_info(found, lookup.existing)

    def _search(self, search: TrackSearch, existing: ExistingTags) -> TrackMetadata | None:
        return self._finder.find(search, existing, replace_cover=True)
