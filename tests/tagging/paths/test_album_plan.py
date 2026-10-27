from pathlib import Path

import pytest

from masterit.tagging.paths.album_plan import find_album_folder, get_file_root, plan_tracks
from masterit.tagging.paths.terms import AlbumFolder, AlbumTrack, AlbumUnit, TrackPlan

ROOT = Path("/library")
ARTIST_FOLDER = ROOT / "Queen"
ALBUM_FOLDER = ARTIST_FOLDER / "Queen - Jazz"


class FakeLister:
    def __init__(self, folders: dict[Path, list[Path]]) -> None:
        self.folders = folders
        self.listed: list[Path] = []

    def __call__(self, folder: Path) -> list[Path]:
        self.listed.append(folder)
        return self.folders.get(folder, [])


def test_reads_an_album_folder_below_its_artist_folder():
    assert find_album_folder(ALBUM_FOLDER / "Queen - Bicycle.mp3") == AlbumFolder(
        ALBUM_FOLDER, "Queen", "Jazz", None
    )


def test_ignores_letter_case_between_artist_folders():
    folder = ROOT / "queen" / "QUEEN - Jazz (1978) [FLAC]"
    assert find_album_folder(folder / "song.flac") == AlbumFolder(folder, "QUEEN", "Jazz", None)


def test_takes_the_disc_from_a_disc_subfolder():
    assert find_album_folder(ALBUM_FOLDER / "CD2" / "a.mp3") == AlbumFolder(
        ALBUM_FOLDER, "Queen", "Jazz", 2
    )
    found = find_album_folder(ALBUM_FOLDER / "Disc 1" / "a.mp3")
    assert found is not None
    assert found.disc == 1


def test_takes_the_disc_from_a_disc_suffix_of_the_album_folder():
    folder = ARTIST_FOLDER / "Queen - Live Killers - CD2"
    assert find_album_folder(folder / "a.mp3") == AlbumFolder(folder, "Queen", "Live Killers", 2)


@pytest.mark.parametrize(
    "file",
    [
        ARTIST_FOLDER / "Queen - Bicycle.mp3",
        ROOT / "Queen - Jazz" / "a.mp3",
        ROOT / "Bowie" / "Queen - Jazz" / "a.mp3",
        ARTIST_FOLDER / "Jazz" / "a.mp3",
        ARTIST_FOLDER / "Queen - Singles" / "a.mp3",
        ARTIST_FOLDER / "Queen - CD2" / "a.mp3",
    ],
)
def test_finds_no_album_outside_the_artist_and_album_layout(file: Path):
    assert find_album_folder(file) is None


@pytest.mark.parametrize(
    ("name", "disc"),
    [
        ("Queen - Jazz (Disc 2)", 2),
        ("Queen - Jazz - CD2 [FLAC]", 2),
        ("Queen - Jazz \u2013 CD2", 2),
        ("Queen - Jazz - CD0", None),
    ],
)
def test_reads_disc_notes_in_any_common_form(name: str, disc: int | None):
    found = find_album_folder(ARTIST_FOLDER / name / "a.mp3")
    assert found is not None
    assert (found.album, found.disc) == ("Jazz", disc)


def test_labelled_disc_folders_win_over_the_album_suffix():
    bonus = find_album_folder(ALBUM_FOLDER / "CD1 - Bonus" / "a.mp3")
    suffixed = find_album_folder(ARTIST_FOLDER / "Queen - Jazz - CD2" / "CD1" / "a.mp3")
    assert bonus is not None
    assert suffixed is not None
    assert (bonus.disc, suffixed.disc) == (1, 1)


def test_keeps_the_artist_as_the_folder_spells_it():
    found = find_album_folder(ROOT / "R.E.M" / "R.E.M - Monster" / "a.mp3")
    assert found is not None
    assert found.artist == "R.E.M"


def test_resolves_relative_paths():
    found = find_album_folder(Path("Queen", "Queen - Jazz", "a.mp3"))
    assert found is not None
    assert found.folder == Path("Queen", "Queen - Jazz").absolute()


def test_file_root_is_its_album_folder_or_its_own_folder():
    assert get_file_root(ALBUM_FOLDER / "CD2" / "a.mp3") == ALBUM_FOLDER
    assert get_file_root(ARTIST_FOLDER / "Queen - Bicycle.mp3") == ARTIST_FOLDER


def test_makes_one_album_of_every_file_of_an_album_folder():
    tracks = [ALBUM_FOLDER / "a.mp3", ALBUM_FOLDER / "b.mp3", ALBUM_FOLDER / "CD2" / "c.mp3"]
    lister = FakeLister({ALBUM_FOLDER: tracks})
    plan = plan_tracks([tracks[1]], lister)
    album_tracks = [
        AlbumTrack(tracks[0], None),
        AlbumTrack(tracks[1], None),
        AlbumTrack(tracks[2], 2),
    ]
    assert plan == TrackPlan([AlbumUnit(ALBUM_FOLDER, "Queen", "Jazz", album_tracks)], [])
    assert lister.listed == [ALBUM_FOLDER]


def test_lists_each_album_folder_once_and_keeps_singles_apart():
    single = ARTIST_FOLDER / "Queen - Bicycle.mp3"
    tracks = [ALBUM_FOLDER / "a.mp3", ALBUM_FOLDER / "b.mp3"]
    lister = FakeLister({ALBUM_FOLDER: tracks})
    plan = plan_tracks([tracks[0], single, tracks[1]], lister)
    assert lister.listed == [ALBUM_FOLDER]
    assert plan.singles == [single]
    assert [len(album.tracks) for album in plan.albums] == [2]


def test_makes_one_album_per_disc_folder():
    first, second = (ARTIST_FOLDER / f"Queen - Live Killers - {disc}" for disc in ("CD1", "CD2"))
    lister = FakeLister({first: [first / "a.mp3"], second: [second / "b.mp3"]})
    plan = plan_tracks([first / "a.mp3", second / "b.mp3"], lister)
    assert [(album.album, album.tracks[0].disc) for album in plan.albums] == [
        ("Live Killers", 1),
        ("Live Killers", 2),
    ]


def test_leaves_out_listed_files_of_other_folders_and_keeps_selected_ones():
    track = ALBUM_FOLDER / "a.mp3"
    bonus = ALBUM_FOLDER / "Bonus" / "b.mp3"
    selected = ALBUM_FOLDER / "c.mp3"
    plan = plan_tracks([selected, bonus], FakeLister({ALBUM_FOLDER: [track, bonus]}))
    assert [album_track.path for album_track in plan.albums[0].tracks] == [track, selected]
    assert plan.singles == [bonus]


def test_collapses_parent_segments_like_resolved_paths():
    file = ALBUM_FOLDER / "CD1" / ".." / "a.mp3"
    assert find_album_folder(file) == AlbumFolder(ALBUM_FOLDER, "Queen", "Jazz", None)
    assert get_file_root(file) == ALBUM_FOLDER


def test_disc_folder_number_ends_at_any_non_ascii_word_character():
    found = find_album_folder(ALBUM_FOLDER / "CD1枚目" / "a.mp3")
    assert found is not None
    assert found.disc == 1
