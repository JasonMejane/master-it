import pytest

from masterit.tagging.paths.terms import TrackSearchTerms
from masterit.tagging.paths.track_name import parse_track_filename, split_label


@pytest.mark.parametrize(
    ("filename", "terms"),
    [
        ("Chumbawamba - Tubthumping.mp3", TrackSearchTerms("Tubthumping", "Chumbawamba")),
        ("Artist_Name - Track.Title.mp3", TrackSearchTerms("Track Title", "Artist Name")),
        ("AC-DC - Track-Title.mp3", TrackSearchTerms("Track-Title", "AC-DC")),
        ("Tubthumping.mp3", TrackSearchTerms("Tubthumping")),
        ("01 - Artist - Song Title.mp3", TrackSearchTerms("Song Title", "Artist")),
        ("1.02 Artist - Song Title.ogg", TrackSearchTerms("Song Title", "Artist")),
        ("12. Song_Title.mp3", TrackSearchTerms("Song Title")),
        ("Artist \u2013 Song Title.mp3", TrackSearchTerms("Song Title", "Artist")),
        ("Artist\u2014Song Title.mp3", TrackSearchTerms("Song Title", "Artist")),
        (
            "AC-DC - Track-Title (Live) feat. Guest.mp3",
            TrackSearchTerms("Track-Title (Live) feat Guest", "AC-DC"),
        ),
        ("AC-DC.mp3", TrackSearchTerms("AC-DC")),
        ("Artist - .mp3", TrackSearchTerms("Artist -")),
        ("_ \u2013 Title.mp3", TrackSearchTerms("\u2013 Title")),
        ("99 Luftballons.mp3", TrackSearchTerms("Luftballons")),
        ("١٢ Song.mp3", TrackSearchTerms("١٢ Song")),
        ("\ufeffArtist - Title.mp3", TrackSearchTerms("Title", "Artist")),
    ],
)
def test_parses_artist_and_title_from_file_names(filename: str, terms: TrackSearchTerms):
    assert parse_track_filename(filename) == terms


def test_split_label_cuts_at_the_first_separator():
    assert split_label("A - B - C") == ("A", "B - C")
    assert split_label("A-B") == ("", "")
