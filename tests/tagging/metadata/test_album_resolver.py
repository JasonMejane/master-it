import urllib.parse

import pytest

from masterit.tagging.metadata.album_resolver import AlbumResolver, AlbumSourceOrder
from masterit.tagging.metadata.types import AlbumData, AlbumSearch, AlbumTrackEntry, FoundAlbum
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ..web.fakes import FakeTransport, make_image_response
from .fakes import make_services

SEARCH = AlbumSearch("Queen", "jazz")
TRACKS = [AlbumTrackEntry("Mustapha", 1, 13, 1, 1)]


class FakeAlbumSource:
    def __init__(self, name: str, found: FoundAlbum | Exception | None) -> None:
        self.name = name
        self.found = found
        self.searches: list[AlbumSearch] = []

    def find_album(self, search: AlbumSearch) -> FoundAlbum | None:
        self.searches.append(search)
        if isinstance(self.found, Exception):
            raise self.found
        return self.found


def make_covers(name: str) -> list[ImageRequest]:
    return [ImageRequest(f"https://covers.test/{name}.jpg")]


def serve_images(missing: tuple[str, ...] = ()) -> FakeTransport:
    def answer(request: HttpRequest) -> HttpResponse:
        path = urllib.parse.urlsplit(request.url).path
        return (
            HttpResponse(404, {}, b"")
            if path in missing
            else make_image_response(f"image {path}".encode())
        )

    return FakeTransport(answer)


class Sources:
    def __init__(
        self,
        deezer: FakeAlbumSource | None = None,
        musicbrainz: FakeAlbumSource | None = None,
        discogs: FakeAlbumSource | None = None,
    ) -> None:
        self.deezer = deezer or FakeAlbumSource(
            "Deezer", FoundAlbum("Jazz", "Queen", "2011", "Rock", make_covers("deezer"))
        )
        self.musicbrainz = musicbrainz or FakeAlbumSource(
            "MusicBrainz", FoundAlbum("Jazz", "Queen", "1978", covers=make_covers("musicbrainz"))
        )
        self.discogs = discogs or FakeAlbumSource(
            "Discogs", FoundAlbum("JAZZ", "Queen", genre="Pop", tracks=TRACKS)
        )

    def make_resolver(self, transport: FakeTransport | None = None) -> AlbumResolver:
        deezer, musicbrainz, discogs = self.deezer, self.musicbrainz, self.discogs
        order = AlbumSourceOrder(
            identity=[deezer, musicbrainz, discogs],
            year=[discogs, musicbrainz, deezer],
            genre=[deezer, discogs],
            tracks=[discogs, deezer],
            cover=[deezer, musicbrainz, discogs],
        )
        return AlbumResolver(order, make_services(transport or serve_images()))


def test_takes_each_field_from_the_first_source_that_has_it():
    assert Sources().make_resolver().resolve(SEARCH) == AlbumData(
        "Jazz", "Queen", "1978", "Rock", b"image /deezer.jpg", TRACKS, True
    )


def test_asks_each_source_once_and_only_while_a_field_needs_it():
    discogs = FakeAlbumSource("Discogs", FoundAlbum("Jazz", "Queen", "1978", tracks=TRACKS))
    sources = Sources(discogs=discogs)
    sources.make_resolver().resolve(SEARCH)
    searches = [
        len(source.searches) for source in (sources.deezer, sources.discogs, sources.musicbrainz)
    ]
    assert searches == [1, 1, 0]


def test_keeps_an_album_for_the_batch_whatever_its_letter_case():
    sources = Sources()
    resolver = sources.make_resolver()
    first = resolver.resolve(SEARCH)
    assert resolver.resolve(AlbumSearch("QUEEN", " Jazz")) is first
    assert len(sources.deezer.searches) == 1


def test_takes_the_next_cover_when_one_cannot_be_downloaded():
    album = Sources().make_resolver(serve_images(("/deezer.jpg",))).resolve(SEARCH)
    assert album.cover == b"image /musicbrainz.jpg"


def test_goes_on_without_a_failing_source():
    album = (
        Sources(deezer=FakeAlbumSource("Deezer", ServiceError("down")))
        .make_resolver()
        .resolve(SEARCH)
    )
    assert (album.album, album.genre, album.cover) == ("Jazz", "Pop", b"image /musicbrainz.jpg")


def test_falls_back_to_the_folder_names_when_no_source_has_the_album():
    none = FakeAlbumSource("None", None)
    resolver = Sources(none, none, none).make_resolver()
    assert resolver.resolve(SEARCH) == AlbumData("jazz", "Queen", "", "", None, [], False)


def test_lets_other_errors_through():
    resolver = Sources(deezer=FakeAlbumSource("Deezer", TypeError("bug"))).make_resolver()
    with pytest.raises(TypeError, match="bug"):
        resolver.resolve(SEARCH)


def test_skips_an_empty_tracklist_and_leaves_an_unknown_year_empty():
    sources = Sources(
        deezer=FakeAlbumSource("Deezer", FoundAlbum("Jazz", "Queen", tracks=TRACKS)),
        musicbrainz=FakeAlbumSource("MusicBrainz", None),
        discogs=FakeAlbumSource("Discogs", FoundAlbum("Jazz", "Queen", tracks=[])),
    )
    album = sources.make_resolver().resolve(SEARCH)
    assert (album.tracks, album.year, album.cover) == (TRACKS, "", None)


def test_prefers_the_tracklist_that_fits_the_folder_file_count():
    longer = [*TRACKS, AlbumTrackEntry("Bonus", 2, 13, 1, 1)]
    deezer = FakeAlbumSource("Deezer", FoundAlbum("Jazz (2011 Remaster)", "Queen", tracks=longer))
    album = Sources(deezer=deezer).make_resolver().resolve(SEARCH, 2)
    assert (album.album, album.tracks, album.genre) == ("Jazz", longer, "Pop")


def test_takes_the_first_tracklist_when_none_fits_the_folder():
    assert Sources().make_resolver().resolve(SEARCH, 5).tracks == TRACKS


def test_keeps_an_album_for_the_batch_whatever_its_unicode_form():
    sources = Sources()
    resolver = sources.make_resolver()
    first = resolver.resolve(AlbumSearch("Beyonce\u0301", "Lemonade"))
    assert resolver.resolve(AlbumSearch("Beyoncé", "Lemonade")) is first
