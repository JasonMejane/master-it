import pytest

from masterit.tagging.metadata.track_matching import (
    FoundAlbumName,
    FoundRelease,
    FoundTrack,
    has_note_after_name,
    is_same_name,
    is_same_release,
    is_same_track,
    is_searched_album,
    is_various_artists,
    strip_remaster_note,
)
from masterit.tagging.metadata.types import AlbumSearch, TrackSearch

GET_LUCKY = TrackSearch("Get Lucky", "Daft Punk", "")
DISCOVERY = AlbumSearch("Daft Punk", "Discovery")


@pytest.mark.parametrize(
    ("found", "searched"),
    [
        ("Beyoncé", "beyonce"),
        ("AC-DC", "ac/dc"),
        ("Title (Remastered 2009)", "Title"),
        ("Title [feat. Jay-Z]", "Title"),
        ("Supermassive Black Hole", "Supermassive Blak Hole"),
        ("Paranoid Android", "Paranoid Androd"),
        ("Smells Like Teen Spirit", "Smels Like Teen Spirit"),
        ("Wish You Were Here - 2011 Remaster", "Wish You Were Here"),
        ("Crazy in Love feat. Jay-Z", "Crazy in Love"),
        ("Title - Mono", "Title"),
        ("Title (Remastered)", "Title"),
        ("Ça Plane Pour Moi", "Ca plane pour moi"),
        ("曲 (版remastered)", "曲"),
        ("曲 - 版remaster", "曲"),
    ],
)
def test_same_names(found: str, searched: str):
    assert is_same_name(found, searched)


@pytest.mark.parametrize(
    ("found", "searched"),
    [
        ("Title (Live)", "Title"),
        ("Title (Karaoke Version)", "Title"),
        (None, "Title"),
        ("Crazy Love", "Crazy in Love"),
        ("Hallo", "Hello"),
        ("Symphony No. 2", "Symphony No. 12"),
        ("Track Title 3", "Track Title 8"),
        ("Symphony I", "Symphony II"),
        ("Movement XVIII", "Movement XVII"),
        ("Lost in Love", "Last in Love"),
        ("Into the Night", "Onto the Night"),
        ("Yesterdays", "Yesterday"),
        ("Smells Like Teen Spirit", "Smells Like Ten Spirit"),
        ("Title - Live", "Title"),
        ("Title (Stereolab Remix)", "Title"),
        ("Title (Monolith Sessions)", "Title"),
        ("Paranoid Android", "Paranoid Andrd"),
        ("Song feat. X\r", "Song"),
        ("Song feat. X\rY", "Song"),
        ("Song feat. X\u2028Y", "Song"),
        ("Song feat. X\n", "Song\n"),
    ],
)
def test_different_names(found: str | None, searched: str):
    assert not is_same_name(found, searched)


def test_same_track_compares_title_and_searched_artist():
    search = TrackSearch("Title", "AC/DC", "")
    assert is_same_track(FoundTrack("TITLE", "ac-dc"), search)
    assert not is_same_track(FoundTrack("Title", "Karaoke Band"), search)
    assert is_same_track(FoundTrack("Title", "Anyone"), TrackSearch("Title", "", ""))


@pytest.mark.parametrize(
    "artist",
    [
        "Daft Punk feat. Pharrell Williams",
        "Pharrell Williams & Daft Punk",
        "Pharrell Williams and Daft Punk",
        "Nile Rodgers, Daft Punk",
    ],
)
def test_same_track_matches_an_artist_shared_by_both_credits(artist: str):
    assert is_same_track(FoundTrack("Get Lucky", artist), GET_LUCKY)


def test_same_track_splits_the_searched_credit_too():
    search = TrackSearch("Get Lucky", "Daft Punk ft. Pharrell Williams", "")
    assert is_same_track(FoundTrack("Get Lucky", "Daft Punk"), search)


def test_same_track_needs_a_shared_artist():
    assert not is_same_track(FoundTrack("Get Lucky", "Pharrell Williams"), GET_LUCKY)
    other = TrackSearch("Get Lucky", "Another, ", "")
    assert not is_same_track(FoundTrack("Get Lucky", "Other, "), other)


def test_same_track_ignores_a_leading_the():
    search = TrackSearch("Simple Little Melody", "Black Eyed Peas", "")
    found = FoundTrack("Simple Little Melody", "The Black Eyed Peas")
    assert is_same_track(found, search)
    assert is_same_track(FoundTrack("Title", "The The"), TrackSearch("Title", "The The", ""))
    assert not is_same_track(FoundTrack("Simple Little Melody", "The Peas"), search)


