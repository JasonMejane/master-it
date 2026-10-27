from pathlib import Path
from typing import Any, cast

import mutagen
import pytest
from mutagen.id3 import ID3

from masterit.tags.fields import TagField
from masterit.tags.tag_store import MutagenTagStore, TagError

from .fixtures import FORMATS, copy_fixture

FULL_TAGS = {
    TagField.TITLE: "Song",
    TagField.ARTIST: "Artist",
    TagField.ALBUM: "Album",
    TagField.ALBUM_ARTIST: "Various",
    TagField.YEAR: "2024",
    TagField.GENRE: "Rock",
    TagField.TRACK: "3/12",
}


def open_raw(path: Path) -> Any:
    return cast(Any, mutagen.File(path))  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.parametrize("extension", FORMATS)
def test_written_tags_are_read_back(tmp_path: Path, extension: str):
    store = MutagenTagStore()
    song = copy_fixture(tmp_path, extension)
    store.write(song, FULL_TAGS)
    assert store.read(song) == FULL_TAGS


@pytest.mark.parametrize("extension", FORMATS)
def test_empty_value_removes_tag(tmp_path: Path, extension: str):
    store = MutagenTagStore()
    song = copy_fixture(tmp_path, extension)
    store.write(song, {TagField.TITLE: "Song", TagField.ARTIST: "Artist"})
    store.write(song, {TagField.TITLE: ""})
    assert store.read(song) == {TagField.ARTIST: "Artist"}


def test_removing_absent_tag_is_harmless(tmp_path: Path):
    store = MutagenTagStore()
    song = copy_fixture(tmp_path, "mp3")
    store.write(song, {TagField.GENRE: ""})
    assert store.read(song) == {}


def test_unrelated_tags_are_kept(tmp_path: Path):
    store = MutagenTagStore()
    song = copy_fixture(tmp_path, "opus")
    store.write(song, {TagField.TITLE: "Song"})
    assert open_raw(song)["encoder"] == ["Lavc libopus"]


@pytest.mark.parametrize("extension", ["mp3", "flac"])
def test_untagged_file_gets_tags(tmp_path: Path, extension: str):
    store = MutagenTagStore()
    song = copy_fixture(tmp_path, extension)
    open_raw(song).delete()
    assert store.read(song) == {}
    store.write(song, {TagField.TITLE: "Song"})
    assert store.read(song) == {TagField.TITLE: "Song"}


def test_mp3_tags_are_id3v24(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3")
    MutagenTagStore().write(song, {TagField.TITLE: "Song"})
    assert ID3(song).version == (2, 4, 0)  # pyright: ignore[reportUnknownMemberType]


def test_unsupported_file_raises_tag_error(tmp_path: Path):
    text = tmp_path / "notes.mp3"
    text.write_text("not audio")
    with pytest.raises(TagError):
        MutagenTagStore().read(text)


def test_missing_file_raises_tag_error(tmp_path: Path):
    with pytest.raises(TagError):
        MutagenTagStore().write(tmp_path / "gone.mp3", {TagField.TITLE: "Song"})


def test_value_rejected_by_format_raises_tag_error(tmp_path: Path):
    song = copy_fixture(tmp_path, "m4a")
    with pytest.raises(TagError):
        MutagenTagStore().write(song, {TagField.TRACK: "three"})


def test_unknown_format_raises_tag_error(tmp_path: Path):
    text = tmp_path / "notes.txt"
    text.write_text("not audio")
    with pytest.raises(TagError, match=r"Tags not supported for notes\.txt"):
        MutagenTagStore().read(text)


def test_ogg_flac_is_supported(tmp_path: Path):
    song = copy_fixture(tmp_path, "ogg", fixture="silence_flac")
    MutagenTagStore().write(song, {TagField.TITLE: "Song"})
    assert MutagenTagStore().read(song) == {TagField.TITLE: "Song"}


def test_format_without_simple_tags_is_refused(tmp_path: Path):
    song = copy_fixture(tmp_path, "wav")
    with pytest.raises(TagError, match=r"Tags not supported for song\.wav"):
        MutagenTagStore().write(song, {TagField.ARTIST: "Z"})
    with pytest.raises(TagError):
        MutagenTagStore().read(song)


@pytest.mark.parametrize("extension", ["mp3", "flac", "m4a"])
def test_multiple_values_are_joined(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    MutagenTagStore().write(song, {TagField.TITLE: "Song"})
    audio = cast(Any, mutagen.File(song, easy=True))  # pyright: ignore[reportUnknownMemberType]
    audio["artist"] = ["A", "B"]
    audio.save()
    assert MutagenTagStore().read(song)[TagField.ARTIST] == "A; B"
