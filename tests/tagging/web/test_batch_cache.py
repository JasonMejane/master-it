import pytest

from masterit.tagging.web.batch_cache import BatchCache


def test_loads_a_key_once():
    cache = BatchCache()
    loads: list[str] = []

    def load() -> str:
        loads.append("load")
        return "value"

    assert cache.get_or_load("key", load) == "value"
    assert cache.get_or_load("key", load) == "value"
    assert loads == ["load"]


def test_keeps_none_results():
    cache = BatchCache()
    loads: list[str] = []

    def load() -> None:
        loads.append("load")

    cache.get_or_load("key", load)
    cache.get_or_load("key", load)
    assert loads == ["load"]


def test_does_not_keep_failures():
    cache = BatchCache()

    def fail() -> str:
        raise RuntimeError("failed")

    with pytest.raises(RuntimeError):
        cache.get_or_load("key", fail)
    assert cache.get_or_load("key", lambda: "value") == "value"


def test_clear_forgets_values():
    cache = BatchCache()
    cache.get_or_load("key", lambda: "old")
    cache.clear()
    assert cache.get_or_load("key", lambda: "new") == "new"
