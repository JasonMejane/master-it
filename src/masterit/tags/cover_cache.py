import hashlib
from functools import partial
from pathlib import Path

from masterit.tags.cover_store import CoverStore
from masterit.tags.file_cache import FileCache
from masterit.tags.tag_store import TagError

# Digests rather than images keep large selections cheap in memory.
type CoverCache = FileCache[str | None]


def make_cover_cache(store: CoverStore) -> CoverCache:
    return FileCache(partial(read_cover_digest, store))


def read_cover_digest(store: CoverStore, path: Path) -> str | None:
    try:
        cover = store.read(path)
    except TagError:
        return None
    return None if cover is None else hashlib.sha256(cover).hexdigest()
