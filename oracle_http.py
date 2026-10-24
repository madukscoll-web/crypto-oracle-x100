"""Bounded, paced public API GET requests. Standard library only."""
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

_LAST_REQUEST = {}
MIN_INTERVAL = 2.2  # Below 30 requests/minute for each public provider.
RETRIES = 2
TIMEOUT = 20


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
    request = urllib.request.Request(url, headers=headers or {})
    for attempt in range(retries + 1):
        wait = MIN_INTERVAL - (time.monotonic() - _LAST_REQUEST.get(host, -MIN_INTERVAL))
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST[host] = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError("Provider JSON must be an object")
            return payload
        except urllib.error.HTTPError as exc:
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
