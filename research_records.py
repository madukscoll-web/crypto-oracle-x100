"""Optional offline evidence records. Never an authorization or trust store.

No URLs from this file are fetched. Untrusted records remain observations even
when internally consistent. The scanner works without this optional file.
"""
import json
import os
from pathlib import Path

MAX_BYTES = 2_000_000


def load_for(item):
    filename = os.environ.get('ORACLE_EVIDENCE_FILE', '').strip()
    if not filename:
        return {}, 'UNVERIFIED: no offline evidence file configured'
    try:
        with Path(filename).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Evidence file exceeds size limit')
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get('schema_version') != 1:
            raise ValueError('Unsupported evidence schema')
        entries = payload.get('tokens')
        if not isinstance(entries, list) or len(entries) > 400:
            raise ValueError('Invalid token records')
        from fundamental_evidence import same_address
        matches = [entry for entry in entries if isinstance(entry, dict) and
                   entry.get('network') == item.get('network') and
                   same_address(item.get('network'), entry.get('contract'), item.get('token_address')) and
                   same_address(item.get('network'), entry.get('pool'), item.get('address'))]
        if len(matches) != 1 or not isinstance(matches[0].get('records'), dict):
            raise ValueError('Unique exact token/pool records absent')
        return matches[0]['records'], 'Offline observations; authenticity UNVERIFIED'
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return {}, 'UNVERIFIED: offline evidence unavailable or invalid'


def combine(item, offline):
    """Keep remote provider observations distinct from optional offline records."""
    records = dict(offline)
    supply = records.get('supply')
    supply = list(supply) if isinstance(supply, list) else []
    fundamentals = item.get('fundamental_evidence') or {}
    reference = fundamentals.get('total_supply') or {}
    if reference.get('source_url'):
        supply.append(dict(provider='CoinGecko', origin='coingecko',
            source_url=reference['source_url'], network=item.get('network'),
            contract=item.get('token_address'), observed_at=reference.get('observed_at'),
            values={key: value.get('value') for key, value in fundamentals.items()
                    if isinstance(value, dict) and value.get('provider') == 'CoinGecko'}))
    security = item.get('security_provider_evidence') or {}
    if security.get('source_url'):
        goplus = dict(provider='GoPlus', origin='goplus', source_url=security['source_url'],
                      network=item.get('network'), contract=item.get('token_address'),
                      observed_at=security.get('retrieved_utc'), values=security.get('values'),
                      findings=security.get('findings'))
        supply.append(goplus)
        # Live provider observations are retained separately; never overwritten by file data.
        records['provider_security'] = goplus
    records['supply'] = supply
    return records
