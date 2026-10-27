from masterit.tagging.web.url_text import encode_path_part, encode_query


def test_encodes_queries_like_browser_forms():
    assert encode_query({"q": "AC/DC: Back in Black", "x": "a+b"}) == (
        "q=AC%2FDC%3A+Back+in+Black&x=a%2Bb"
    )


def test_replaces_lone_surrogates_as_browsers_do():
    assert encode_query({"q": "Song \ud83d"}) == "q=Song+%EF%BF%BD"
    assert encode_path_part("id\udcff") == "id%EF%BF%BD"


def test_keeps_surrogate_pairs_whole():
    assert encode_query({"q": "😀"}) == "q=%F0%9F%98%80"


def test_encodes_path_parts_like_uri_components():
    assert encode_path_part("release id/!*'()~") == "release%20id%2F!*'()~"
