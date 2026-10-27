from masterit.tagging.metadata.album_tracklist import (
    TrackNames,
    TrackPlace,
    build_tracklist,
    find_tracklist_entry,
)
from masterit.tagging.metadata.types import AlbumTrackEntry

JAZZ = build_tracklist(
    [
        TrackPlace("Mustapha", 1, 1),
        TrackPlace("Bicycle Race", 1, 2),
        TrackPlace("Mustapha", 2, 1),
    ]
)


def test_counts_the_tracks_of_each_disc_and_the_discs():
    places = [TrackPlace("A", 1, 1), TrackPlace("B", 2, 1), TrackPlace("C", 2, 2)]
    assert build_tracklist(places) == [
        AlbumTrackEntry("A", 1, 1, 1, 2),
        AlbumTrackEntry("B", 1, 2, 2, 2),
        AlbumTrackEntry("C", 2, 2, 2, 2),
    ]
    assert build_tracklist([]) == []


def test_keeps_each_track_artist():
    assert build_tracklist([TrackPlace("A", 1, 1, "X")])[0].artist == "X"


def test_gives_nothing_when_two_tracks_share_a_place():
    assert build_tracklist([TrackPlace("A", 1, 1), TrackPlace("B", 1, 1)]) == []


def test_matches_one_of_the_titles_ignoring_case_and_notes():
    entry = find_tracklist_entry(JAZZ, TrackNames(["", "bicycle race (2011 remaster)"], None))
    assert entry is not None
    assert entry.track_number == 2
    assert find_tracklist_entry(JAZZ, TrackNames(["Fat Bottomed Girls"], None)) is None


def test_prefers_the_entry_of_the_track_disc():
    second = find_tracklist_entry(JAZZ, TrackNames(["Mustapha"], 2))
    first = find_tracklist_entry(JAZZ, TrackNames(["Mustapha"], None))
    assert second is not None
    assert first is not None
    assert (second.disc_number, first.disc_number) == (2, 1)


def test_takes_no_entry_of_another_disc():
    assert find_tracklist_entry(JAZZ, TrackNames(["Bicycle Race"], 2)) is None
