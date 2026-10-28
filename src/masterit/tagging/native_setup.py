from dataclasses import dataclass, fields, replace
from importlib.metadata import PackageNotFoundError, version

from masterit.library.audio_files import list_audio_files
from masterit.tagging.metadata.album_resolver import AlbumResolver, AlbumSourceOrder
from masterit.tagging.metadata.metadata_chain import MetadataChain
from masterit.tagging.metadata.providers.deezer import DeezerProvider
from masterit.tagging.metadata.providers.deezer_album import DeezerAlbumSource
from masterit.tagging.metadata.providers.deezer_client import DeezerClient
from masterit.tagging.metadata.providers.deezer_cover import DeezerCoverProvider
from masterit.tagging.metadata.providers.discogs import (
    DiscogsAlbumProvider,
    DiscogsProvider,
    DiscogsTrackFinder,
)
from masterit.tagging.metadata.providers.discogs_album import DiscogsAlbumSource
from masterit.tagging.metadata.providers.discogs_client import DiscogsClient, DiscogsCredentials
from masterit.tagging.metadata.providers.itunes import ItunesProvider
from masterit.tagging.metadata.providers.lastfm import LastFmProvider
from masterit.tagging.metadata.providers.listenbrainz import ListenBrainzProvider
from masterit.tagging.metadata.providers.listenbrainz_client import (
    ListenBrainzClient,
    ListenBrainzCredentials,
)
from masterit.tagging.metadata.providers.musicbrainz import MusicBrainzProvider
from masterit.tagging.metadata.providers.musicbrainz_album import MusicBrainzAlbumSource
from masterit.tagging.metadata.providers.musicbrainz_client import MusicBrainzClient
from masterit.tagging.metadata.providers.youtube import YouTubeCoverProvider
from masterit.tagging.metadata.types import (
    AlbumSource,
    CoverProvider,
    MetadataProvider,
    ProviderServices,
)
from masterit.tagging.processing.native_tagger import NativeTagger
from masterit.tagging.stop_guard import StopGuard, StoppableClock, StoppableTransport
from masterit.tagging.track_tags import TrackTagStore
from masterit.tagging.web.batch_cache import BatchCache
from masterit.tagging.web.images import ImageCache
from masterit.tagging.web.transport import HttpTransport, UrllibTransport


# MusicBrainz throttles anonymous clients; a per-install id sets this one apart.
def get_default_user_agent(client_id: str) -> str:
    return f"{get_app_name()} ( {client_id} )"


def get_app_name() -> str:
    try:
        return f"MasterIt/{version('masterit')}"
    except PackageNotFoundError:
        return "MasterIt"


# Each service is left out while its key is missing; Deezer and iTunes need none.
@dataclass(frozen=True)
class TaggerKeys:
    musicbrainz_user_agent: str = ""
    listenbrainz_token: str = ""
    discogs_key: str = ""
    discogs_secret: str = ""
    lastfm_api_key: str = ""
    youtube_api_key: str = ""

    def make_trimmed(self) -> TaggerKeys:
        return replace(
            self, **{field.name: getattr(self, field.name).strip() for field in fields(self)}
        )


@dataclass(frozen=True)
class MetadataLookups:
    chain: MetadataChain
    albums: AlbumResolver


# Providers of one service share its client, and so its rate limit and cache.
@dataclass(frozen=True)
class ServiceClients:
    deezer: DeezerClient
    musicbrainz: MusicBrainzClient
    discogs: DiscogsClient | None


def make_discogs_client(keys: TaggerKeys, services: ProviderServices) -> DiscogsClient | None:
    if not (keys.discogs_key and keys.discogs_secret):
        return None
    return DiscogsClient(DiscogsCredentials(keys.discogs_key, keys.discogs_secret), services)


def make_clients(keys: TaggerKeys, services: ProviderServices) -> ServiceClients:
    return ServiceClients(
        DeezerClient(services),
        MusicBrainzClient(keys.musicbrainz_user_agent, services),
        make_discogs_client(keys, services),
    )


