from typing import Any

from masterit.tagging.metadata.providers.discogs import DiscogsTrackFinder
from masterit.tagging.metadata.providers.discogs_client import DiscogsClient, DiscogsCredentials

from ...web.fakes import FakeTransport, FakeWeb
from ..fakes import make_services

DISCOGS_COVER = "https://i.discogs.test/cover.jpg"


def make_discogs_web(responses: dict[str, Any]) -> FakeWeb:
    return FakeWeb("api.discogs.com", responses, missing={"results": []})


def make_discogs_client(web: FakeWeb) -> DiscogsClient:
    return DiscogsClient(
        DiscogsCredentials("consumer-key", "consumer-secret"), make_services(web.transport)
    )


def make_finder(web: FakeWeb) -> DiscogsTrackFinder:
    return make_finder_on(web.transport)


def make_finder_on(transport: FakeTransport) -> DiscogsTrackFinder:
    services = make_services(transport)
    client = DiscogsClient(DiscogsCredentials("key", "secret"), services)
    return DiscogsTrackFinder(client, services)