def test_same_track_keeps_typo_tolerance_for_artists_starting_with_the():
    search = TrackSearch("Help", "The Beatles", "")
    assert is_same_track(FoundTrack("Help", "The Beattles"), search)
    assert is_same_track(FoundTrack("Help", "Beatles"), search)
    roots = TrackSearch("Help", "Roots", "")
    assert is_same_track(FoundTrack("Help", "Jay-Z feat. The Roots"), roots)


@pytest.mark.parametrize(
    ("release", "album"),
    [
        (FoundRelease("Back in Black"), ""),
        (FoundRelease(" back in black "), "Back in Black"),
        (FoundRelease("Undercover, Vol. 2", "Daft Punk", "Daft Punk"), ""),
        (FoundRelease("Undercover, Vol. 2", "Daft Punk & Friends", "Daft Punk"), ""),
        (FoundRelease("Undercover, Vol. 2", "Various Artists", "Daft Punk"), ""),
        (FoundRelease("Album", "Other"), ""),
        (FoundRelease("The E•N•D"), "The E.N.D."),
        (FoundRelease("12 X 5"), "12 x 5"),
        (FoundRelease("Talkin' Blues [Remastered]"), "Talkin\u2019 Blues"),
        (FoundRelease("Album", "The Roots", "Roots"), ""),
        (FoundRelease("Nevermind (2011 Remaster)"), "Nevermind"),
        (FoundRelease("Nevermind - Remastered 2011"), "Nevermind"),
        (FoundRelease("÷"), "÷"),
    ],
)
def test_same_releases(release: FoundRelease, album: str):
    assert is_same_release(release, album)


@pytest.mark.parametrize(
    ("release", "album"),
    [
        (FoundRelease("Greatest Hits"), "Back in Black"),
        (FoundRelease(), "Back in Black"),
        (FoundRelease("Undercover, Vol. 2", "The Infamous Stringdusters", "Daft Punk"), ""),
        (FoundRelease("Back to Black (Deluxe Edition)"), "Back to Black"),
        (FoundRelease("Back to Black (Deluxe Remastered Edition)"), "Back to Black"),
        (FoundRelease("Made in Japan (Live / Remastered)"), "Made in Japan"),
        (FoundRelease("Hits (Stereolab Remix)"), "Hits"),
        (FoundRelease("Album (feat. Someone)"), "Album"),
        (FoundRelease("\u00d7"), "÷"),
        (FoundRelease(), "÷"),
    ],
)
def test_different_releases(release: FoundRelease, album: str):
    assert not is_same_release(release, album)


@pytest.mark.parametrize(
    ("artist", "expected"),
    [("Various Artists", True), ("VARIOUS-ARTISTS", True), ("Various", False), ("", False)],
)
def test_spots_various_artists(artist: str, expected: bool):
    assert is_various_artists(artist) is expected


@pytest.mark.parametrize(
    ("name", "start", "expected"),
    [
        ("Song (Live)", "song", True),
        ("Café - Radio Edit", "Cafe", True),
        ("Album [Deluxe]", "Album", True),
        ("Bicycle Race", "Bicycle", False),
        ("Greatest Hits II", "Greatest Hits", False),
        ("Song", "Song", False),
        ("Love Song (Live)", "Song", False),
    ],
)
def test_note_after_name(name: str, start: str, expected: bool):
    assert has_note_after_name(name, start) is expected


@pytest.mark.parametrize(
    ("found", "expected"),
    [
        (FoundAlbumName("DISCOVERY", "Daft Punk"), True),
        (FoundAlbumName("Discovery (Remastered)", "Daft Punk"), True),
        (FoundAlbumName("Discovery (Deluxe)", "Daft Punk"), False),
        (FoundAlbumName("Discovery", "Data Punk"), False),
        (FoundAlbumName(None, "Daft Punk"), False),
    ],
)
def test_searched_album_needs_same_album_by_same_artist(found: FoundAlbumName, expected: bool):
    assert is_searched_album(found, DISCOVERY) is expected


def test_searched_album_takes_various_and_va_for_various_artists():
    hits = AlbumSearch("VA", "Hits 90")
    assert is_searched_album(FoundAlbumName("Hits 90", "Various Artists"), hits)
    various = AlbumSearch("Various Artists", "Hits 90")
    assert is_searched_album(FoundAlbumName("Hits 90", "Various"), various)
    assert not is_searched_album(FoundAlbumName("Hits 90", "Haddaway"), hits)


@pytest.mark.parametrize(
    ("album", "stripped"),
    [
        ("Jazz (2011 Remaster)", "Jazz"),
        ("Abbey Road - Remastered 2009", "Abbey Road"),
        ("Discovery (Deluxe Edition)", "Discovery (Deluxe Edition)"),
        ("(Remastered)", "(Remastered)"),
    ],
)
def test_strips_only_remaster_notes(album: str, stripped: str):
    assert strip_remaster_note(album) == stripped
