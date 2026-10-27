DEFAULT_MIME_TYPE = "image/jpeg"
# Each type's byte patterns, as (offset, bytes) pairs that must all match.
IMAGE_SIGNATURES: tuple[tuple[str, tuple[tuple[int, bytes], ...]], ...] = (
    ("image/jpeg", ((0, b"\xff\xd8\xff"),)),
    ("image/png", ((0, b"\x89PNG"),)),
    ("image/gif", ((0, b"GIF8"),)),
    ("image/webp", ((0, b"RIFF"), (8, b"WEBP"))),
)


def get_image_mime_type(data: bytes) -> str:
    return next(
        (
            mime_type
            for mime_type, patterns in IMAGE_SIGNATURES
            if all(data[offset : offset + len(part)] == part for offset, part in patterns)
        ),
        DEFAULT_MIME_TYPE,
    )
