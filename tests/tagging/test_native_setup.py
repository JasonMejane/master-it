from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from masterit.cancellation import CancelToken
from masterit.tagging import native_setup
from masterit.tagging.events import AutoTagStatus, FileAutoTagged, TaggerEvent
from masterit.tagging.metadata.types import ProviderServices
from masterit.tagging.native_setup import (
    TaggerKeys,
    get_default_user_agent,
    make_metadata_lookups,
    make_native_tagger,
)
from masterit.tagging.web.batch_cache import BatchCache
from masterit.tagging.web.images import ImageCache
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ..tags.fixtures import copy_fixture
from .web.fakes import FakeClock, FakeTransport, make_json_response

ALL_KEYS = TaggerKeys(" MasterIt/1.0 ", "token", "key", "secret", "lastfm", "youtube")


def make_services() -> ProviderServices:
    transport = FakeTransport(lambda _request: make_json_response({}))
    return ProviderServices(FakeClock(), transport, ImageCache(transport), BatchCache())


def test_orders_every_service_like_the_album_first_chain():
    lookups = make_metadata_lookups(ALL_KEYS, make_services())
    assert [provider.name for provider in lookups.chain.providers] == [
        "Discogs",
        "ListenBrainz",
        "MusicBrainz",
        "Deezer",
        "Discogs",
        "iTunes",
        "Last.fm",
    ]
    assert [provider.name for provider in lookups.chain.cover_providers] == ["Deezer", "YouTube"]
    order = lookups.albums.order
    assert [source.name for source in order.identity] == ["Deezer", "MusicBrainz", "Discogs"]
    assert [source.name for source in order.year] == ["Discogs", "MusicBrainz", "Deezer"]
    assert [source.name for source in order.genre] == ["Deezer", "Discogs"]
    assert [source.name for source in order.tracks] == ["Discogs", "Deezer"]
    assert [source.name for source in order.cover] == ["Deezer", "MusicBrainz", "Discogs"]


def test_leaves_out_the_services_whose_keys_are_missing_or_blank():
    keys = TaggerKeys(musicbrainz_user_agent=" ", listenbrainz_token="token", discogs_key="key")
    lookups = make_metadata_lookups(keys, make_services())
    assert [provider.name for provider in lookups.chain.providers] == ["Deezer", "iTunes"]
    assert [provider.name for provider in lookups.chain.cover_providers] == ["Deezer"]
    assert [source.name for source in lookups.albums.order.identity] == ["Deezer"]


def test_keeps_listenbrainz_out_without_a_token():
    keys = TaggerKeys(musicbrainz_user_agent="MasterIt/1.0")
    lookups = make_metadata_lookups(keys, make_services())
    assert [provider.name for provider in lookups.chain.providers] == [
        "MusicBrainz",
        "Deezer",
        "iTunes",
    ]


def test_makes_a_tagger_that_skips_a_song_no_service_knows(tmp_path: Path):
    song = copy_fixture(tmp_path, "mp3", "Nobody - Nothing")
    requests: list[HttpRequest] = []

    def answer(request: HttpRequest) -> HttpResponse:
        requests.append(request)
        return make_json_response({})

    tagger = make_native_tagger(TaggerKeys("MasterIt/1.0"), FakeTransport(answer))
    events: list[TaggerEvent] = []
    tagger.tag([song], events.append, CancelToken())
    assert FileAutoTagged(song, AutoTagStatus.SKIPPED, "not found") in events
    assert requests


def test_the_default_user_agent_names_the_app_its_version_and_repository():
    agent = get_default_user_agent()
    assert agent.startswith("MasterIt/")
    assert agent.endswith("( https://github.com/JasonMejane/master-it )")


def test_the_default_user_agent_falls_back_without_an_installed_package(
    monkeypatch: pytest.MonkeyPatch,
):
    def fail(_name: str) -> str:
        raise PackageNotFoundError("masterit")

    monkeypatch.setattr(native_setup, "version", fail)
    assert get_default_user_agent() == "MasterIt ( https://github.com/JasonMejane/master-it )"
