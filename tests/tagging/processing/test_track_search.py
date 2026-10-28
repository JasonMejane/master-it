import os
from pathlib import Path

from masterit.tagging.metadata.types import TrackInfo, TrackSearch
from masterit.tagging.processing.track_search import build_track_search, is_other_version

ROOT = Path("/library")
SOURCE = ROOT / "Folder Artist" / "Folder Album" / "File Artist - File Title.mp3"


def test_prefers_embedded_tags_then_file_name_then_folders():
    assert build_track_search(SOURCE, ROOT, TrackInfo()) == TrackSearch(
        "File Title", "File Artist", "Folder Album"
    )
    bare = ROOT / "Folder Artist" / "Folder Album" / "Title.mp3"
    assert build_track_search(bare, ROOT, TrackInfo()) == TrackSearch(
        "Title", "Folder Artist", "Folder Album"
    )
    tags = TrackInfo("Tag Title", "Tag Artist", "Tag Album")
    assert build_track_search(SOURCE, ROOT, tags) == TrackSearch(
        "Tag Title", "Tag Artist", "Tag Album"
    )
    assert build_track_search(ROOT / "Title.mp3", ROOT, TrackInfo()) == TrackSearch("Title")


def test_takes_the_artist_and_album_from_a_library_path():
    album_path = ROOT / "Queen" / "Queen - Greatest Hits" / "Queen - Bicycle.mp3"
    assert build_track_search(album_path, ROOT, TrackInfo()) == TrackSearch(
        "Bicycle", "Queen", "Greatest Hits"
    )
    single = ROOT / "Music" / "Queen" / "Queen - Bicycle.mp3"
    assert build_track_search(single, ROOT, TrackInfo()) == TrackSearch("Bicycle", "Queen")


def test_reads_undecodable_file_names_as_replacement_characters():
    odd = ROOT / "Band - Caf\udce9.mp3"
    assert build_track_search(odd, ROOT, TrackInfo()) == TrackSearch("Caf�", "Band")


def test_tags_naming_another_version_than_the_found_song():
    assert is_other_version("Song (Live)", "Song")
    assert not is_other_version("Song (Remastered)", "Song")
    assert not is_other_version("Track 01", "Song")


def test_reads_a_broken_byte_sequence_as_one_replacement_character_like_node():
    truncated = ROOT / os.fsdecode(b"Band - a\xe9\x80b.mp3")
    assert build_track_search(truncated, ROOT, TrackInfo()) == TrackSearch("a�b", "Band")
