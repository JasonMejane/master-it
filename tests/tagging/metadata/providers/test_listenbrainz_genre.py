from typing import Any

import pytest

from masterit.tagging.metadata.providers.listenbrainz_genre import pick_genre

GENRE = "genre-id"


def test_takes_the_most_voted_genre_of_the_recording():
    tags = {
        "recording": [
            {"tag": "electronic", "count": 7, "genre_mbid": GENRE},
            {"tag": "house", "count": 9, "genre_mbid": GENRE},
            {"tag": "club/dance", "count": 20},
        ],
        "release_group": [{"tag": "trip-hop", "count": 50, "genre_mbid": GENRE}],
    }
    assert pick_genre(tags) == "House"


def test_keeps_the_first_of_equally_voted_genres():
    tags = {"recording": [{"tag": "a", "genre_mbid": GENRE}, {"tag": "b", "genre_mbid": GENRE}]}
    assert pick_genre(tags) == "A"


def test_falls_back_to_the_album_then_the_artist():
    artist = [{"tag": "progressive rock", "count": 59, "genre_mbid": GENRE}]
    tags: dict[str, Any] = {
        "recording": [{"tag": "favourite", "count": 3}],
        "release_group": [{"tag": "art rock", "genre_mbid": GENRE}],
        "artist": artist,
    }
    assert pick_genre(tags) == "Art Rock"
    assert pick_genre({"recording": [], "artist": artist}) == "Progressive Rock"


def test_writes_every_word_in_title_case():
    assert pick_genre({"artist": [{"tag": "hip-hop soul", "genre_mbid": GENRE}]}) == "Hip-Hop Soul"


def test_gives_nothing_without_a_genre_tag():
    assert pick_genre({"artist": [{"tag": "british", "count": 14}]}) is None
    assert pick_genre({}) is None


@pytest.mark.parametrize(
    ("tag", "genre"),
    [("r&b", "R&B"), ("uk garage", "UK Garage"), ("edm", "EDM"), ("rock/pop", "Rock/Pop")],
)
def test_keeps_acronyms_and_joined_genres_readable(tag: str, genre: str):
    assert pick_genre({"artist": [{"tag": tag, "genre_mbid": GENRE}]}) == genre
