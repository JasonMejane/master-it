from typing import Any

from masterit.tagging.metadata.providers.musicbrainz_release import (
    get_first_release_year,
    get_track_position_extras,
)
from masterit.tagging.metadata.types import TrackExtras

THE_WALL: dict[str, Any] = {
    "release-group": {"first-release-date": "1979-11-30"},
    "media": [
        {
            "position": 1,
            "track-count": 13,
            "tracks": [{"position": 1, "recording": {"id": "in-the-flesh"}}],
        },
        {
            "position": 2,
            "track-count": 13,
            "tracks": [
                {"position": 5, "recording": {"id": "vera"}},
                {
                    "position": 6,
                    "recording": {"id": "comfortably-numb", "first-release-date": "1979-11-30"},
                },
            ],
        },
    ],
}


def test_finds_the_track_and_disc_of_a_recording():
    assert get_track_position_extras(THE_WALL, "comfortably-numb") == TrackExtras(
        track_number=6, track_count=13, disc_number=2, disc_count=2
    )


def test_gives_nothing_for_a_recording_not_on_the_release():
    assert get_track_position_extras(THE_WALL, "other") == TrackExtras()
    assert get_track_position_extras({}, "vera") == TrackExtras()


def test_leaves_out_unknown_positions():
    sparse = {"media": [{"tracks": [{"recording": {"id": "vera"}}]}]}
    assert get_track_position_extras(sparse, "vera") == TrackExtras(disc_count=1)


def test_takes_the_recording_first_release_on_a_compilation():
    compilation = {**THE_WALL, "release-group": {"first-release-date": "2010"}}
    assert get_first_release_year(compilation, "comfortably-numb") == "1979"
    assert get_first_release_year({}, "vera") == ""


def test_takes_the_album_first_release_for_a_remastered_recording():
    remaster = {
        "release-group": {"first-release-date": "1979-11-30"},
        "media": [
            {"tracks": [{"recording": {"id": "remastered-numb", "first-release-date": "1984-09"}}]}
        ],
    }
    assert get_first_release_year(remaster, "remastered-numb") == "1979"
    assert get_first_release_year(THE_WALL, "vera") == "1979"
