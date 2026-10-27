import json
from typing import Any, cast

from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpResponse

type JsonObject = dict[str, Any]


def read_json(response: HttpResponse, service_name: str) -> JsonObject:
    if not response.is_ok:
        raise ServiceError(f"{service_name} request failed: HTTP {response.status}")
    payload = parse_json(response.body, service_name)
    if not isinstance(payload, dict):
        raise make_unexpected_error(service_name)
    return cast(JsonObject, payload)


def parse_json(body: bytes, service_name: str) -> object:
    try:
        return json.loads(body)
    except ValueError as error:
        raise make_unexpected_error(service_name) from error


def make_unexpected_error(service_name: str) -> ServiceError:
    return ServiceError(f"{service_name} returned an unexpected response")


def get_retry_after_delay(response: HttpResponse, fallback: float, maximum: float) -> float:
    retry_after = response.get_header("retry-after").strip()
    if not (retry_after.isascii() and retry_after.isdigit()):
        return fallback
    return min(float(retry_after), maximum)
