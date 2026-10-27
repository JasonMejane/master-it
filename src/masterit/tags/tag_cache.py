from functools import partial
from pathlib import Path

from masterit.tags.fields import Tags
from masterit.tags.file_cache import FileCache
from masterit.tags.tag_store import TagError, TagStore

type TagCache = FileCache[Tags]


def make_tag_cache(store: TagStore) -> TagCache:
    return FileCache(partial(read_tags_or_empty, store))


def read_tags_or_empty(store: TagStore, path: Path) -> Tags:
    try:
        return store.read(path)
    except TagError:
        return {}
