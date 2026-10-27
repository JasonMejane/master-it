from pathlib import Path

import pytest

from masterit.tags.cover_store import MutagenCoverStore
from masterit.tags.tag_store import TagError

from .fixtures import BACK_COVER, FORMATS, copy_fixture, count_pictures, embed_cover, open_raw

COVER = b"front-cover"


@pytest.mark.parametrize("extension", [*FORMATS, "wav"])
def test_embedded_cover_is_read(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    embed_cover(song, COVER)
    assert MutagenCoverStore().read(song) == COVER


@pytest.mark.parametrize("extension", [*FORMATS, "wav"])
def test_file_without_cover_has_none(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    assert MutagenCoverStore().read(song) is None


@pytest.mark.parametrize("extension", ["mp3", "flac", "opus"])
def test_front_cover_is_preferred(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    embed_cover(song, b"back", BACK_COVER)
    embed_cover(song, COVER)
    assert MutagenCoverStore().read(song) == COVER


@pytest.mark.parametrize("extension", ["mp3", "flac", "opus"])
def test_other_picture_is_used_without_front_cover(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    embed_cover(song, b"back", BACK_COVER)
    assert MutagenCoverStore().read(song) == b"back"


def test_untagged_mp3_has_no_cover(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3")
    open_raw(song).delete()
    assert MutagenCoverStore().read(song) is None


def test_unreadable_file_raises_tag_error(tmp_path: Path):
    text = tmp_path / "notes.mp3"
    text.write_text("not audio")
    with pytest.raises(TagError):
        MutagenCoverStore().read(text)


def test_unknown_format_has_no_cover(tmp_path: Path):
    text = tmp_path / "notes.txt"
    text.write_text("not audio")
    assert MutagenCoverStore().read(text) is None


def test_malformed_ogg_picture_is_skipped(tmp_path: Path):
    song = copy_fixture(tmp_path, "opus")
    audio = open_raw(song)
    audio["metadata_block_picture"] = ["not-a-picture"]
    audio.save()
    embed_cover(song, COVER)
    assert MutagenCoverStore().read(song) == COVER


PNG_COVER = b"\x89PNG\r\nnew-cover"


@pytest.mark.parametrize("extension", FORMATS)
def test_written_cover_replaces_every_picture(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    embed_cover(song, b"back", BACK_COVER)
    embed_cover(song, COVER)
    MutagenCoverStore().write(song, PNG_COVER)
    assert MutagenCoverStore().read(song) == PNG_COVER
    assert count_pictures(song) == 1


@pytest.mark.parametrize("extension", FORMATS)
def test_cover_is_written_to_a_file_without_tags(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    open_raw(song).delete()
    MutagenCoverStore().write(song, b"\xff\xd8\xffjpeg")
    assert MutagenCoverStore().read(song) == b"\xff\xd8\xffjpeg"


def test_written_cover_is_a_front_cover_with_its_image_type(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3")
    MutagenCoverStore().write(song, PNG_COVER)
    picture = open_raw(song).tags.getall("APIC")[0]
    assert (picture.type, picture.mime) == (3, "image/png")


def test_cover_of_a_wav_file_is_refused(tmp_path: Path):
    song = copy_fixture(tmp_path, "wav")
    with pytest.raises(TagError):
        MutagenCoverStore().write(song, COVER)


def test_cover_of_a_broken_file_is_refused(tmp_path: Path):
    song = tmp_path / "broken.mp3"
    song.write_bytes(b"not audio")
    with pytest.raises(TagError):
        MutagenCoverStore().write(song, COVER)


def test_ogg_cover_replaces_legacy_cover_art(tmp_path: Path):
    song = copy_fixture(tmp_path, "opus")
    audio = open_raw(song)
    audio["coverart"] = ["b2xk"]
    audio.save()
    MutagenCoverStore().write(song, PNG_COVER)
    assert "coverart" not in open_raw(song)
