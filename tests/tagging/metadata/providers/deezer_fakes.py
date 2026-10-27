from typing import Any

from masterit.tagging.metadata.providers.deezer_client import DeezerClient
from masterit.tagging.metadata.types import ProviderServices

from ...web.fakes import FakeClock, FakeWeb
from ..fakes import make_services

DEEZER_COVER_XL = "https://cdn.deezer.test/1000x1000.jpg"


def make_deezer_web(responses: dict[str, Any]) -> FakeWeb:
    return FakeWeb("api.deezer.com", responses, missing={"data": []})


def make_deezer_services(web: FakeWeb, clock: FakeClock | None = None) -> ProviderServices:
    return make_services(web.transport, clock)


def make_deezer_client(web: FakeWeb, clock: FakeClock | None = None) -> DeezerClient:
    return DeezerClient(make_deezer_services(web, clock))
