import shutil
from pathlib import Path
from typing import Any, cast

import mutagen
import pytest
from mutagen.flac import FLAC

from masterit.tagging.metadata.types import (
    ExistingTags,
    ExtraField,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
)
from masterit.tagging.track_tags import TagWrite, TrackTagStore
from masterit.tags.cover_store import MutagenCoverStore
from masterit.tags.tag_store import TagError

from ..tags.fixtures import FORMATS, copy_fixture, embed_cover, open_raw

INFO = TrackInfo("Title", "Artist", "Album", "1999")
EXTRAS = TrackExtras("Rock", "Band", 3, 12, 1, 2)
COVER = b"\xff\xd8\xffcover"


def open_easy(song: Path) -> Any:
    audio = cast(Any, mutagen.File(song, easy=True))  # pyright: ignore[reportUnknownMemberType]
    if audio.tags is None:
        audio.add_tags()
    return audio


def write(
    song: Path, metadata: TrackMetadata, cleared: tuple[ExtraField, ...] = ()
) -> ExistingTags:
    store = TrackTagStore()
    store.write(song, TagWrite(metadata, cleared))
    return store.read(song)


@pytest.mark.parametrize("extension", FORMATS)
def test_written_tags_read_back(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    assert write(song, TrackMetadata(INFO, EXTRAS, COVER)) == ExistingTags(
        INFO, EXTRAS, has_cover=True
    )
    assert TrackTagStore().read_cover(song) == COVER


@pytest.mark.parametrize("extension", FORMATS)
def test_untagged_file_reads_empty(tmp_path: Path, extension: str):
    assert TrackTagStore().read(copy_fixture(tmp_path, extension)) == ExistingTags()


@pytest.mark.parametrize("extension", FORMATS)
def test_blank_fields_and_unknown_extras_keep_stored_values(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    write(song, TrackMetadata(INFO, EXTRAS, COVER))
    stored = write(song, TrackMetadata(TrackInfo("New", " ", "", ""), TrackExtras(genre="Pop")))
    expected_extras = TrackExtras("Pop", "Band", 3, 12, 1, 2)
    assert stored == ExistingTags(
        TrackInfo("New", "Artist", "Album", "1999"), expected_extras, True
    )


@pytest.mark.parametrize("extension", FORMATS)
def test_cleared_counts_go_and_new_positions_are_written(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    write(song, TrackMetadata(INFO, EXTRAS))
    found = TrackExtras(track_number=5, disc_number=2)
    stored = write(song, TrackMetadata(TrackInfo(), found), ("track_count", "disc_count"))
    assert stored.extras == TrackExtras("Rock", "Band", 5, None, 2, None)


@pytest.mark.parametrize("extension", FORMATS)
def test_cleared_genre_and_album_artist_go(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    write(song, TrackMetadata(INFO, EXTRAS))
    stored = write(song, TrackMetadata(TrackInfo()), ("genre", "album_artist"))
    assert (stored.extras.genre, stored.extras.album_artist) == (None, None)


@pytest.mark.parametrize("extension", FORMATS)
def test_only_the_lead_artist_is_replaced(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    easy = open_easy(song)
    easy["artist"] = ["Old", "Guest"]
    easy.save()
    write(song, TrackMetadata(TrackInfo(artist="New")))
    assert open_easy(song)["artist"] == ["New", "Guest"]


def test_reads_vorbis_totals_and_slashed_positions(tmp_path: Path):
    song = copy_fixture(tmp_path, "flac")
    audio = open_raw(song)
    audio["tracknumber"] = ["4"]
    audio["totaltracks"] = ["9"]
    audio["discnumber"] = ["1/3"]
    audio["date"] = ["2004-05-17"]
    audio.save()
    stored = TrackTagStore().read(song)
    extras = stored.extras
    assert (extras.track_number, extras.track_count, extras.disc_number, extras.disc_count) == (
        4,
        9,
        1,
        3,
    )
    assert stored.info.year == "2004"


def test_reads_odd_positions_as_unknown(tmp_path: Path):
    song = copy_fixture(tmp_path, "flac")
    audio = open_raw(song)
    audio["tracknumber"] = ["A1"]
    audio["discnumber"] = ["0/0"]
    audio.save()
    extras = TrackTagStore().read(song).extras
    assert (extras.track_number, extras.disc_number, extras.disc_count) == (None, None, None)


def test_writes_vorbis_totals_in_their_own_keys(tmp_path: Path):
    song = copy_fixture(tmp_path, "opus")
    write(song, TrackMetadata(TrackInfo(), EXTRAS))
    audio = open_raw(song)
    assert (audio["tracknumber"], audio["tracktotal"], audio["discnumber"], audio["disctotal"]) == (
        ["3"],
        ["12"],
        ["1"],
        ["2"],
    )


def test_writes_mp3_positions_with_their_counts(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3")
    write(
        song, TrackMetadata(TrackInfo(), TrackExtras(track_number=3, track_count=12, disc_number=1))
    )
    tags = open_raw(song).tags
    assert (str(tags["TRCK"]), str(tags["TPOS"])) == ("3/12", "1")


@pytest.mark.parametrize("extension", FORMATS)
def test_an_existing_cover_counts_and_is_kept_without_a_new_one(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    embed_cover(song, COVER)
    assert write(song, TrackMetadata(INFO)).has_cover
    assert MutagenCoverStore().read(song) == COVER


def test_wav_files_are_refused(tmp_path: Path):
    song = copy_fixture(tmp_path, "wav")
    store = TrackTagStore()
    with pytest.raises(TagError, match="not supported"):
        store.read(song)
    with pytest.raises(TagError, match="not supported"):
        store.write(song, TagWrite(TrackMetadata(INFO)))


@pytest.mark.parametrize(("extension", "position"), [("flac", (None, 20)), ("mp3", (None, None))])
def test_a_cleared_number_goes_with_its_field(
    tmp_path: Path, extension: str, position: tuple[int | None, int | None]
):
    song = copy_fixture(tmp_path, extension)
    write(song, TrackMetadata(INFO, EXTRAS))
    stored = write(song, TrackMetadata(TrackInfo(), TrackExtras(track_count=20)), ("track_number",))
    assert (stored.extras.track_number, stored.extras.track_count) == position


def test_a_failed_write_leaves_the_file_as_it_was(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    song = copy_fixture(tmp_path, "flac")
    before = song.read_bytes()

    def fail(_store: object, _path: Path, _data: bytes) -> None:
        raise TagError("disk full")

    monkeypatch.setattr(MutagenCoverStore, "write", fail)
    with pytest.raises(TagError, match="disk full"):
        TrackTagStore().write(song, TagWrite(TrackMetadata(INFO, EXTRAS, COVER)))
    assert song.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["song.flac"]


def test_a_file_that_cannot_be_saved_fails_with_a_tag_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    song = copy_fixture(tmp_path, "flac")

    def fail(_audio: object, *_args: object, **_kwargs: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(FLAC, "save", fail)
    with pytest.raises(TagError, match="read-only"):
        TrackTagStore().write(song, TagWrite(TrackMetadata(INFO)))


def test_writes_through_a_hidden_copy_and_keeps_the_file_mode(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3")
    song.chmod(0o640)
    write(song, TrackMetadata(INFO, EXTRAS, COVER))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["song.mp3"]
    assert song.stat().st_mode & 0o777 == 0o640


def test_reads_and_clears_the_spaced_vorbis_album_artist(tmp_path: Path):
    song = copy_fixture(tmp_path, "flac")
    audio = open_raw(song)
    audio["album artist"] = ["Band"]
    audio.save()
    assert TrackTagStore().read(song).extras.album_artist == "Band"
    assert write(song, TrackMetadata(TrackInfo()), ("album_artist",)).extras.album_artist is None


@pytest.mark.parametrize("extension", FORMATS)
def test_a_new_number_keeps_the_stored_count(tmp_path: Path, extension: str):
    song = copy_fixture(tmp_path, extension)
    write(song, TrackMetadata(INFO, EXTRAS))
    stored = write(song, TrackMetadata(TrackInfo(), TrackExtras(track_number=5)))
    assert (stored.extras.track_number, stored.extras.track_count) == (5, 12)


def test_a_new_vorbis_number_keeps_a_slashed_count(tmp_path: Path):
    song = set_vorbis_keys(tmp_path, {"tracknumber": "4/10"})
    stored = write(song, TrackMetadata(TrackInfo(), TrackExtras(track_number=5)))
    assert (stored.extras.track_number, stored.extras.track_count) == (5, 10)


def test_clearing_a_vorbis_count_drops_it_from_the_number(tmp_path: Path):
    song = set_vorbis_keys(tmp_path, {"tracknumber": "4/10", "tracktotal": "10"})
    stored = write(song, TrackMetadata(TrackInfo()), ("track_count",))
    assert (stored.extras.track_number, stored.extras.track_count) == (4, None)
    assert open_raw(song)["tracknumber"] == ["4"]


def test_the_vorbis_total_wins_over_a_slashed_count(tmp_path: Path):
    song = set_vorbis_keys(tmp_path, {"tracknumber": "4/10", "tracktotal": "12"})
    assert TrackTagStore().read(song).extras.track_count == 12


def test_writes_and_reads_ogg_flac_files(tmp_path: Path):
    song = copy_fixture(tmp_path, "ogg", fixture="silence_flac")
    stored = write(song, TrackMetadata(INFO, EXTRAS, COVER))
    assert stored == ExistingTags(INFO, EXTRAS, has_cover=True)


def set_vorbis_keys(folder: Path, values: dict[str, str]) -> Path:
    song = copy_fixture(folder, "flac")
    audio = open_raw(song)
    for key, value in values.items():
        audio[key] = [value]
    audio.save()
    return song


def test_a_copy_that_cannot_be_made_fails_with_a_tag_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    song = copy_fixture(tmp_path, "flac")

    def fail(_source: Path, _target: Path) -> None:
        raise OSError("no space left")

    monkeypatch.setattr(shutil, "copyfile", fail)
    with pytest.raises(TagError, match="no space left"):
        TrackTagStore().write(song, TagWrite(TrackMetadata(INFO)))


def test_tags_files_whose_name_is_near_the_length_limit(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3", name="あ" * 80)
    assert write(song, TrackMetadata(INFO)).info == INFO


def test_tags_the_target_of_a_symbolic_link(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3")
    link = tmp_path / "link.mp3"
    link.symlink_to(song)
    write(link, TrackMetadata(INFO))
    assert link.is_symlink()
    assert TrackTagStore().read(song).info == INFO


def test_a_failed_replace_fails_with_a_tag_error_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    song = copy_fixture(tmp_path, "flac")

    def fail(_source: Path, _target: Path) -> None:
        raise PermissionError("file in use")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(TagError, match="file in use"):
        TrackTagStore().write(song, TagWrite(TrackMetadata(INFO)))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["song.flac"]


@pytest.mark.parametrize(("extension", "position"), [("m4a", (None, 20)), ("mp3", (None, None))])
def test_a_count_without_number_is_kept_as_taglib_and_node_id3_do(
    tmp_path: Path, extension: str, position: tuple[int | None, int | None]
):
    song = copy_fixture(tmp_path, extension)
    write(song, TrackMetadata(INFO, EXTRAS))
    stored = write(song, TrackMetadata(TrackInfo(), TrackExtras(track_count=20)), ("track_number",))
    assert (stored.extras.track_number, stored.extras.track_count) == position
