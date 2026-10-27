from pathlib import Path

from masterit.tags.file_cache import FileCache

SONG = Path("/music/Song.mp3")
OTHER = Path("/music/Other.mp3")


class CountingReader:
    def __init__(self) -> None:
        self.reads: list[Path] = []
        self.value = "old"

    def read(self, path: Path) -> str:
        self.reads.append(path)
        return f"{self.value} {path.stem}"


def test_files_are_read_once():
    reader = CountingReader()
    cache = FileCache(reader.read)
    assert cache.get(SONG) == "old Song"
    assert cache.get(SONG) == "old Song"
    assert reader.reads == [SONG]


def test_forgotten_files_are_read_again():
    reader = CountingReader()
    cache = FileCache(reader.read)
    cache.get(SONG)
    cache.get(OTHER)
    reader.value = "new"
    cache.forget([SONG])
    assert cache.get(SONG) == "new Song"
    assert cache.get(OTHER) == "old Other"


def test_forgetting_unknown_files_is_harmless():
    FileCache(CountingReader().read).forget([SONG])


def test_clear_forgets_everything():
    reader = CountingReader()
    cache = FileCache(reader.read)
    cache.get(SONG)
    cache.clear()
    cache.get(SONG)
    assert reader.reads == [SONG, SONG]
