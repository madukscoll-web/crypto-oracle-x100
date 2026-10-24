"""Source identity, invalid provider data and fail-closed alert regressions."""
import datetime as dt
import unittest
from unittest.mock import patch
import fundamental_evidence as f
import investment_gates as gates
import crypto_oracle_scanner as scanner

NOW = dt.datetime(2026, 10, 24, 4, tzinfo=dt.timezone.utc)
AXIS = '0x5be75e3b0aff5d1a042a5363ae36acb1d6d755ea'


def item(**kw):
    value = dict(network='base', token_address=AXIS, address='exact-pool', score=100,
                 liquidity=2460000, volume=11940000, buy_share=.48,
                 observed_at=NOW.isoformat(), source='GeckoTerminal',
                 risk_category='WAIT / VERIFY')
    value.update(kw)
    return value


def payload(**kw):
    market = dict(circulating_supply=100, total_supply=150, max_supply=200,
                  market_cap={'usd': 1000}, fully_diluted_valuation={'usd': 2000})
    market.update(kw)
    return dict(platforms={'base': AXIS}, market_data=market, last_updated=NOW.isoformat())


class FundamentalsTests(unittest.TestCase):
    def test_exact_contract_observations_have_provenance_but_not_verification(self):
        report = f.collect(item(), lambda _: payload(), NOW)
        for key in f.FIELDS:
            r = report[key]
            self.assertEqual(r['status'], 'UNVERIFIED')
            self.assertEqual(r['contract'], AXIS)
            self.assertEqual(r['network'], 'base')
            self.assertEqual(r['observed_at'], NOW.isoformat())
        self.assertEqual(report['circulating_supply']['value'], 100)
        self.assertEqual(len(report['circulating_supply']['response_sha256']), 64)

    def test_wrong_contract_conflicts(self):
        value = payload(); value['platforms']['base'] = '0x' + '0' * 40
        report = f.collect(item(), lambda _: value, NOW)
        self.assertEqual(report['circulating_supply']['status'], 'CONFLICTING')
        self.assertIsNone(report['circulating_supply']['value'])

    def test_absent_and_nonfinite_supply_never_becomes_zero(self):
        for value in (None, 'NaN', 'Infinity', -1, True, {}, []):
            r = f.collect(item(), lambda _: payload(circulating_supply=value), NOW)
            self.assertIsNone(r['circulating_supply']['value'])
            self.assertEqual(r['circulating_supply']['status'], 'UNVERIFIED')

    def test_conflicting_supply(self):
        r = f.collect(item(), lambda _: payload(circulating_supply=1000), NOW)
        self.assertEqual(r['max_supply']['status'], 'CONFLICTING')

    def test_api_failure_and_malformed_payload(self):
        def fail(_): raise TimeoutError()
        for fetch in (fail, lambda _: {'market_data': []}, lambda _: None):
            r = f.collect(item(), fetch, NOW)
            self.assertTrue(all(v['status'] == 'UNVERIFIED' for v in r.values()))

    def test_unknown_identity_does_not_request(self):
        with patch('builtins.print'):
            def fail(_): self.fail('Must not fetch unidentified contract')
            r = f.collect(item(token_address='UNVERIFIED'), fail, NOW)
        self.assertTrue(all(v['value'] is None for v in r.values()))

    def test_solana_identity_is_case_sensitive(self):
        self.assertFalse(f.same_address('solana', 'AbC', 'abc'))
        self.assertTrue(f.same_address('base', AXIS, AXIS.upper()))

    def test_fake_verification_flags_leave_blockers(self):
        r = gates.assess(item(sellability_verified=True, tokenomics_verified=True,
                              holder_distribution_verified=True, executable_quote_verified=True))
        self.assertIn('independent sellability not verified', r['blockers'])
        self.assertFalse(r['buy_eligible'])
        self.assertEqual(r['decision'], 'WAIT / VERIFY')

    def test_large_unlock_and_missing_holders(self):
        r = gates.assess(item(circulating_supply=100, unlock_amount=80))
        self.assertTrue(any('Large claimed unlock' in x for x in r['warnings']))
        self.assertTrue(any('Top-holder' in x for x in r['blockers']))

    def test_stale_future_crossed_wide_and_thin_quotes(self):
        for stamp in ('2000-01-01T00:00:00Z', '2099-01-01T00:00:00Z'):
            r = gates.assess(item(execution_evidence=dict(network='base', token_address=AXIS,
                pool_address='exact-pool', observed_at=stamp, source='fabricated',
                source_url='https://example.org', bid=2, ask=1, spread_percent=5,
                depth_usd=1, slippage_percent=10)))
            self.assertTrue(any('stale or future' in x for x in r['blockers']))
            self.assertTrue(any('crossed' in x for x in r['blockers']))
            self.assertTrue(any('Wide' in x for x in r['warnings']))
            self.assertTrue(any('Thin' in x for x in r['warnings']))
            self.assertFalse(r['buy_eligible'])

    def test_old_pool_is_not_token_age_evidence(self):
        r = gates.assess(item(age_hours=100000, token_age='UNVERIFIED'))
        self.assertEqual(r['decision'], 'WAIT / VERIFY')
        self.assertFalse(r['buy_eligible'])

    def test_alert_safety_and_scenarios_survive_truncation(self):
        from test_signals import sample
        x = sample()
        x.update(name='AXIS/USDC', pool_class='NEW POOL', token_age='UNVERIFIED',
                 age_hours=10, token_symbol='AXIS', previous_pools='UNVERIFIED', trades=100,
                 buys=48, sells=52, flags=['very long diagnostic ' * 1000],
                 contract_security='UNVERIFIED', holder_concentration='UNVERIFIED',
                 liquidity_lock='UNVERIFIED', security_details='UNVERIFIED',
                 security_fields='UNVERIFIED', holder_details='UNVERIFIED', risk_reasons=['Incomplete'],
                 return_probabilities='UNVERIFIED', url='https://example.org',
                 source='GeckoTerminal', security_source='UNVERIFIED')
        with patch.dict('os.environ', TELEGRAM_BOT_TOKEN='test', TELEGRAM_CHAT_ID='test'), patch.object(scanner, 'send_message', return_value=True) as send:
            scanner.send_telegram(x)
        message = send.call_args.args[0]
        self.assertLessEqual(len(message), 4096)
        for phrase in ('FINAL DECISION: WAIT', 'BLOCKERS:', '3m / 12m / 3y', 'observed:'):
            self.assertIn(phrase, message)
