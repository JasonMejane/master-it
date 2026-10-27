from masterit.tagging.metadata.types import (
    ProviderNeeds,
    ProviderServices,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.batch_cache import BatchCache
from masterit.tagging.web.images import ImageCache
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ..web.fakes import FakeClock, FakeTransport


class FakeMetadataProvider:
    def __init__(self, result: TrackMetadata | None, name: str = "Fake") -> None:
        self.result = result
        self.name = name
        self.calls: list[tuple[TrackSearch, ProviderNeeds]] = []

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        self.calls.append((search, needs))
        return self.result


class FakeCoverProvider:
    def __init__(self, cover: bytes | None, name: str = "FakeCover") -> None:
        self.cover = cover
        self.name = name
        self.searches: list[TrackSearch] = []

    def find_cover(self, search: TrackSearch) -> bytes | None:
        self.searches.append(search)
        return self.cover


def refuse_request(request: HttpRequest) -> HttpResponse:
    raise AssertionError(f"unexpected request: {request.url}")


def make_services(
    transport: FakeTransport | None = None, clock: FakeClock | None = None
) -> ProviderServices:
    web = transport or FakeTransport(refuse_request)
    return ProviderServices(clock or FakeClock(), web, ImageCache(web), BatchCache())
