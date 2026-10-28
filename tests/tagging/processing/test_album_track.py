from pathlib import Path

import pytest

from masterit.tagging.events import AutoTagStatus
from masterit.tagging.metadata.types import (
    AlbumData,
    AlbumTrackEntry,
    ExistingTags,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
)
from masterit.tagging.paths.terms import AlbumTrack
from masterit.tagging.processing.album_track import AlbumTrackTagger, build_album_track
from masterit.tags.tag_store import TagError

from .fakes import FakeTagFiles

FOLDER = Path("/library/Queen/Queen - Jazz")
JAZZ = AlbumData(
    "Jazz", "Queen", "1978", "Rock", b"cover", [AlbumTrackEntry("Mustapha", 1, 13, 1, 1)], True
)


def test_takes_the_album_and_the_matched_tracklist_entry():
    track = AlbumTrack(FOLDER / "Queen - mustapha (remastered).mp3", None)
    assert build_album_track(JAZZ, track, ExistingTags()) == TrackMetadata(
        TrackInfo("Mustapha", "Queen", "Jazz", "1978"),
        TrackExtras("Rock", "Queen", 1, 13, 1, 1),
        b"cover",
    )


def test_matches_the_entry_by_the_stored_title_too():
    track = AlbumTrack(FOLDER / "01.mp3", None)
    found = build_album_track(JAZZ, track, ExistingTags(TrackInfo("Mustapha")))
    assert found.extras.track_number == 1


def test_keeps_the_file_title_and_the_folder_disc_without_an_entry():
    album = AlbumData("Jazz", "Queen", "", "", None, [], False)
    track = AlbumTrack(FOLDER / "CD2" / "Queen - Bicycle Race.mp3", 2)
    assert build_album_track(album, track, ExistingTags()) == TrackMetadata(
        TrackInfo("Bicycle Race", "Queen", "Jazz", ""),
        TrackExtras(album_artist="Queen", disc_number=2),
    )


def test_tags_a_track_and_keeps_stored_numbers_missing_from_the_tracklist():
    path = FOLDER / "Queen - Bicycle Race.mp3"
    stored = ExistingTags(TrackInfo("Bicycle Race"), TrackExtras(track_number=2, track_count=13))
    files = FakeTagFiles({path: stored})
    outcome = AlbumTrackTagger(files).tag(AlbumTrack(path, None), lambda: JAZZ)
    assert outcome.status == AutoTagStatus.TAGGED
    written = files.writes[0][1]
    assert (written.metadata.extras.track_number, written.cleared_extras) == (None, ())


def test_lets_an_unreadable_file_fail_before_the_album_lookup():
    lookups: list[str] = []

    def look_up() -> AlbumData:
        lookups.append("album")
        return JAZZ

    with pytest.raises(TagError):
        AlbumTrackTagger(FakeTagFiles()).tag(AlbumTrack(FOLDER / "a.wav", None), look_up)
    assert lookups == []
