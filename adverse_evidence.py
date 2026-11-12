"""Shared conservative rejection policy; adverse labels never grant approval.

These records can withhold a candidate, but are not authenticated positive proof.
Provider absence, malformed records and caller PASS flags cannot authorize BUY.
"""
CHECKS = ('contract_security', 'sellability', 'honeypot', 'holders', 'liquidity',
          'tokenomics', 'unlocks', 'unlock_provider', 'supply_comparison',
          'contract_source', 'custody', 'nft_custody', 'tokenized_stock_reference',
          'execution', 'execution_checks', 'kyber', 'kyber_execution',
          'calldata_policy', 'pool_identity_followup', 'owner_control')
ADVERSE = ('FAIL', 'FAILED', 'CONFLICTING', 'HIGH CONCERN')


def findings(item):
    report = item.get('verification')
    if not isinstance(report, dict):
        report = {}
    result = {}
    for name in CHECKS:
        record = report.get(name)
        if isinstance(record, dict) and record.get('status') in ADVERSE:
            result[name] = str(record.get('reason') or 'Adverse evidence; investigate')
    # Recompute adverse provider facts instead of trusting a mutable status label.
    # This can only reject. Even a forged clear response never proves safety.
    import verification
    from urllib.parse import urlsplit
    token = item.get('token_address')
    network = item.get('network')
    chain = verification.CHAINS.get(network) if isinstance(network, str) else None
    if isinstance(token, str) and chain is not None:
        for name in ('contract_security', 'sellability'):
            record = report.get(name)
            if not isinstance(record, dict):
                continue
            try:
                endpoint = urlsplit(record.get('url', ''))
                raw = record.get('raw')
                if not isinstance(raw, dict):
                    continue
                if (name == 'contract_security' and record.get('source') == 'goplus'
                        and endpoint.scheme == 'https' and endpoint.hostname == 'api.gopluslabs.io'
                        and endpoint.path == f'/api/v1/token_security/{chain}'
                        and raw.get('code') == 1):
                    info = (raw.get('result') or {}).get(token.lower())
                    if not isinstance(info, dict):
                        continue
                    status, reason = verification.security(info)
                elif (name == 'sellability' and record.get('source') == 'honeypot'
                        and endpoint.scheme == 'https' and endpoint.hostname == 'api.honeypot.is'
                        and endpoint.path == '/v2/IsHoneypot'):
                    status, reason = verification.honeypot(raw, token, chain, item.get('address') or '')
                else:
                    continue
                if status in ADVERSE:
                    result[name] = reason
            except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
                # A malformed response is not affirmative evidence of safety.
                continue
    if item.get('risk_category') == 'AVOID / HIGH CONCERN':
        result['provider_risk'] = 'Critical provider/security concern'
    return result

