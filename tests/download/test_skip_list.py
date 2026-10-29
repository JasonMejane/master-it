from masterit.download.skip_list import SkipList


def test_new_list_skips_nothing():
    assert not SkipList().is_skipped("a", "id1")


def test_skipped_item_is_skipped_only_for_its_link():
    skip_list = SkipList()
    skip_list.set_skipped("a", "id1", True)
    assert skip_list.is_skipped("a", "id1")
    assert not skip_list.is_skipped("b", "id1")
    assert not skip_list.is_skipped("a", "id2")


def test_unskipped_item_is_downloaded_again():
    skip_list = SkipList()
    skip_list.set_skipped("a", "id1", True)
    skip_list.set_skipped("a", "id1", False)
    assert not skip_list.is_skipped("a", "id1")


def test_skipped_link_does_not_skip_its_items():
    skip_list = SkipList()
    skip_list.set_skipped("a", None, True)
    assert skip_list.is_skipped("a", None)
    assert not skip_list.is_skipped("a", "id1")
