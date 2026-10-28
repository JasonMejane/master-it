import os
from pathlib import Path

from masterit.tagging.paths.readable_path import make_readable_path


def test_reads_a_broken_byte_sequence_as_one_replacement_character_like_node():
    path = Path(os.fsdecode(b"/music/a\xe9\x80b.mp3"))
    assert make_readable_path(path) == Path("/music/a\ufffdb.mp3")


def test_keeps_readable_paths():
    assert make_readable_path(Path("/music/Café.mp3")) == Path("/music/Café.mp3")


def test_reads_a_lone_surrogate_of_a_windows_name_as_one_replacement_character():
    assert make_readable_path(Path("C:/music/a\ud800b.mp3"), "nt") == Path("C:/music/a\ufffdb.mp3")
