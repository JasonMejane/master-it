from pathlib import Path

import pytest

from masterit.tags.fields import TagField
from masterit.tags.name_tags import make_name_tag_edits, parse_name_tags


@pytest.mark.parametrize(
    ("stem", "artist", "title"),
    [
        ("Queen - Bicycle Race", "Queen", "Bicycle Race"),
        ("Queen \u2013 Bicycle Race", "Queen", "Bicycle Race"),
        ("Queen \u2014 Bicycle Race", "Queen", "Bicycle Race"),
        ("Queen - Live - Bicycle Race", "Queen", "Live - Bicycle Race"),
        ("Jay-Z - 99 Problems", "Jay-Z", "99 Problems"),
        ("  Queen   -  Jazz  ", "Queen", "Jazz"),
    ],
)
def test_name_splits_at_the_first_spaced_dash(stem: str, artist: str, title: str):
    assert parse_name_tags(stem) == {TagField.ARTIST: artist, TagField.TITLE: title}


@pytest.mark.parametrize("stem", ["Bicycle Race", "Jay-Z-99", " - Title", "Artist - ", "-"])
def test_name_without_artist_and_title_gives_nothing(stem: str):
    assert parse_name_tags(stem) is None


def test_name_tag_edits_leave_out_unparsed_files():
    named = Path("/music/Queen - Jazz.mp3")
    edits = make_name_tag_edits([named, Path("/music/Jazz.mp3")])
    assert edits == {named: {TagField.ARTIST: "Queen", TagField.TITLE: "Jazz"}}
