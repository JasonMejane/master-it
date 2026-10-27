import pytest

from masterit.tagging.web.errors import HttpStatusError, ServiceError
from masterit.tagging.web.images import ImageCache, ImageRequest, download_image
from masterit.tagging.web.transport import (
    IMAGE_TIMEOUT_SECONDS,
    HttpRequest,
    HttpResponse,
)

from .fakes import FakeTransport, make_image_response

COVER = "https://example.test/cover.jpg"


def serve_image(_request: HttpRequest) -> HttpResponse:
    return make_image_response(b"image-bytes")


def serve_missing(_request: HttpRequest) -> HttpResponse:
    return make_image_response(b"", status=404)


def test_download_returns_bytes_and_sends_headers_limit_and_image_timeout():
    transport = FakeTransport(serve_image)
    image = download_image(transport, ImageRequest(COVER, {"User-Agent": "MasterIt"}, 10))
    assert image == b"image-bytes"
    assert transport.requests == [
        HttpRequest(COVER, {"User-Agent": "MasterIt"}, IMAGE_TIMEOUT_SECONDS, 10)
    ]
    assert IMAGE_TIMEOUT_SECONDS == 10.0


def test_status_is_checked_before_the_size():
    transport = FakeTransport(lambda _request: HttpResponse(404, {}, bytes(100)))
    with pytest.raises(HttpStatusError):
        download_image(transport, ImageRequest(COVER, byte_limit=10))


def test_failed_download_keeps_its_status():
    with pytest.raises(HttpStatusError, match="HTTP 404") as raised:
        download_image(FakeTransport(serve_missing), ImageRequest(COVER))
    assert raised.value.status == 404


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (HttpResponse(200, {"content-type": "text/html"}, b"text"), "not an image"),
        (HttpResponse(200, {}, b"text"), "not an image"),
        (HttpResponse(200, {"content-type": "IMAGE/PNG"}, b""), "empty"),
    ],
)
def test_rejects_non_images_and_empty_images(response: HttpResponse, message: str):
    with pytest.raises(ServiceError, match=message):
        download_image(FakeTransport(lambda _request: response), ImageRequest(COVER))


def test_cache_downloads_a_url_once():
    transport = FakeTransport(serve_image)
    cache = ImageCache(transport)
    assert cache.download(ImageRequest(COVER)) == cache.download(ImageRequest(COVER))
    assert len(transport.requests) == 1


def test_cache_tells_byte_limits_apart():
    transport = FakeTransport(serve_image)
    cache = ImageCache(transport)
    cache.download(ImageRequest(COVER))
    cache.download(ImageRequest(COVER, byte_limit=100))
    assert len(transport.requests) == 2


def test_cache_does_not_keep_failures():
    transport = FakeTransport(serve_missing)
    cache = ImageCache(transport)
    for _ in range(2):
        with pytest.raises(HttpStatusError):
            cache.download(ImageRequest(COVER))
    assert len(transport.requests) == 2


def test_cache_evicts_least_recently_used():
    transport = FakeTransport(serve_image)
    cache = ImageCache(transport, capacity=2)
    first, second, third = (ImageRequest(f"{COVER}?{index}") for index in range(3))
    cache.download(first)
    cache.download(second)
    cache.download(first)
    cache.download(third)
    cache.download(first)
    cache.download(second)
    assert [request.url for request in transport.requests] == [
        first.url,
        second.url,
        third.url,
        second.url,
    ]


def test_clear_forgets_images():
    transport = FakeTransport(serve_image)
    cache = ImageCache(transport)
    cache.download(ImageRequest(COVER))
    cache.clear()
    cache.download(ImageRequest(COVER))
    assert len(transport.requests) == 2


def serve_second_only(request: HttpRequest) -> HttpResponse:
    if request.url.endswith("second"):
        return make_image_response(b"second")
    return make_image_response(b"", status=404)


def test_download_first_returns_first_image_that_downloads():
    cache = ImageCache(FakeTransport(serve_second_only))
    requests = [ImageRequest(f"{COVER}?{name}") for name in ("first", "second", "third")]
    assert cache.download_first(requests) == b"second"


def test_download_first_returns_none_when_all_fail():
    cache = ImageCache(FakeTransport(serve_missing))
    assert cache.download_first([ImageRequest(COVER)]) is None


def test_download_first_lets_bugs_through():
    def fail(_request: HttpRequest) -> HttpResponse:
        raise KeyError("bug")

    with pytest.raises(KeyError):
        ImageCache(FakeTransport(fail)).download_first([ImageRequest(COVER)])
