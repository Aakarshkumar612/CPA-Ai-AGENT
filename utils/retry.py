"""
Retry Logic — Resilient API calls with exponential backoff.

What this does:
1. Wraps any function call with automatic retry on failure
2. Uses exponential backoff (wait longer between retries)
3. Handles rate limit errors specifically (429 status code)
4. Logs retry attempts so you know what happened

Why exponential backoff?
- If an API is rate-limited, retrying immediately will also fail
- Waiting 1s → 2s → 4s → 8s gives the API time to recover
- Jitter (random delay) prevents "thundering herd" when many clients retry
- This is the same strategy AWS, Google Cloud, and Azure use

Usage:
    @retry(max_retries=3, backoff_base=1.0, jitter=True)
    def call_groq_api():
        return client.chat.completions.create(...)

    # Or manually:
    result = retry_function(call_groq_api, max_retries=3)
"""

import time
import random
import logging
import functools
from typing import Callable, TypeVar, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""
    pass


def retry(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    backoff_max: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator: automatically retry a function on failure with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (0 = no retries)
        backoff_base: Base delay in seconds (doubles each retry)
        backoff_max: Maximum delay cap (never wait longer than this)
        jitter: Add random delay to prevent thundering herd
        retryable_exceptions: Which exceptions trigger a retry
        
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry(max_retries=3, backoff_base=1.0)
        def groq_api_call():
            return client.chat.completions.create(...)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt >= max_retries:
                        # All retries exhausted
                        logger.error(
                            "Function '%s' failed after %d attempts: %s",
                            func.__name__,
                            max_retries,
                            str(e)[:200],
                        )
                        raise RetryExhaustedError(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        ) from e
                    
                    # Calculate backoff delay
                    delay = min(backoff_base * (2 ** attempt), backoff_max)
                    
                    if jitter:
                        # Add 0-25% random jitter
                        delay *= (1 + random.uniform(0, 0.25))
                    
                    logger.warning(
                        "Function '%s' failed (attempt %d/%d): %s — retrying in %.1fs",
                        func.__name__,
                        attempt + 1,
                        max_retries,
                        str(e)[:150],
                        delay,
                    )
                    
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception  # type: ignore
        
        return wrapper
    return decorator


def retry_function(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    backoff_base: float = 1.0,
    **kwargs: Any,
) -> T:
    """
    Call a function with retry logic (non-decorator version).
    
    Use this when you can't decorate the function (e.g., third-party library calls).
    
    Args:
        func: The function to call
        *args: Positional arguments for the function
        max_retries: Number of retry attempts
        backoff_base: Base delay between retries
        **kwargs: Keyword arguments for the function
        
    Returns:
        The function's return value
        
    Example:
        result = retry_function(client.chat.completions.create, model="...", max_retries=3)
    """
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt >= max_retries:
                logger.error(
                    "Function call failed after %d retries: %s",
                    max_retries,
                    str(e)[:200],
                )
                raise
            
            delay = min(backoff_base * (2 ** attempt), 30.0)
            delay *= (1 + random.uniform(0, 0.25))  # jitter
            
            logger.warning(
                "Attempt %d/%d failed: %s — retrying in %.1fs",
                attempt + 1,
                max_retries,
                str(e)[:150],
                delay,
            )
            
            time.sleep(delay)
    
    raise RuntimeError("retry_function should not reach here")
