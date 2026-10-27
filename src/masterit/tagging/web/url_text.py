import urllib.parse

# What JavaScript's encodeURIComponent leaves as is, besides letters, digits and "-_.~".
URI_COMPONENT_SAFE = "!*'()"


# Service answers and odd file names can hold half an emoji, which UTF-8 cannot encode.
def replace_lone_surrogates(text: str) -> str:
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def encode_query(params: dict[str, str]) -> str:
    return urllib.parse.urlencode(
        {name: replace_lone_surrogates(value) for name, value in params.items()}
    )


def encode_path_part(value: str) -> str:
    return urllib.parse.quote(replace_lone_surrogates(value), safe=URI_COMPONENT_SAFE)
