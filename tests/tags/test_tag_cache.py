from pathlib import Path

from masterit.tags.fields import TagField
from masterit.tags.tag_cache import make_tag_cache

from .fakes import FakeTagStore

SONG = Path("/music/Song.mp3")


def test_tags_are_read_from_the_store():
    store = FakeTagStore({SONG: {TagField.TITLE: "Song"}})
    assert make_tag_cache(store).get(SONG) == {TagField.TITLE: "Song"}


def test_unreadable_file_has_no_tags():
    cache = make_tag_cache(FakeTagStore(failing={SONG}))
    assert cache.get(SONG) == {}
