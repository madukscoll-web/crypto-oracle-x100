"""Production evidence plumbing, outage isolation and budget regressions."""
import unittest
from unittest.mock import patch
import urllib.error

import hourly_evidence as h
import investment_gates
from provider_session import Session, CURRENT, ProviderUnavailable

TOKEN = '0x' + '1' * 40
POOL = '0x' + '2' * 40


def item():
    return dict(network='base', token_address=TOKEN, address=POOL,
                risk_category='WAIT / VERIFY', liquidity=300000, volume=400000)


class HourlyEvidenceTests(unittest.TestCase):
    def test_collects_existing_adapters_and_gate_without_authorizing_buy(self):
        x = item()
        report = dict(sellability=dict(status='LIMITED', reason='Exact-pool simulation succeeded'),
                      contract_security=dict(status='LIMITED', reason='Provider screening only', raw={}))
        collector = h.HourlyEvidence()
        with patch.object(h.verification, 'collect', return_value=report), patch.object(
                h.onchain, 'collect', return_value={'status': 'LIMITED', 'reason': 'Pinned balances'}), patch.object(
                h.supply_evidence, 'collect', return_value={'status': 'LIMITED', 'reason': 'Gross supply only'}), patch.object(
                collector.gate, 'catalog'), patch.object(collector.gate, 'eligibility', return_value={
                    'status': 'CONFIRMED_SPOT', 'reason': 'Exact contract match'}), patch.object(
                collector.gate, 'research', return_value={'status': 'LIMITED', 'orders_allowed': False}):
            collector.collect(x)
        self.assertIn('onchain', x['verification'])
        self.assertIn('unlocks', x['verification'])
        self.assertEqual(x['gate_spot']['status'], 'CONFIRMED_SPOT')
        assessment = investment_gates.assess(x)
        self.assertFalse(assessment['buy_eligible'])
        self.assertEqual(assessment['live_findings']['Sell simulation']['status'], 'LIMITED')
        self.assertNotIn('independent sellability not verified', assessment['blockers'])
        self.assertTrue(any('Order-specific' in b for b in assessment['blockers']))
        self.assertIsNone(CURRENT.get())

    def test_provider_denied_and_unsupported_network_keep_alert_available(self):
        def denied(url, payload, headers, timeout):
            raise urllib.error.HTTPError(url, 403, 'private remote detail', {}, None)
        collector = h.HourlyEvidence(transport=denied)
        x = dict(network='solana', token_address='A' * 44, address='B' * 44)
        h.collect_safely(collector, x)
        self.assertEqual(x['hourly_evidence']['status'], 'COLLECTED')
        self.assertEqual(x['gate_spot']['status'], 'UNKNOWN')
        self.assertEqual(collector.session.requests, 1)
        self.assertIsNone(CURRENT.get())

    def test_candidate_budget_is_explicit(self):
        collector = h.HourlyEvidence(max_candidates=0)
        x = item()
        collector.collect(x)
        self.assertEqual(x['hourly_evidence']['status'], 'NOT_CHECKED')
        self.assertEqual(h.findings(x)['Sell simulation']['status'], 'NOT_CHECKED')
        self.assertEqual(collector.session.requests, 0)

    def test_failures_do_not_leak_exception_text(self):
        class Broken:
            def collect(self, x):
                raise ValueError('SECRET_TOKEN')
        x = item()
        h.collect_safely(Broken(), x)
        self.assertEqual(x['hourly_evidence']['status'], 'ERROR')
        self.assertNotIn('SECRET_TOKEN', str(x))

    def test_adverse_simulation_overrides_wait_in_assessment(self):
        x = item()
        x['verification'] = dict(sellability=dict(status='FAIL', reason='Honeypot'))
        self.assertTrue(h.adverse(x))
        self.assertEqual(investment_gates.assess(x)['decision'], 'AVOID / HIGH CONCERN')

    def test_partial_supply_and_lp_cannot_remove_complete_safety_requirements(self):
        x = item()
        x['verification'] = {k: dict(status='LIMITED', reason='Partial observations')
                             for k in ('onchain', 'supply_comparison', 'unlocks')}
        result = investment_gates.assess(x)
        self.assertFalse(result['buy_eligible'])
        self.assertTrue(any('beneficial ownership' in b for b in result['blockers']))
        self.assertTrue(any('vesting' in b for b in result['blockers']))

    def test_real_budget_caps_transport_timeout_and_blocks_later_calls(self):
        now = [0]
        timeouts = []
        def transport(url, payload, headers, timeout):
            timeouts.append(timeout)
            now[0] += 2
            return {}
        session = Session(max_seconds=1, clock=lambda: now[0], sleeper=lambda _: None, transport=transport)
        session.get('https://example.test/a')
        self.assertEqual(timeouts, [1])
        with self.assertRaises(ProviderUnavailable):
            session.get('https://example.test/b')
        self.assertEqual(len(timeouts), 1)

    def test_report_keeps_identity_and_full_evidence_link_before_diagnostics(self):
        x = item()
        x['verification'] = dict(sellability=dict(status='UNKNOWN', reason='Provider unavailable: HTTP 429'))
        with patch.dict('os.environ', GITHUB_REPOSITORY='owner/repo', GITHUB_RUN_ID='123'):
            text = investment_gates.telegram_summary(x)
        self.assertIn('HTTP 429', text)
        self.assertIn('actions/runs/123', text)
        self.assertIn('automatic trading disabled', text)
        self.assertNotIn('further evidence gaps', text)
