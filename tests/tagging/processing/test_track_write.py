from pathlib import Path

from masterit.tagging.events import AutoTagStatus
from masterit.tagging.metadata.types import ExistingTags, TrackExtras, TrackInfo, TrackMetadata
from masterit.tagging.processing.track_write import TrackOutcome, write_found_metadata
from masterit.tagging.track_tags import TagWrite

from .fakes import FakeTagFiles

SONG = Path("/music/song.mp3")
STORED = ExistingTags(TrackInfo("Song", "Artist"), has_cover=True)


def test_writes_the_changes_and_tags_the_file():
    files = FakeTagFiles()
    found = TrackMetadata(TrackInfo("Song", "Artist", "Album"), TrackExtras(genre="Rock"))
    assert write_found_metadata(files, SONG, STORED, found) == TrackOutcome(AutoTagStatus.TAGGED)
    assert files.writes == [(SONG, TagWrite(found))]


def test_skips_a_file_that_gets_nothing_new():
    files = FakeTagFiles()
    outcome = write_found_metadata(files, SONG, STORED, TrackMetadata(STORED.info))
    assert outcome == TrackOutcome(AutoTagStatus.SKIPPED, "nothing new")
    assert files.writes == []


def test_skips_an_overwrite_whose_cover_is_the_stored_one():
    files = FakeTagFiles(covers={SONG: b"cover"})
    outcome = write_found_metadata(
        files, SONG, STORED, TrackMetadata(STORED.info, cover_data=b"cover")
    )
    assert outcome.status == AutoTagStatus.SKIPPED


def test_writes_a_different_cover():
    files = FakeTagFiles(covers={SONG: b"old"})
    write_found_metadata(files, SONG, STORED, TrackMetadata(STORED.info, cover_data=b"new"))
    assert files.writes[0][1].metadata.cover_data == b"new"


def test_writes_a_cover_without_reading_one_the_file_lacks():
    files = FakeTagFiles(covers={SONG: b"cover"})
    stored = ExistingTags(STORED.info)
    write_found_metadata(files, SONG, stored, TrackMetadata(stored.info, cover_data=b"cover"))
    assert files.writes[0][1].metadata.cover_data == b"cover"
