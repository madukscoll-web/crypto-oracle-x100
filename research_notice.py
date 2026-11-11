"""Process capabilities issued by recomputing research pipelines, never BUY.

This protects transport against serialized caller labels or Boolean flags. It is
not remote-source authentication, nor a sandbox against arbitrary Python code.
Only trusted pipeline code calls the private issuer after replaying evidence.
"""
import hashlib
import hmac
import secrets

_KEY = secrets.token_bytes(32)
_CONSTRUCTOR = object()
LABELS = frozenset({'NEW TOKEN DISCOVERY', 'ALL TIME LOW', 'NEAR ALL TIME LOW', 'ATL RECOVERY WATCH', 'UNVERIFIED ATL RESEARCH WATCH', 'EARLY REVERSAL WATCH',
                    'CONFIRMED TECHNICAL REVERSAL', 'INVALIDATED SETUP'})
PREFIXES = {
    'ALL TIME LOW': 'ALL-TIME LOW WATCH',
    'NEAR ALL TIME LOW': 'ALL-TIME LOW WATCH',
    'ATL RECOVERY WATCH': 'ALL-TIME LOW WATCH',
    'UNVERIFIED ATL RESEARCH WATCH': 'ALL-TIME LOW WATCH',
    'EARLY REVERSAL WATCH': 'EARLY BULLISH REVERSAL WATCH',
    'CONFIRMED TECHNICAL REVERSAL': 'CONFIRMED BULLISH REVERSAL',
}


class ResearchNotice(str):
    def __new__(cls, text, *, _capability=None):
        if _capability is not _CONSTRUCTOR:
            raise ValueError('Research notices must originate in a validated pipeline')
        notice = super().__new__(cls, text)
        notice._signature = hmac.digest(_KEY, text.encode(), hashlib.sha256)
        return notice


def _issue(classification, body):
    if classification not in LABELS or not isinstance(body, str) or not body.strip():
        raise ValueError('Invalid structured research classification')
    body = body.strip()
    if body.splitlines()[0] == classification:
        body = '\n'.join(body.splitlines()[1:]).strip()
    if not body:
        raise ValueError('Missing research body')
    prefix = PREFIXES.get(classification, classification)
    # The umbrella is navigation, not stronger evidence. Preserve the exact
    # computed subtype so provider-reported lows never become lifetime claims.
    subtype = 'Research subtype: '+classification+'\n' if prefix != classification else ''
    return ResearchNotice(prefix+'\n'+subtype+body, _capability=_CONSTRUCTOR)


def verified_text(notice):
    if type(notice) is not ResearchNotice:
        raise ValueError('Raw text and caller labels are not research credentials')
    text = str(notice)
    expected = hmac.digest(_KEY, text.encode(), hashlib.sha256)
    if not hmac.compare_digest(getattr(notice, '_signature', b''), expected):
        raise ValueError('Invalid research capability')
    if text.splitlines()[0] not in {PREFIXES.get(label, label) for label in LABELS}:
        raise ValueError('Unsupported research classification')
    return text