# MusicBrainz searches and ListenBrainz release lookups share one rate limit.
def make_brainz_providers(
    keys: TaggerKeys, clients: ServiceClients, services: ProviderServices
) -> list[MetadataProvider]:
    user_agent = keys.musicbrainz_user_agent
    if not user_agent:
        return []
    musicbrainz = MusicBrainzProvider(clients.musicbrainz, services)
    if not keys.listenbrainz_token:
        return [musicbrainz]
    credentials = ListenBrainzCredentials(keys.listenbrainz_token, user_agent)
    listenbrainz = ListenBrainzClient(credentials, services)
    return [ListenBrainzProvider(listenbrainz, clients.musicbrainz, services), musicbrainz]


def make_discogs_providers(
    clients: ServiceClients, services: ProviderServices
) -> tuple[list[MetadataProvider], list[MetadataProvider]]:
    if clients.discogs is None:
        return ([], [])
    finder = DiscogsTrackFinder(clients.discogs, services)
    return ([DiscogsAlbumProvider(finder)], [DiscogsProvider(finder)])


def make_other_providers(keys: TaggerKeys, services: ProviderServices) -> list[MetadataProvider]:
    lastfm = [LastFmProvider(keys.lastfm_api_key, services)] if keys.lastfm_api_key else []
    return [ItunesProvider(services), *lastfm]


# Discogs checks the album first, and searches songs with no album after Deezer.
def order_providers(
    keys: TaggerKeys, clients: ServiceClients, services: ProviderServices
) -> list[MetadataProvider]:
    album_discogs, song_discogs = make_discogs_providers(clients, services)
    return [
        *album_discogs,
        *make_brainz_providers(keys, clients, services),
        DeezerProvider(clients.deezer, services),
        *song_discogs,
        *make_other_providers(keys, services),
    ]


def make_cover_providers(
    keys: TaggerKeys, clients: ServiceClients, services: ProviderServices
) -> list[CoverProvider]:
    youtube = [YouTubeCoverProvider(keys.youtube_api_key, services)] if keys.youtube_api_key else []
    return [DeezerCoverProvider(clients.deezer, services), *youtube]


# Deezer has the best covers, Discogs masters and MusicBrainz the original years.
def make_album_resolver(
    keys: TaggerKeys, clients: ServiceClients, services: ProviderServices
) -> AlbumResolver:
    deezer: list[AlbumSource] = [DeezerAlbumSource(clients.deezer)]
    musicbrainz = (
        [MusicBrainzAlbumSource(clients.musicbrainz)] if keys.musicbrainz_user_agent else []
    )
    discogs = [DiscogsAlbumSource(clients.discogs)] if clients.discogs else []
    order = AlbumSourceOrder(
        identity=[*deezer, *musicbrainz, *discogs],
        year=[*discogs, *musicbrainz, *deezer],
        genre=[*deezer, *discogs],
        tracks=[*discogs, *deezer],
        cover=[*deezer, *musicbrainz, *discogs],
    )
    return AlbumResolver(order, services)


def make_metadata_lookups(keys: TaggerKeys, services: ProviderServices) -> MetadataLookups:
    trimmed = keys.make_trimmed()
    clients = make_clients(trimmed, services)
    chain = MetadataChain(
        order_providers(trimmed, clients, services),
        make_cover_providers(trimmed, clients, services),
        services,
    )
    return MetadataLookups(chain, make_album_resolver(trimmed, clients, services))


def make_native_tagger(keys: TaggerKeys, transport: HttpTransport | None = None) -> NativeTagger:
    guard = StopGuard()
    web = StoppableTransport(transport or UrllibTransport(), guard)
    services = ProviderServices(StoppableClock(guard), web, ImageCache(web), BatchCache())
    lookups = make_metadata_lookups(keys, services)
    return NativeTagger(lookups.chain, lookups.albums, TrackTagStore(), list_audio_files, guard)
