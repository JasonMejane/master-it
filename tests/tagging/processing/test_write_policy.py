from masterit.tagging.metadata.types import ExistingTags, TrackExtras, TrackInfo, TrackMetadata
from masterit.tagging.processing.write_policy import get_overwrite, get_searched_tags
from masterit.tagging.track_tags import TagWrite

STORED = ExistingTags(
    TrackInfo("Song", "Artist", "Album", "1990"),
    TrackExtras(genre="Rock", track_number=5, track_count=12),
    has_cover=True,
)
FOUND = TrackMetadata(
    TrackInfo("Song", "Artist", "", "1991"), TrackExtras(genre="Rock", track_number=3)
)


def test_searches_from_no_tags_but_keeps_the_stored_cover():
    assert get_searched_tags(STORED) == ExistingTags(has_cover=True)


def test_writes_changed_fields_and_clears_stale_counts():
    assert get_overwrite(STORED, FOUND) == TagWrite(
        TrackMetadata(FOUND.info, TrackExtras(track_number=3)), ("track_count",)
    )


def test_writes_nothing_when_nothing_differs():
    same = TrackMetadata(STORED.info, STORED.extras)
    assert get_overwrite(STORED, same) is None


def test_writes_a_new_cover_alone():
    found = TrackMetadata(STORED.info, STORED.extras, b"")
    assert get_overwrite(STORED, found) == TagWrite(TrackMetadata(STORED.info, TrackExtras(), b""))
