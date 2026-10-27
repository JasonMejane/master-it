import pytest

from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.json_response import get_retry_after_delay, read_json
from masterit.tagging.web.transport import HttpResponse

from .fakes import make_json_response


def make_retry_response(value: str) -> HttpResponse:
    return HttpResponse(503, {"retry-after": value}, b"")


def test_reads_json_objects():
    assert read_json(make_json_response({"value": 1}), "Service") == {"value": 1}


def test_names_service_and_status_on_failure():
    with pytest.raises(ServiceError, match=r"^Service request failed: HTTP 429$"):
        read_json(make_json_response({}, status=429), "Service")


@pytest.mark.parametrize("body", [b"not json", b"null", b"[1]", b"\xff"])
def test_rejects_bodies_that_are_not_json_objects(body: bytes):
    response = HttpResponse(200, {}, body)
    with pytest.raises(ServiceError, match=r"^Service returned an unexpected response$"):
        read_json(response, "Service")


@pytest.mark.parametrize(("value", "delay"), [("3", 3.0), ("60", 10.0), ("0", 0.0)])
def test_retry_after_seconds_are_capped(value: str, delay: float):
    assert get_retry_after_delay(make_retry_response(value), 2.0, 10.0) == delay


@pytest.mark.parametrize(
    "value", ["", " ", "-5", "0x10", "1e1", "1.5", "٣", "Wed, 21 Oct 2026 07:28:00 GMT"]
)
def test_retry_after_falls_back_for_non_decimal_values(value: str):
    assert get_retry_after_delay(make_retry_response(value), 2.0, 10.0) == 2.0


def test_retry_after_ignores_surrounding_blanks():
    assert get_retry_after_delay(make_retry_response(" 4 "), 2.0, 10.0) == 4.0
