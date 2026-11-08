"""Build source-bound, unreviewed Gate research dossiers from retained reports.

This is an offline review interface, not review authentication or registry intake.
Hashes bind canonical JSON responses, not HTTP wire bytes or source authority.
All assessed rows, including adverse and incomplete findings, remain in output.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
from urllib.parse import urlsplit

from asset_identity import GATE_CHAINS, key

STATUSES = ('VERIFIED', 'ADVERSE', 'CONFLICTING', 'UNKNOWN', 'NOT APPLICABLE')
TOPICS = ('exchange_pair_identity', 'security', 'sellability', 'transaction_taxes',
          'transfer_restrictions', 'blacklist_controls', 'mint_privileges',
          'upgradeability', 'lp_control', 'lp_locks_burns', 'holder_concentration',
          'beneficial_ownership', 'circulating_supply', 'vesting', 'unlock_schedule',
          'bridge_backing', 'executable_liquidity', 'slippage', 'router_identity')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _url(value):
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password else None


def _stamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value if parsed.tzinfo is not None else None
    except (AttributeError, ValueError, TypeError):
        return None


def _topic(status='UNKNOWN', reason='Required independent evidence not collected', **extra):
    if status not in STATUSES:
        raise ValueError('Invalid dossier topic state')
    return dict(status=status, reason=reason, **extra)


def identity(row):
    """Recheck exchange metadata joins, never infer a contract from its symbol."""
    try:
        identity_key = key(row['network'], row['token_address'])
        if row.get('asset_key') != identity_key:
            raise ValueError('Candidate exact identity mismatch')
        evidence = row.get('evidence') or {}
        gate = evidence.get('gate_identity') or {}
        if gate.get('status') != 'CONFIRMED_SPOT':
            status = 'CONFLICTING' if gate.get('status') == 'CONFLICTING' else 'UNKNOWN'
            return identity_key, _topic(status, 'Exact exchange identity not established')
        raw = gate['raw']; currency, chain, pair = (raw[k] for k in ('currency', 'chain', 'pair'))
        symbol = currency['currency']; pair_id = symbol + '_USDT'
        if (row.get('symbol') != symbol or row.get('pair_id') != pair_id or
                gate.get('pair_id') != pair_id or pair.get('id') != pair_id or
                pair.get('base') != symbol or pair.get('quote') != 'USDT'):
            raise ValueError('Exchange pair identity conflict')
        if (GATE_CHAINS.get(chain.get('chain')) != row['network'] or
                key(row['network'], chain.get('contract_address')) != identity_key):
            raise ValueError('Wallet-chain contract mismatch')
        matches = [c for c in currency.get('chains', [])
                   if GATE_CHAINS.get(c.get('name')) == row['network'] and
                   key(row['network'], c.get('addr')) == identity_key]
        if len(matches) != 1:
            raise ValueError('Currency catalog contract absent/ambiguous')
        if (currency.get('delisted') is not False or currency.get('trade_disabled') is not False or
                pair.get('type') != 'normal' or pair.get('trade_status') != 'tradable' or
                pair.get('st_tag') is not False or type(chain.get('is_disabled')) is not int or
                chain['is_disabled'] != 0):
            return identity_key, _topic('ADVERSE', 'Collected exchange metadata disabled or not normal tradable Spot')
        if not _stamp(row.get('observed_at')):
            return identity_key, _topic('UNKNOWN', 'Timezone-aware identity observation timestamp missing')
        return identity_key, _topic('VERIFIED', 'Exact contract agrees across retained exchange currency, wallet-chain and Spot pair metadata',
            verification_scope='INTERNAL_EXCHANGE_METADATA_JOIN_AT_COLLECTION_ONLY',
            independently_authenticated=False, current_eligibility_established=False)
    except (KeyError, ValueError, TypeError, AttributeError):
        return None, _topic('CONFLICTING', 'Malformed or inconsistent exact asset/market identity')


def sources(report):
    """Index retained public response objects without asserting independence."""
    result = []
    def append(entry, path):
        if not isinstance(entry, dict) or 'raw' not in entry:
            return
        url = _url(entry.get('url') or entry.get('source_url'))
        result.append(dict(source_path=path, source_url=url,
            source_url_status='RECORDED' if url else 'MISSING_OR_INVALID',
            canonical_response_sha256=digest(entry['raw']),
            retrieved_at=_stamp(entry.get('retrieved_at')),
            source_authority='UNREVIEWED', independence='NOT_ESTABLISHED'))
    for index, entry in enumerate(report.get('gate_evidence', [])):
        append(entry, 'gate_evidence/'+str(index))
    for index, row in enumerate(report['candidates']):
        if not isinstance(row, dict):
            continue
        for name, entry in (row.get('evidence') or {}).items():
            append(entry, 'candidates/'+str(index)+'/evidence/'+str(name))
    return result


def _security_topics(row, topics):
    evidence = row.get('evidence') or {}
    security = evidence.get('security') or {}
    provider_status = security.get('status', 'UNKNOWN')
    state = 'CONFLICTING' if provider_status == 'CONFLICTING' else 'ADVERSE' if provider_status in ('FAIL', 'ADVERSE', 'HIGH CONCERN') else 'UNKNOWN'
    topics['security'] = _topic(state, security.get('reason') or 'Provider screening is not independent security clearance',
        provider_status=provider_status, missing_fields=security.get('missing_fields', []))
    raw = security.get('raw') or {}
    info = (raw.get('result') or {}).get(str(row.get('token_address', '')).lower(), {})
    flags = {'sellability': ('is_honeypot', 'cannot_sell_all'),
             'transfer_restrictions': ('transfer_pausable', 'trading_cooldown'),
             'blacklist_controls': ('is_blacklisted',), 'mint_privileges': ('is_mintable',),
             'upgradeability': ('is_proxy',)}
    for topic, names in flags.items():
        findings = {name: info[name] for name in names if name in info}
        adverse = any(str(value) == '1' for value in findings.values())
        topics[topic] = _topic('ADVERSE' if adverse else 'UNKNOWN',
            'Provider reports a risk/control requiring independent investigation' if adverse else
            'Missing or non-adverse provider flags do not establish independent verification',
            provider_observations=findings)
    if row.get('classification') == 'AVOID / HIGH CONCERN':
        topics['security'] = _topic('ADVERSE', 'Original assessed adverse finding retained', provider_status=provider_status)
    supply = evidence.get('issuer_supply') or {}
    if supply.get('status') == 'CONFLICTING':
        topics['circulating_supply'] = _topic('CONFLICTING', supply.get('reason') or 'Issuer/provider supply conflict')
    else:
        topics['circulating_supply'] = _topic('UNKNOWN',
            'Provider/issuer supply observations do not reconstruct independently verified circulation',
            provider_status=(evidence.get('supply') or {}).get('status', 'UNKNOWN'),
            issuer_status=supply.get('status', 'UNKNOWN'))


def build(report):
    if (not isinstance(report, dict) or not isinstance(report.get('candidates'), list) or
            len(report['candidates']) > 30 or not isinstance(report.get('gate_evidence', []), list)):
        raise ValueError('Bounded Gate discovery report required')
    # Reject nonfinite/provider-corrupted JSON before making provenance hashes.
    report_hash = digest(report)
    manifest = sources(report)
    dossiers = []
    for index, original in enumerate(report['candidates']):
        row = original if isinstance(original, dict) else {}
        identity_key, identity_topic = identity(row)
        topics = {name: _topic() for name in TOPICS}
        topics['exchange_pair_identity'] = identity_topic
        _security_topics(row, topics)
        row_hash = digest(original)
        identifier = 'gate-dossier-'+str(index)+'-'+row_hash[:16]
        blockers = [value for value in row.get('blockers', []) if isinstance(value, str)]
        missing = [name for name, finding in topics.items() if finding['status'] != 'VERIFIED']
        dossiers.append(dict(dossier_id=identifier, asset_key=identity_key,
            identity=dict(symbol=row.get('symbol'), network=row.get('network'),
                          contract=row.get('token_address'), pair=row.get('pair_id')),
            observed_at=_stamp(row.get('observed_at')), original_classification=row.get('classification', 'UNKNOWN'),
            candidate_canonical_sha256=row_hash, report_canonical_sha256=report_hash,
            raw_candidate=original, topics=topics, missing_or_adverse_topics=missing,
            original_blockers=blockers, review_status='UNREVIEWED',
            source_manifest_paths=[entry['source_path'] for entry in manifest
                                   if entry['source_path'].startswith('candidates/'+str(index)+'/') or
                                   entry['source_path'].startswith('gate_evidence/')],
            review_interface=dict(dossier_id=identifier, evidence_digest=row_hash,
                reviewer_name=None, reviewer_public_identity=None, reviewed_at=None,
                independent_source_reviews=[], topic_decisions={}, decision='UNREVIEWED',
                instructions='Inspect retained source content and exact identity, obtain missing primary and independent evidence, document adverse findings. This template is not an approved registry record or signed admission bundle.'),
            buy_authorized=False, orders_allowed=False, telegram_eligible=False))
    return dict(schema_version=1, status='REVIEW_DOSSIERS_UNAPPROVED',
        report_canonical_sha256=report_hash, source_manifest=manifest, dossiers=dossiers,
        review_index=[dict(dossier_id=row['dossier_id'], asset_key=row['asset_key'],
            pair=row['identity']['pair'], review_status='UNREVIEWED',
            adverse_topics=[name for name, value in row['topics'].items() if value['status'] == 'ADVERSE'],
            missing_topics=row['missing_or_adverse_topics']) for row in dossiers],
        assessed_rows=len(dossiers), reviewed_rows=0, approved_rows=0,
        collection_errors=report.get('errors', []), buy_authorized=False,
        orders_allowed=False, telegram_eligible=False,
        limitations=['Canonical JSON hashes establish retained content integrity, not provider authenticity or independence.',
            'VERIFIED exchange identity is scoped to rechecked metadata joins at collection time; it is not security clearance or current venue eligibility.',
            'All dossiers remain unreviewed; this output never populates gate_token_reviews.json or enrolls reviewers.',
            'Book depth and slippage remain historical observations, not authenticated executable liquidity or fills.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default='gate_spot_discovery_report.json')
    parser.add_argument('--output', default='gate_review_dossiers.json')
    args = parser.parse_args()
    report = json.loads(pathlib.Path(args.report).read_text(encoding='utf-8'))
    result = build(report)
    output = pathlib.Path(args.output)
    temporary = output.with_suffix(output.suffix+'.tmp')
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(output)
    print(json.dumps({name: result[name] for name in
                      ('status', 'assessed_rows', 'reviewed_rows', 'approved_rows', 'buy_authorized', 'orders_allowed')}))


if __name__ == '__main__':
    main()
