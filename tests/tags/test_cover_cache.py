from pathlib import Path

from masterit.tags.cover_cache import make_cover_cache

from .fakes import FakeCoverStore

SONG = Path("/music/Song.mp3")
OTHER = Path("/music/Other.mp3")


def test_same_covers_share_a_digest():
    cache = make_cover_cache(FakeCoverStore({SONG: b"cover", OTHER: b"cover"}))
    assert cache.get(SONG) is not None
    assert cache.get(SONG) == cache.get(OTHER)


def test_different_covers_have_different_digests():
    cache = make_cover_cache(FakeCoverStore({SONG: b"cover", OTHER: b"other"}))
    assert cache.get(SONG) != cache.get(OTHER)


def test_missing_or_unreadable_cover_has_no_digest():
    cache = make_cover_cache(FakeCoverStore(failing={OTHER}))
    assert cache.get(SONG) is None
    assert cache.get(OTHER) is None
