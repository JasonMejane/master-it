from masterit.download.cancellation import CancelToken


def test_token_starts_not_cancelled():
    assert not CancelToken().is_cancelled


def test_cancel_marks_token_cancelled():
    token = CancelToken()
    token.cancel()
    assert token.is_cancelled
