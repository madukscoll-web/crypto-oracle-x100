"""Bounded read-only signed-evidence intake from a repository-enrolled HTTPS feed.

Transport never authorizes a candidate; authenticated_admission independently
verifies every signature, identity, policy invariant and expiration afterward.
"""
import json
import pathlib
import time
import urllib.parse
import urllib.request

_CACHE={}


def fetch(url):
    from provider_session import CURRENT
    session=CURRENT.get()
    if session is not None:
        return session.json(url)
    request=urllib.request.Request(url,headers={'Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=5) as response:
        payload=response.read(2_000_001)
    if len(payload)>2_000_000:raise ValueError('Evidence response exceeds limit')
    return json.loads(payload)


def collect(identity, trust, transport=None, clock=None):
    # Tests may supply an isolated transport; production always uses the same
    # configured session/HTTPS path and repository trust registry.
    endpoint=trust.get('bundle_endpoint')
    parsed=urllib.parse.urlsplit(endpoint or '')
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.port not in (None,443)):
        raise ValueError('Repository-enrolled HTTPS evidence feed unavailable')
    if len(trust.get('reviewers',{}))<2:raise ValueError('Independent reviewers not enrolled')
    url=endpoint+'?'+urllib.parse.urlencode(identity)
    clock=time.monotonic if clock is None else clock
    now=clock()
    cached=_CACHE.get(url)
    if cached and 0<=now-cached[0]<5:
        if cached[1] is None:raise ValueError('Evidence feed recently unavailable')
        return json.loads(cached[1])
    if len(_CACHE)>=256:_CACHE.clear()
    try:
        result=(transport or fetch)(url)
        serialized=json.dumps(result,allow_nan=False)
        if len(serialized)>2_000_000:raise ValueError('Evidence response exceeds limit')
        _CACHE[url]=(now,serialized)
        return json.loads(serialized)
    except (OSError,ValueError,TypeError):
        _CACHE[url]=(now,None)
        raise ValueError('Evidence feed unavailable or malformed') from None
