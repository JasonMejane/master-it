def parse_urls(text: str) -> list[str]:
    return list(dict.fromkeys(text.split()))
