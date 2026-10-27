import pytest

from masterit.tagging.metadata.metadata_chain import MetadataChain
from masterit.tagging.metadata.types import (
    ExistingTags,
    ProviderNeeds,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.images import ImageRequest

from ..web.fakes import FakeTransport, make_image_response
from .fakes import FakeCoverProvider, FakeMetadataProvider, make_services

SEARCH = TrackSearch("Query", "Artist", "")
COVER = b"cover"
NO_TAGS = ExistingTags()
WITH_COVER = ExistingTags(has_cover=True)
REQUIRED_EXTRAS = TrackExtras(genre="Rock", track_number=1)
COMPLETE_INFO = TrackInfo("T", "A", "B", "2000")


def make_chain(
    providers: list[FakeMetadataProvider], cover_providers: list[FakeCoverProvider] | None = None
) -> MetadataChain:
    return MetadataChain(providers, cover_providers or [], make_services())


class BrokenProvider:
    name = "Broken"

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        raise ServiceError("Broken request failed: HTTP 500")


class BuggyProvider:
    name = "Buggy"

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        raise KeyError("bug")


class BrokenCoverProvider:
    name = "BrokenCover"

    def find_cover(self, search: TrackSearch) -> bytes | None:
        raise ServiceError("timed out")


def test_returns_none_without_asking_for_a_cover_when_nothing_matches():
    cover_provider = FakeCoverProvider(COVER)
    chain = make_chain([FakeMetadataProvider(None), FakeMetadataProvider(None)], [cover_provider])
    assert chain.find(SEARCH, NO_TAGS) is None
    assert cover_provider.searches == []


def test_fills_missing_fields_in_provider_order_without_overwriting():
    chain = make_chain(
        [
            FakeMetadataProvider(TrackMetadata(TrackInfo("First"))),
            FakeMetadataProvider(
                TrackMetadata(TrackInfo("Second", "Second", "Album"), cover_data=COVER)
            ),
        ]
    )
    existing = ExistingTags(TrackInfo(year="2020"))
    assert chain.find(SEARCH, existing) == TrackMetadata(
        TrackInfo("First", "Second", "Album", "2020"), TrackExtras(), COVER
    )


def test_stops_asking_providers_once_metadata_is_complete():
    last = FakeMetadataProvider(None)
    complete = TrackMetadata(COMPLETE_INFO, REQUIRED_EXTRAS, COVER)
    make_chain([FakeMetadataProvider(complete), last]).find(SEARCH, NO_TAGS)
    assert last.calls == []


def test_searches_with_collected_info_and_only_requests_missing_covers():
    first = FakeMetadataProvider(TrackMetadata(TrackInfo("Found title"), cover_data=COVER))
    second = FakeMetadataProvider(None)
    make_chain([first, second]).find(SEARCH, NO_TAGS)
    assert first.calls == [(SEARCH, ProviderNeeds(cover=True, details=True))]
    assert second.calls == [
        (TrackSearch("Found title", "Artist", ""), ProviderNeeds(cover=False, details=True))
    ]


def test_asks_for_details_until_the_year_and_every_extra_are_known():
    provider = FakeMetadataProvider(None)
    chain = make_chain([provider])
    all_extras = TrackExtras(genre="Rock", album_artist="Artist", track_number=1, disc_number=1)
    chain.find(SEARCH, ExistingTags(TrackInfo(year="2000"), all_extras))
    chain.find(SEARCH, ExistingTags(TrackInfo(), all_extras))
    no_disc = TrackExtras(genre="Rock", album_artist="Artist", track_number=1)
    chain.find(SEARCH, ExistingTags(TrackInfo(year="2000"), no_disc))
    assert [needs.details for _search, needs in provider.calls] == [False, True, True]


def test_uses_cover_providers_only_when_matched_metadata_lacks_a_cover():
    cover_provider = FakeCoverProvider(COVER)
    chain = make_chain([FakeMetadataProvider(TrackMetadata(TrackInfo("Found")))], [cover_provider])
    metadata = chain.find(SEARCH, NO_TAGS)
    assert metadata is not None
    assert metadata.cover_data == COVER
    assert cover_provider.searches == [TrackSearch("Found", "Artist", "")]


def test_skips_cover_providers_when_a_cover_was_found():
    cover_provider = FakeCoverProvider(b"other")
    found = TrackMetadata(TrackInfo("Found"), cover_data=COVER)
    metadata = make_chain([FakeMetadataProvider(found)], [cover_provider]).find(SEARCH, NO_TAGS)
    assert metadata is not None
    assert metadata.cover_data == COVER
    assert cover_provider.searches == []


def test_tries_cover_providers_in_order_until_one_finds_a_cover():
    cover_providers = [FakeCoverProvider(None), FakeCoverProvider(COVER), FakeCoverProvider(b"x")]
    chain = make_chain([FakeMetadataProvider(TrackMetadata(TrackInfo("Query")))], cover_providers)
    metadata = chain.find(SEARCH, NO_TAGS)
    assert metadata is not None
    assert metadata.cover_data == COVER
    assert [len(provider.searches) for provider in cover_providers] == [1, 1, 0]


def test_carries_on_after_a_failing_service():
    found = FakeMetadataProvider(TrackMetadata(TrackInfo("Query")))
    chain = MetadataChain([BrokenProvider(), found], [], make_services())
    metadata = chain.find(SEARCH, WITH_COVER)
    assert metadata is not None
    assert metadata.info.title == "Query"


def test_carries_on_after_a_failing_cover_service():
    found = FakeMetadataProvider(TrackMetadata(TrackInfo("Query")))
    chain = MetadataChain(
        [found], [BrokenCoverProvider(), FakeCoverProvider(COVER)], make_services()
    )
    metadata = chain.find(SEARCH, NO_TAGS)
    assert metadata is not None
    assert metadata.cover_data == COVER


def test_bugs_fail_the_search():
    with pytest.raises(KeyError):
        MetadataChain([BuggyProvider()], [], make_services()).find(SEARCH, NO_TAGS)


def test_keeps_existing_extras_and_fills_missing_ones():
    found = TrackMetadata(TrackInfo("Found"), TrackExtras(genre="Pop", track_number=4))
    existing = ExistingTags(extras=TrackExtras(genre="Rock"))
    metadata = make_chain([FakeMetadataProvider(found)]).find(SEARCH, existing)
    assert metadata is not None
    assert metadata.extras == TrackExtras(genre="Rock", track_number=4)


def test_keeps_an_existing_cover_without_looking_for_another():
    provider = FakeMetadataProvider(TrackMetadata(TrackInfo("Query")))
    cover_provider = FakeCoverProvider(COVER)
    metadata = make_chain([provider], [cover_provider]).find(SEARCH, WITH_COVER)
    assert metadata is not None
    assert metadata.cover_data is None
    assert not provider.calls[0][1].cover
    assert cover_provider.searches == []


def test_counts_an_existing_cover_towards_complete_metadata():
    last = FakeMetadataProvider(None)
    complete = TrackMetadata(COMPLETE_INFO, REQUIRED_EXTRAS)
    make_chain([FakeMetadataProvider(complete), last]).find(SEARCH, WITH_COVER)
    assert last.calls == []


def test_asks_providers_for_a_replacement_cover_without_a_fallback():
    provider = FakeMetadataProvider(TrackMetadata(TrackInfo("Query")))
    cover_provider = FakeCoverProvider(COVER)
    chain = make_chain([provider], [cover_provider])
    metadata = chain.find(SEARCH, WITH_COVER, replace_cover=True)
    assert metadata is not None
    assert metadata.cover_data is None
    assert provider.calls[0][1].cover
    assert cover_provider.searches == []


def test_keeps_asking_for_a_replacement_cover_after_complete_details():
    complete = TrackMetadata(TrackInfo("Query", "Artist", "Album", "2024"), REQUIRED_EXTRAS)
    second = FakeMetadataProvider(TrackMetadata(TrackInfo(), cover_data=COVER))
    chain = make_chain([FakeMetadataProvider(complete), second])
    metadata = chain.find(SEARCH, WITH_COVER, replace_cover=True)
    assert metadata is not None
    assert metadata.cover_data == COVER


def test_clear_cache_clears_the_shared_image_and_batch_caches():
    transport = FakeTransport(lambda _request: make_image_response())
    services = make_services(transport)
    services.images.download(ImageRequest("https://example.test/a.jpg"))
    services.cache.get_or_load("key", lambda: "first")
    MetadataChain([], [], services).clear_cache()
    services.images.download(ImageRequest("https://example.test/a.jpg"))
    assert len(transport.requests) == 2
    assert services.cache.get_or_load("key", lambda: "second") == "second"


def test_an_empty_cover_needs_no_other_cover():
    first = FakeMetadataProvider(TrackMetadata(TrackInfo("Query"), cover_data=b""))
    second = FakeMetadataProvider(None)
    cover_provider = FakeCoverProvider(COVER)
    metadata = make_chain([first, second], [cover_provider]).find(SEARCH, NO_TAGS)
    assert metadata is not None
    assert metadata.cover_data == b""
    assert not second.calls[0][1].cover
    assert cover_provider.searches == []
