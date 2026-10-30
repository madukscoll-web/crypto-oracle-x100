"""Bounded public integration probe. No secrets, notifications or orders.

Outages are retained as evidence, never converted into passes. CI checks schema,
identity binding and fail-closed behavior; provider availability is reported
separately and is not an investment/security approval.
"""
import json
import pathlib

import evidence_coverage
import hourly_evidence
from crypto_oracle_scanner import telegram_eligible

REFERENCES = [
    dict(network='solana', token_address='So11111111111111111111111111111111111111112',
         address='11111111111111111111111111111111'),
    dict(network='eth', token_address='0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
         address='0x811beed0119b4afce20d2583eb608c6f7af1954f'),
]


def run():
    collector = hourly_evidence.HourlyEvidence(max_candidates=2, max_seconds=90, max_requests=60)
    records = []
    for reference in REFERENCES:
        item = dict(reference)
        hourly_evidence.collect_safely(collector, item)
        coverage = evidence_coverage.summary(item)
        assert set(coverage) == set(evidence_coverage.GATES)
        assert all(row['status'] in evidence_coverage.STATES for row in coverage.values())
        assert not telegram_eligible(item), 'Incomplete public observations cannot authorize alerts'
        for entry in item['verification'].values():
            assert entry['network'] == reference['network']
            assert entry['token_address'] == reference['token_address']
        records.append(dict(reference=reference, coverage=coverage, evidence=item['verification']))
        print(reference['network'] + ': ' + json.dumps(coverage, sort_keys=True))
    output = dict(records=records, session=collector.summary(), automated_trading_enabled=False,
                  alerts_sent=0, buy_signals=0)
    path = pathlib.Path('work/hourly_evidence_probe.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    run()
