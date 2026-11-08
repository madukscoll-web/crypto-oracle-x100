"""Bounded, paced public API GET requests. Standard library only."""
import json
import datetime as dt
import email.utils
import math
import time
import urllib.error
import urllib.parse
import urllib.request

_LAST_REQUEST = {}
_COOLDOWN_UNTIL = {}
MIN_INTERVAL = 2.2  # Below 30 requests/minute for each public provider.
HOST_INTERVALS = {"api.geckoterminal.com": 8.0}
RETRIES = 2
TIMEOUT = 20


class ProviderRateLimited(OSError):
    """A provider cooldown is active; no remote request was made."""


def rate_limit_delay(headers):
    """Honor both Retry-After formats without truncating a long server delay."""
    value = (headers or {}).get("Retry-After", "")
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            target = email.utils.parsedate_to_datetime(value)
            delay = (target - dt.datetime.now(dt.timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            delay = 60.0
    return max(60.0, delay) if math.isfinite(delay) else 60.0


def retry_delay(headers, attempt):
    try:
        value = float(headers.get("Retry-After", ""))
        if math.isfinite(value) and value > 0:
            return min(value, 60)
    except (TypeError, ValueError):
        pass
    return (12, 24)[min(attempt, 1)]


def get_json(url, headers=None, *, retries=RETRIES, timeout=TIMEOUT):
    host = urllib.parse.urlsplit(url).netloc
    if time.monotonic() < _COOLDOWN_UNTIL.get(host, 0):
        raise ProviderRateLimited("Public provider cooldown active")
    request = urllib.request.Request(url, headers=headers or {})
    for attempt in range(retries + 1):
        interval = HOST_INTERVALS.get(host, MIN_INTERVAL)
        wait = interval - (time.monotonic() - _LAST_REQUEST.get(host, -interval))
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST[host] = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError("Provider JSON must be an object")
            _COOLDOWN_UNTIL.pop(host, None)
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                delay = rate_limit_delay(exc.headers)
                _COOLDOWN_UNTIL[host] = time.monotonic() + delay
                # A rate limit is a scheduling outcome, not a transient request
                # failure. Return control to the caller for fallback/deferral;
                # sleeping here consumed five minutes across ten candidates in
                # production. The shared cooldown still prevents early retries
                # through other resources on this host. 5xx/network retries
                # remain bounded below, and fresh calls recover after expiry.
                print(f"API {host}: HTTP 429; deferred during {delay:g}s provider cooldown", flush=True)
                raise
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            delay = retry_delay(exc.headers, attempt)
            print(f"API {host}: HTTP {exc.code}; retry {attempt + 1}/{RETRIES} in {delay:g}s", flush=True)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == retries:
                raise
            delay = retry_delay({}, attempt)
            print(f"API {host}: {type(exc).__name__}; retry {attempt + 1}/{RETRIES}", flush=True)
        time.sleep(delay)


