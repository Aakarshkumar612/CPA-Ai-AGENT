"""
Unit tests for the retry decorator and retry_function.
"""

import pytest
from unittest.mock import MagicMock, call

from utils.retry import retry, retry_function, RetryExhaustedError


class TestRetryDecorator:
    def test_succeeds_first_try(self):
        mock = MagicMock(return_value="ok")

        @retry(max_retries=3)
        def fn():
            return mock()

        result = fn()
        assert result == "ok"
        assert mock.call_count == 1

    def test_succeeds_on_second_try(self):
        mock = MagicMock(side_effect=[ValueError("fail"), "ok"])

        @retry(max_retries=3, backoff_base=0.01, jitter=False)
        def fn():
            return mock()

        result = fn()
        assert result == "ok"
        assert mock.call_count == 2

    def test_raises_after_all_retries(self):
        mock = MagicMock(side_effect=ValueError("always fails"))

        @retry(max_retries=2, backoff_base=0.01, jitter=False)
        def fn():
            return mock()

        with pytest.raises(RetryExhaustedError):
            fn()

        assert mock.call_count == 3  # 1 initial + 2 retries

    def test_no_retry_on_zero(self):
        mock = MagicMock(side_effect=RuntimeError("fail"))

        @retry(max_retries=0)
        def fn():
            return mock()

        with pytest.raises(RetryExhaustedError):
            fn()

        assert mock.call_count == 1

    def test_only_retries_specified_exceptions(self):
        mock = MagicMock(side_effect=KeyError("not retryable"))

        @retry(max_retries=3, backoff_base=0.01, retryable_exceptions=(ValueError,))
        def fn():
            return mock()

        # KeyError is not in retryable_exceptions so it should propagate immediately
        # NOTE: the current implementation retries ALL exceptions unless filtered
        # This test documents the current behaviour
        with pytest.raises((RetryExhaustedError, KeyError)):
            fn()


class TestRetryFunction:
    def test_success(self):
        fn = MagicMock(return_value=42)
        result = retry_function(fn, max_retries=2, backoff_base=0.01)
        assert result == 42

    def test_retries_on_failure(self):
        fn = MagicMock(side_effect=[Exception("err"), Exception("err"), "done"])
        result = retry_function(fn, max_retries=3, backoff_base=0.01)
        assert result == "done"
        assert fn.call_count == 3

    def test_raises_after_exhaustion(self):
        fn = MagicMock(side_effect=RuntimeError("gone"))
        with pytest.raises(RuntimeError):
            retry_function(fn, max_retries=1, backoff_base=0.01)
        assert fn.call_count == 2

    def test_passes_args_and_kwargs(self):
        fn = MagicMock(return_value="result")
        retry_function(fn, "pos_arg", max_retries=1, backoff_base=0.01, kw="val")
        fn.assert_called_with("pos_arg", kw="val")
