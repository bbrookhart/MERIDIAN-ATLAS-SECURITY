import httpx
import pytest
from atlas_detect._retry import with_retry


def test_with_retry_returns_result_on_first_success():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    assert with_retry(fn, attempts=3, backoff_seconds=0) == "ok"
    assert len(calls) == 1


def test_with_retry_recovers_after_transient_timeouts():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ReadTimeout("slow")
        return "ok"

    assert with_retry(fn, attempts=3, backoff_seconds=0) == "ok"
    assert len(calls) == 3


def test_with_retry_raises_after_exhausting_attempts():
    def fn():
        raise httpx.ConnectError("down")

    with pytest.raises(httpx.ConnectError):
        with_retry(fn, attempts=2, backoff_seconds=0)


def test_with_retry_does_not_swallow_non_transient_errors():
    def fn():
        raise ValueError("real bug")

    with pytest.raises(ValueError):
        with_retry(fn, attempts=3, backoff_seconds=0)
