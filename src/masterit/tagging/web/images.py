import math
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from masterit.tagging.web.errors import HttpStatusError, ServiceError
from masterit.tagging.web.transport import (
    IMAGE_TIMEOUT_SECONDS,
    HttpRequest,
    HttpTransport,
)

# Tracks of an album are processed together, so a few entries catch nearly every repeat.
DEFAULT_CAPACITY = 20


@dataclass(frozen=True)
class ImageRequest:
    url: str
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    byte_limit: float = math.inf

    @property
    def cache_key(self) -> tuple[str, float]:
        return (self.url, self.byte_limit)


def download_image(transport: HttpTransport, request: ImageRequest) -> bytes:
    response = transport.send(
        HttpRequest(
            request.url, request.headers, IMAGE_TIMEOUT_SECONDS, request.byte_limit, ensure_image
        )
    )
    if not response.body:
        raise ServiceError("Image response was empty.")
    return response.body


def ensure_image(status: int, headers: Mapping[str, str]) -> None:
    if not 200 <= status < 300:
        raise HttpStatusError(status, f"Image request failed: HTTP {status}")
    if not headers.get("content-type", "").lower().startswith("image/"):
        raise ServiceError("Image response was not an image.")


class ImageCache:
    def __init__(self, transport: HttpTransport, capacity: int = DEFAULT_CAPACITY) -> None:
        self._transport = transport
        self._capacity = capacity
        self._images: OrderedDict[tuple[str, float], bytes] = OrderedDict()

    def download(self, request: ImageRequest) -> bytes:
        image = self._images.pop(request.cache_key, None)
        if image is None:
            image = download_image(self._transport, request)
        self._images[request.cache_key] = image
        if len(self._images) > self._capacity:
            self._images.popitem(last=False)
        return image

    def download_first(self, requests: Iterable[ImageRequest]) -> bytes | None:
        for request in requests:
            try:
                return self.download(request)
            except ServiceError:
                continue
        return None

    def clear(self) -> None:
        self._images.clear()
