import pytest

from masterit.library.rename_rules import AddPrefix, AddSuffix, RemoveText, SetName


@pytest.mark.parametrize(
    ("text", "stem", "expected"),
    [
        ("Official Video", "Song (Official Video)", "Song"),
        ("official video", "Song [OFFICIAL VIDEO] Live", "Song Live"),
        ("Artist", "Artist - Song", "Song"),
        ("feat. X", "Song feat. X - Remix", "Song - Remix"),
        ("x", "Song", "Song"),
        ("", "Song  -", "Song  -"),
        ("a.b", "Song axb", "Song axb"),
        ("official", "Song (Official) -_-", "Song -_-"),
        ("live", "_Intro_ (Live)", "_Intro_"),
        ("remix", "Song () Remix", "Song ()"),
        ("official video", "Song (Official Video 2009)", "Song (2009)"),
        ("x", "AxB", "AB"),
        ("ab", "ab ab Song", "Song"),
        ("lyrics", "Title (Lyrics) Lyrics", "Title"),
        ("lyrics", "Lyrics (Lyrics) Title", "Title"),
        ("official video", "Title \uff5c Official Video", "Title"),
        ("b", "A - B - C", "A - C"),
        ("official video", "Title \uff5c Official Video \uff5c 4K", "Title \uff5c 4K"),
        ("official", "Song_Official_Video", "Song_Video"),
    ],
)
def test_remove_text_ignores_case_and_tidies(text: str, stem: str, expected: str):
    assert RemoveText(text).make_name(stem) == expected


def test_prefix_and_suffix_are_added_as_is():
    assert AddPrefix("Artist - ").make_name("Song") == "Artist - Song"
    assert AddSuffix(" (Live)").make_name("Song") == "Song (Live)"


def test_set_name_replaces_name_trimmed():
    assert SetName("  New Song ").make_name("Old") == "New Song"


@pytest.mark.parametrize(
    ("text", "stem", "expected"),
    [
        ("AC/DC", "AC\u29f8DC - Song", "Song"),
        ("Live: 1979", "Song (Live\uff1a 1979)", "Song"),
        ("| Lyrics", "Song \uff5c Lyrics", "Song"),
        ('"Best"', "Song \uff02Best\uff02", "Song"),
        ("Why? *", "Song Why\uff1f \uff0a", "Song"),
        ("<HD>", "Song \uff1cHD\uff1e", "Song"),
        ("a\\b", "Song a\u29f9b", "Song"),
        ("Why\uff1f", "Song Why?", "Song"),
        ("(Official Video)", "Song\u00a0(Official\u00a0Video)", "Song"),
        ("Official  Video", "Song (Official Video)", "Song"),
    ],
)
def test_removal_matches_file_name_lookalikes_and_spaces(text: str, stem: str, expected: str):
    assert RemoveText(text).make_name(stem) == expected


@pytest.mark.parametrize(
    ("text", "stem", "expected"),
    [
        ("Video ", "Song Video", "Song"),
        ("   ", "Song  -  Live", "Song  -  Live"),
    ],
)
def test_removal_ignores_spaces_around_the_text(text: str, stem: str, expected: str):
    assert RemoveText(text).make_name(stem) == expected


@pytest.mark.parametrize(
    ("text", "stem", "expected"),
    [
        ("Artist", "Artist \u29f8 Song", "Song"),
        ("Live", "Song \uff1a Live", "Song"),
        ("Live", "Song \u29f8 Live \uff1a 1979", "Song \uff1a 1979"),
        ("Song", "AC\u29f8DC - Song", "AC\u29f8DC"),
        ("Live", "Song - Live\uff1a1979", "Song\uff1a1979"),
    ],
)
def test_removal_takes_lookalike_separators_along(text: str, stem: str, expected: str):
    assert RemoveText(text).make_name(stem) == expected
