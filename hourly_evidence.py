"""Bounded read-only evidence collection for the production hourly scanner.

Observations never authorize BUY. One shared budget covers all selected tokens;
unsupported networks, provider failures and unexamined candidates remain explicit.
"""
import json
import pathlib
import os
import evidence_coverage
import execution_quotes
import execution_configuration
import contract_sources
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
    def __init__(self, max_candidates=6, max_seconds=240, max_requests=270, transport=None):
        self.max_candidates = max_candidates
        self.assessed = 0
        self.session = Session(max_requests=max_requests, max_seconds=max_seconds,
                               transport=transport, max_request_seconds=3)
        self.gate = PublicGate(self.fetch)
        self.catalog_attempted = False
        self.registry = json.loads(pathlib.Path(__file__).with_name('evidence_registry.json').read_text())

    def fetch(self, url):
        return self.session.json(url, timeout=5)

    def stage(self, name, action, seconds=6, requests=8):
        """A slow or failed provider must leave budget for unrelated evidence."""
        try:
            with self.session.budget(seconds, requests):
                return action()
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
            return evidence_coverage.unavailable(name, '', exc)

    def collect(self, item):
        # The session is shared across candidates, including RPC calls made by
        # collectors. Restore any outer context even when a collector fails.
        if self.assessed >= self.max_candidates:
            item['hourly_evidence'] = {'status': 'NOT_CHECKED', 'reason': 'Hourly candidate budget exhausted'}
            evidence_coverage.complete(item)
            return
        self.assessed += 1
        with self.session, self.session.budget(40, 45):
            with self.session.budget(7, 5):
                item['verification'] = verification.collect(item, self.fetch, include_entry=False)
            report = item['verification']
            report['execution'] = self.stage('0x', lambda: execution_quotes.collect(item, os.environ), seconds=3)
            if item.get('network') in kyber_quotes.CHAINS:
                report['kyber'] = self.stage('kyber', lambda: kyber_quotes.collect(item, os.environ), seconds=3)
            else:
                report['kyber'] = verification.observation('kyber', '', None, 'UNSUPPORTED', 'EVM route adapter unsupported on network')
            if item.get('network') in onchain.RPCS and re.fullmatch(r'0x[0-9a-fA-F]{40}', item.get('token_address', '')):
                info = ((report.get('contract_security', {}).get('raw') or {}).get('result') or {}).get(item['token_address'].lower(), {})
                # Exact-pool identity and holder balance observations; no LP
                # control or beneficial-owner verification is inferred.
                report['supply_comparison'] = self.stage('supply_comparison', lambda: supply_evidence.collect(item, self.fetch))
                report['onchain'] = self.stage('evm_rpc', lambda: onchain.collect(item, (info.get('holders') or [])[:8],
                    lock_descriptors=self.registry.get('lp_locks', {}).get(item['network'] + ':' + item['address'].lower(), [])), seconds=9, requests=24)
                report['source_controls'] = self.stage('sourcify', lambda: contract_sources.collect(item, self.fetch), seconds=5)

            report['unlocks'] = token_unlocks.collect(item, self.registry)
            if 'onchain' not in report:
                report['onchain'] = verification.observation('policy', '', None, 'UNSUPPORTED', 'No reviewed on-chain pool/holder adapter for network')
            if 'supply_comparison' not in report:
                report['supply_comparison'] = verification.observation('policy', '', None, 'UNSUPPORTED', 'No reviewed independent supply comparison adapter for network')
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
            evidence_coverage.complete(item)
            item['hourly_evidence'] = dict(status='COLLECTED', reason='Read-only observations; complete safety and execution remain unverified')

    def summary(self):
        return dict(candidates_assessed=self.assessed,
                    execution_configuration=execution_configuration.status(os.environ),
                    **self.session.summary())


def collect_safely(collector, item):
    """Optional research failure must not interrupt core Telegram delivery."""
    try:
        collector.collect(item)
    except Exception as exc:
        # Never expose exception text, credential-bearing URLs or raw bodies.
        item['hourly_evidence'] = dict(status='ERROR', reason='Optional collector failed: ' + type(exc).__name__)
    evidence_coverage.complete(item)


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
    return any((report.get(k) or {}).get('status') in ('FAIL', 'FAILED', 'HIGH CONCERN', 'CONFLICTING')
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


def rotate(items, watchlist):
    """Least recently checked exact tokens first; pool duplicates share a slot.

    Persisted observation times advance even for silent WAIT results. Stable
    score ordering breaks ties without making highest-ranked tokens permanent.
    """
    ordered = sorted(items, key=lambda x: (
        watchlist.get(x['key'], {}).get('evidence_checked_at', ''),
        -x.get('score', 0), x['key']))
    result, tokens = [], set()
    for item in ordered:
        token = item.get('token_address') or item.get('discovery_token_hint')
        identity = (item.get('network'), token if item.get('network') == 'solana' else str(token).lower())
        if not token:
            identity = (item.get('network'), item['key'])
        if identity not in tokens:
            tokens.add(identity)
            result.append(item)
    return result

