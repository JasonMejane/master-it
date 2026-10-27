from pathlib import Path

from masterit.tags.fields import TagField
from masterit.tags.tag_cache import TagCache

from .fakes import FakeTagStore

SONG = Path("/music/Song.mp3")


def test_tags_are_read_once():
    store = FakeTagStore({SONG: {TagField.TITLE: "Song"}})
    cache = TagCache(store)
    assert cache.get(SONG) == {TagField.TITLE: "Song"}
    assert cache.get(SONG) == {TagField.TITLE: "Song"}
    assert store.reads == [SONG]


def test_unreadable_file_has_no_tags():
    cache = TagCache(FakeTagStore(failing={SONG}))
    assert cache.get(SONG) == {}


def test_forgotten_files_are_read_again():
    store = FakeTagStore({SONG: {TagField.TITLE: "Old"}})
    cache = TagCache(store)
    cache.get(SONG)
    store.tags[SONG] = {TagField.TITLE: "New"}
    cache.forget([SONG])
    assert cache.get(SONG) == {TagField.TITLE: "New"}


def test_clear_forgets_everything():
    store = FakeTagStore()
    cache = TagCache(store)
    cache.get(SONG)
    cache.clear()
    cache.get(SONG)
    assert store.reads == [SONG, SONG]
