"""Bounded read-only evidence collection for the production hourly scanner.

Observations never authorize BUY. One shared budget covers all selected tokens;
unsupported networks, provider failures and unexamined candidates remain explicit.
"""
import json
import pathlib
import os
import execution_quotes
import kyber_quotes
import re

import onchain
import supply_evidence
import token_unlocks
import verification
from asset_identity import key
from gate_spot_research import PublicGate
from provider_session import Session


class HourlyEvidence:
    def __init__(self, max_candidates=3, max_seconds=60, max_requests=90, transport=None):
        self.max_candidates = max_candidates
        self.assessed = 0
        self.session = Session(max_requests=max_requests, max_seconds=max_seconds,
                               transport=transport, max_request_seconds=5)
        self.gate = PublicGate(self.fetch)
        self.catalog_attempted = False
        self.registry = json.loads(pathlib.Path(__file__).with_name('evidence_registry.json').read_text())

    def fetch(self, url):
        return self.session.json(url, timeout=5)

    def collect(self, item):
        # The session is shared across candidates, including RPC calls made by
        # collectors. Restore any outer context even when a collector fails.
        if self.assessed >= self.max_candidates:
            item['hourly_evidence'] = {'status': 'NOT_CHECKED', 'reason': 'Hourly candidate budget exhausted'}
            return
        self.assessed += 1
        with self.session:
            item['verification'] = verification.collect(item, self.fetch)
            report = item['verification']
            # Reuse one catalog per run, never join by ticker alone.
            if not self.catalog_attempted:
                self.catalog_attempted = True
                try:
                    self.gate.catalog()
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    pass
            gate_start = len(self.gate.evidence)
            asset = dict(network=item.get('network'), token_address=item.get('token_address'))
            try:
                asset['asset_key'] = key(asset['network'], asset['token_address'])
                item['gate_spot'] = self.gate.eligibility(asset)
            except (ValueError, KeyError, TypeError):
                item['gate_spot'] = dict(status='UNKNOWN', reason='Unsupported exact chain/contract identity')
            item['gate_execution_research'] = self.gate.research(item['gate_spot'])
            item['gate_provider_evidence'] = self.gate.evidence[gate_start:]
            if item.get('network') in onchain.RPCS and re.fullmatch(r'0x[0-9a-fA-F]{40}', item.get('token_address', '')):
                info = ((report.get('contract_security', {}).get('raw') or {}).get('result') or {}).get(item['token_address'].lower(), {})
                # Exact-pool identity and holder balance observations; no LP
                # control or beneficial-owner verification is inferred.
                report['onchain'] = onchain.collect(item, info.get('holders') or [],
                    lock_descriptors=self.registry.get('lp_locks', {}).get(item['network'] + ':' + item['address'].lower(), []))
                report['supply_comparison'] = supply_evidence.collect(item, self.fetch)
            report['unlocks'] = token_unlocks.collect(item, self.registry)
            report['execution'] = execution_quotes.collect(item, os.environ)
            report['kyber'] = kyber_quotes.collect(item, os.environ)
            item['hourly_evidence'] = dict(status='COLLECTED', reason='Read-only observations; complete safety and execution remain unverified')

    def summary(self):
        return dict(candidates_assessed=self.assessed, **self.session.summary())


def collect_safely(collector, item):
    """Optional research failure must not interrupt core Telegram delivery."""
    try:
        collector.collect(item)
    except Exception as exc:
        # Never expose exception text, credential-bearing URLs or raw bodies.
        item['hourly_evidence'] = dict(status='ERROR', reason='Optional collector failed: ' + type(exc).__name__)


def findings(item):
    """Descriptive evidence states, deliberately distinct from authorization."""
    report = item.get('verification') or {}
    results = {}
    for label, name in [('Sell simulation', 'sellability'), ('Contract screening', 'contract_security'),
                        ('Holder coverage', 'holders'), ('LP screening', 'liquidity'),
                        ('On-chain pool/holders', 'onchain'), ('Supply comparison', 'supply_comparison'),
                        ('Unlock disclosure', 'unlocks'), ('0x quote', 'execution'), ('Kyber route', 'kyber')]:
        entry = report.get(name) or {}
        # Failed requests use their provider key in verification.collect.
        if not entry and name == 'sellability':
            entry = report.get('honeypot') or {}
        if not entry and name in ('contract_security', 'holders', 'liquidity'):
            entry = report.get('goplus') or {}
        reason = entry.get('reason', (item.get('hourly_evidence') or {}).get('reason', 'No live collector result'))
        http_status = (entry.get('diagnostic') or {}).get('http_status')
        if http_status is not None:
            reason += ' (HTTP ' + str(http_status) + ')'
        results[label] = dict(status=entry.get('status', 'NOT_CHECKED'),
            reason=reason,
            observed_at=entry.get('observed_at'), source=entry.get('source'), url=entry.get('url'))
    return results


def adverse(item):
    report = item.get('verification') or {}
    return any((report.get(k) or {}).get('status') in ('FAIL', 'HIGH CONCERN', 'CONFLICTING')
               for k in ('contract_security', 'sellability', 'tokenomics', 'supply_comparison'))


def telegram_lines(item):
    lines = []
    for label, result in findings(item).items():
        lines.append(label + ': ' + result['status'] + ' — ' + result['reason'][:180])
    gate = item.get('gate_spot') or {}
    lines.append('Gate Spot: ' + gate.get('status', 'NOT_CHECKED') + ' — ' + gate.get('reason', 'No exact-contract market result')[:160])
    research = item.get('gate_execution_research') or {}
    book = research.get('book') or {}
    if book:
        lines.append('Gate snapshot (USDT): spread ' + str(book.get('spread_bps')) + ' bps; buy/sell depth sufficient ' +
                     str(book.get('buy_depth_sufficient')) + '/' + str(book.get('sell_depth_sufficient')) +
                     '; not a DEX quote or guaranteed fill')
    return lines
