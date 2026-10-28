from pathlib import Path

import pytest

from masterit.tagging.events import AutoTagStatus
from masterit.tagging.metadata.types import (
    ExistingTags,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.processing.single_track import SingleTrackTagger
from masterit.tagging.processing.track_write import TrackOutcome
from masterit.tags.tag_store import TagError

from .fakes import FakeTagFiles, FakeTrackFinder

LIBRARY = Path("/library")
LEVER = TrackMetadata(TrackInfo("Lever l'ancre", "Alfa Rococo", "", "2007"))


def make_tagger(path: Path, stored: TrackInfo, results: list[TrackMetadata | None]):
    files = FakeTagFiles({path: ExistingTags(stored)})
    finder = FakeTrackFinder(results)
    return SingleTrackTagger(finder, files), finder, files


def get_titles(finder: FakeTrackFinder) -> list[str]:
    return [search.title for search, _existing, _replace in finder.calls]


def test_skips_a_track_no_service_identifies():
    path = LIBRARY / "Unknown.mp3"
    tagger, finder, _files = make_tagger(path, TrackInfo(), [])
    assert tagger.tag(path) == TrackOutcome(AutoTagStatus.SKIPPED, "not found")
    assert len(finder.calls) == 1


def test_skips_a_match_without_title_and_artist():
    path = LIBRARY / "Untitled.mp3"
    tagger, _finder, files = make_tagger(
        path, TrackInfo(), [TrackMetadata(TrackInfo(album="Album only"))]
    )
    assert tagger.tag(path) == TrackOutcome(AutoTagStatus.SKIPPED, "no title or artist found")
    assert files.writes == []


def test_searches_with_the_library_path_first_and_keeps_its_folder_album():
    path = LIBRARY / "Alfa Rococo" / "Alfa Rococo - Best Of" / "Alfa Rococo - Lever l'ancre.mp3"
    tagger, finder, files = make_tagger(
        path, TrackInfo("Alfa Rococo - Lever", "Alfa Rococo"), [LEVER]
    )
    assert tagger.tag(path).status == AutoTagStatus.TAGGED
    assert finder.calls == [
        (
            TrackSearch("Lever l'ancre", "Alfa Rococo", "Best Of"),
            ExistingTags(TrackInfo(album="Best Of")),
            True,
        )
    ]
    assert files.writes[0][1].metadata.info == TrackInfo(
        "Lever l'ancre", "Alfa Rococo", "Best Of", "2007"
    )


def test_searches_with_the_tags_when_the_library_path_finds_nothing():
    path = LIBRARY / "Alfa Rococo" / "Alfa Rococo - Lever.mp3"
    tagger, finder, _files = make_tagger(
        path, TrackInfo("Lever l'ancre", "Alfa Rococo"), [None, LEVER]
    )
    assert tagger.tag(path).status == AutoTagStatus.TAGGED
    assert get_titles(finder) == ["Lever", "Lever l'ancre"]


def test_searches_with_the_tags_when_they_name_another_version_than_the_path():
    path = LIBRARY / "Alfa Rococo" / "Alfa Rococo - Lever l'ancre.mp3"
    tagger, finder, _files = make_tagger(
        path, TrackInfo("Lever l'ancre (Live)", "Alfa Rococo"), [LEVER, None]
    )
    tagger.tag(path)
    assert get_titles(finder) == ["Lever l'ancre", "Lever l'ancre (Live)"]


def test_searches_once_when_the_path_only_spells_the_tags_differently():
    path = LIBRARY / "AC_DC" / "AC_DC - Back in Black.mp3"
    tagger, finder, _files = make_tagger(path, TrackInfo("Back in Black", "AC/DC"), [])
    tagger.tag(path)
    assert len(finder.calls) == 1


def test_takes_the_path_song_over_a_placeholder_tag_title():
    path = LIBRARY / "Alfa Rococo" / "Alfa Rococo - Lever l'ancre.mp3"
    tagger, finder, _files = make_tagger(path, TrackInfo("Track 01", "Alfa Rococo"), [LEVER])
    assert tagger.tag(path).status == AutoTagStatus.TAGGED
    assert len(finder.calls) == 1


def test_searches_the_tags_from_no_tags_with_the_stored_cover_and_replaces_covers():
    path = LIBRARY / "Song.mp3"
    files = FakeTagFiles(
        {path: ExistingTags(TrackInfo("Song", "Band"), TrackExtras(genre="Rock"), True)}
    )
    finder = FakeTrackFinder([])
    SingleTrackTagger(finder, files).tag(path)
    assert finder.calls == [(TrackSearch("Song", "Band"), ExistingTags(has_cover=True), True)]


def test_lets_an_unreadable_file_fail():
    tagger, _finder, _files = make_tagger(LIBRARY / "a.mp3", TrackInfo(), [])
    with pytest.raises(TagError):
        tagger.tag(LIBRARY / "broken.wav")
