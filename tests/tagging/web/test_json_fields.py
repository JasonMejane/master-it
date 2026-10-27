import pytest

from masterit.tagging.web.json_fields import (
    read_int,
    read_list,
    read_object,
    read_objects,
    read_text,
)

PAYLOAD = {
    "title": "Song",
    "count": 3,
    "flag": True,
    "ratio": 1.5,
    "artist": {"name": "Band"},
    "data": [{"id": 1}, "noise", {"id": 2}],
}


def test_reads_text_only_from_strings():
    assert read_text(PAYLOAD, "title") == "Song"
    assert read_text(PAYLOAD, "count") is None
    assert read_text(PAYLOAD, "missing") is None


@pytest.mark.parametrize(("key", "value"), [("count", 3), ("flag", None), ("ratio", None)])
def test_reads_whole_numbers_but_not_booleans_or_fractions(key: str, value: int | None):
    assert read_int(PAYLOAD, key) == value


def test_reads_whole_floats_as_numbers():
    assert read_int({"count": 3.0}, "count") == 3


def test_reads_objects_or_an_empty_one():
    assert read_object(PAYLOAD, "artist") == {"name": "Band"}
    assert read_object(PAYLOAD, "title") == {}
    assert read_object(PAYLOAD, "missing") == {}


def test_reads_lists_or_an_empty_one():
    assert read_list(PAYLOAD, "data") == [{"id": 1}, "noise", {"id": 2}]
    assert read_list(PAYLOAD, "artist") == []


def test_reads_only_the_objects_of_a_list():
    assert read_objects(PAYLOAD, "data") == [{"id": 1}, {"id": 2}]
    assert read_objects(PAYLOAD, "missing") == []
