from masterit.download.url_input import parse_urls


def test_parse_urls_splits_on_lines_and_spaces():
    text = "https://a.example/1\n  https://a.example/2 https://a.example/3\n"
    assert parse_urls(text) == ["https://a.example/1", "https://a.example/2", "https://a.example/3"]


def test_parse_urls_ignores_blank_input():
    assert parse_urls(" \n\t\n") == []


def test_parse_urls_removes_duplicates_keeping_order():
    text = "https://a.example/2\nhttps://a.example/1\nhttps://a.example/2"
    assert parse_urls(text) == ["https://a.example/2", "https://a.example/1"]
