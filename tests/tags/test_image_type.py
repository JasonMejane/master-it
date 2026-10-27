import pytest

from masterit.tags.image_type import get_image_mime_type


@pytest.mark.parametrize(
    ("data", "mime_type"),
    [
        (b"\xff\xd8\xff\xe0rest", "image/jpeg"),
        (b"\x89PNG\r\n", "image/png"),
        (b"GIF89a", "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8", "image/webp"),
        (b"RIFF\x00\x00\x00\x00WAVE", "image/jpeg"),
        (b"", "image/jpeg"),
        (b"unknown", "image/jpeg"),
    ],
)
def test_reads_the_image_type_from_its_signature(data: bytes, mime_type: str):
    assert get_image_mime_type(data) == mime_type
