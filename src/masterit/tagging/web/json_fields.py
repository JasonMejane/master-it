from typing import Any, cast

from masterit.tagging.web.json_response import JsonObject


# Services leave fields out or change their type; an odd field reads as missing, never as a bug.
def read_text(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def read_int(payload: JsonObject, key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value) if float(value).is_integer() else None


def read_object(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def read_list(payload: JsonObject, key: str) -> list[Any]:
    value = payload.get(key)
    return cast(list[Any], value) if isinstance(value, list) else []


# Odd items stay in place, so the first item is still the service's first answer.
def read_objects(payload: JsonObject, key: str) -> list[JsonObject]:
    return [
        cast(JsonObject, item) if isinstance(item, dict) else {} for item in read_list(payload, key)
    ]
