import threading

from masterit.cancellation import CancelToken


def test_token_starts_not_cancelled():
    assert not CancelToken().is_cancelled


def test_cancel_marks_token_cancelled():
    token = CancelToken()
    token.cancel()
    assert token.is_cancelled


def test_wait_cancelled_times_out_while_not_cancelled():
    assert not CancelToken().wait_cancelled(0.01)


def test_wait_cancelled_returns_once_cancelled():
    token = CancelToken()
    token.cancel()
    assert token.wait_cancelled(5)


def test_cancel_requests_are_counted():
    token = CancelToken()
    assert token.wait_for_request(0, 0.01) == 0
    token.cancel()
    token.cancel()
    assert token.wait_for_request(1, 5) == 2
    assert token.is_cancelled


def test_wait_for_request_blocks_until_a_new_request():
    token = CancelToken()
    token.cancel()
    assert token.wait_for_request(1, 0.05) == 1
    threading.Timer(0.05, token.cancel).start()
    assert token.wait_for_request(1, 5) == 2
