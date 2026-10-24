"""Deterministic fixtures; all amounts below are synthetic, not market evidence."""
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evidence_checks as c
import research_records
import crypto_oracle_scanner as scanner

NOW = dt.datetime(2026, 10, 24, 4, tzinfo=dt.timezone.utc)
ITEM = dict(network='base', token_address='0x'+'1'*40, address='0x'+'2'*40,
            quote_token_address='0x'+'3'*40, circulating_supply=100)


def record(**changes):
    value = dict(provider='fixture provider', origin='independent-a',
                 source_url='https://fixture.invalid/report', network=ITEM['network'],
                 contract=ITEM['token_address'], pool=ITEM['address'], observed_at=NOW.isoformat())
    value.update(changes)
    if value.get('origin') == 'independent-b' and 'source_url' not in changes:
        value['source_url'] = 'https://other-fixture.invalid/report'
    return value


def supplies():
    values = dict(circulating_supply=100, total_supply=150, max_supply=200,
                  market_cap_usd=1000, fdv_usd=2000)
    return [record(values=values), record(origin='independent-b', values=values.copy())]


def schedule(**changes):
    return record(coverage_start=(NOW-dt.timedelta(days=1)).isoformat(),
                  coverage_end=(NOW+dt.timedelta(days=365)).isoformat(),
                  events=[dict(at=(NOW+dt.timedelta(days=1)).isoformat(), amount=50)], **changes)


def quote(**changes):
    values = dict(quote_token=ITEM['quote_token_address'], quote_id='fixture-quote',
                  block_number=12345, kind='EXECUTABLE', expires_at=(NOW+dt.timedelta(seconds=60)).isoformat(),
                  bid=10, ask=10, depth_usd=10000, order_usd=1000, buy_amount_in=1000,
                  buy_amount_out=100, sell_amount_in=100, sell_amount_out=1000, fees_usd=0,
                  slippage_percent=0)
    values.update(changes)
    return record(**values)


class EvidenceChecksTests(unittest.TestCase):
    def test_two_sources_corroborate_without_verifying_authenticity(self):
        r = c.supply(supplies(), ITEM, NOW)
        self.assertTrue(all(x['status'] == 'CORROBORATED' for x in r.values()))
        self.assertFalse(c.review(dict(ITEM, research_records={'supply': supplies()}), NOW)['buy_eligible'])

    def test_same_origin_mirrors_are_not_independent(self):
        records = supplies(); records[1]['origin'] = records[0]['origin']
        self.assertEqual(c.supply(records, ITEM, NOW)['max_supply']['status'], 'UNVERIFIED')

    def test_conflicting_supply_sources(self):
        records = supplies(); records[1]['values']['circulating_supply'] = 10
        self.assertEqual(c.supply(records, ITEM, NOW)['circulating_supply']['status'], 'CONFLICTING')

    def test_impossible_supply_constraint(self):
        records = supplies()
        for r in records: r['values']['circulating_supply'] = 201
        self.assertEqual(c.supply(records, ITEM, NOW)['max_supply']['status'], 'CONFLICTING')

    def test_missing_and_fake_supply_values(self):
        for value in (None, True, 'NaN', 'Infinity', -1, {}, []):
            records = supplies()
            for r in records: r['values']['circulating_supply'] = value
            self.assertEqual(c.supply(records, ITEM, NOW)['circulating_supply']['status'], 'UNVERIFIED')

    def test_wrong_chain_contract_future_stale_and_unidentified_source(self):
        for change in ({'network': 'bsc'}, {'contract': '0xother'}, {'source_url': 'http://fixture.invalid'},
                       {'source_url': 'https://[invalid'}, {'origin': ''}, {'observed_at': '2020-01-01T00:00:00Z'},
                       {'observed_at': '2099-01-01T00:00:00Z'}, {'observed_at': '2026-10-24T04:00:00'}):
            self.assertFalse(c.provenance(record(**change), ITEM, NOW))

    def test_huge_upcoming_unlock(self):
        r = c.unlocks([schedule(), schedule(origin='independent-b')], ITEM, NOW, 100)
        self.assertEqual(r['status'], 'CORROBORATED')
        self.assertTrue(r['large_unlock'])
        self.assertEqual(r['fraction'], '0.5')

    def test_absent_coverage_is_not_no_unlocks(self):
        r = schedule(); r.pop('coverage_end'); r['events'] = []
        self.assertEqual(c.unlocks([r], ITEM, NOW)['status'], 'UNVERIFIED')

    def test_explicit_no_unlocks_requires_two_covered_schedules(self):
        a, b = schedule(), schedule(origin='independent-b')
        a['events'] = []; b['events'] = []
        r = c.unlocks([a, b], ITEM, NOW, 100)
        self.assertEqual(r['upcoming_amount'], '0')
        self.assertFalse(r['large_unlock'])

    def test_conflicting_unlocks(self):
        a, b = schedule(), schedule(origin='independent-b'); b['events'][0]['amount'] = 80
        self.assertEqual(c.unlocks([a, b], ITEM, NOW)['status'], 'CONFLICTING')

    def test_complete_holder_snapshot_and_source_bound_exclusions(self):
        rows = [dict(address='holder'+str(i), balance=10) for i in range(20)]
        rows.append(dict(address='lp', balance=100, exclusion=record(kind='LP', holder='lp')))
        r = c.holders(record(total_supply=300, complete=True, holders=rows), ITEM, NOW)
        self.assertEqual(r['adjusted_top10_fraction'], '0.5')
        self.assertEqual(r['denominator'], '200')
        self.assertEqual(r['status'], 'OBSERVED')

    def test_unverified_holder_exclusions_incomplete_and_duplicate(self):
        for changes in ({'complete': False}, {'holders': []},
                        {'holders': [dict(address='lp', balance=100, exclusion={'kind': 'LP'})]},
                        {'holders': [dict(address='a', balance=50), dict(address='a', balance=50)]}):
            r = c.holders(record(total_supply=100, complete=True, holders=[dict(address='a', balance=100)]) | changes, ITEM, NOW)
            self.assertEqual(r['status'], 'UNVERIFIED')

    def test_excessive_holders_and_wrong_total(self):
        r = record(total_supply=100, complete=True, holders=[dict(address='a', balance=100)])
        self.assertTrue(c.holders(r, ITEM, NOW)['excessive'])
        r['total_supply'] = 101
        self.assertEqual(c.holders(r, ITEM, NOW)['status'], 'CONFLICTING')

    def test_quote_zero_spread_and_slippage_valid_metrics_never_buy(self):
        r = c.quotes(quote(), ITEM, NOW)
        self.assertEqual(r['spread_percent'], '0')
        self.assertTrue(r['acceptable_metrics'])
        self.assertFalse(r['trade_ready'])

    def test_missing_quote_fields_do_not_become_zero(self):
        for key in ('fees_usd', 'slippage_percent', 'bid', 'ask', 'depth_usd', 'order_usd',
                    'buy_amount_out', 'sell_amount_out', 'quote_id', 'block_number', 'expires_at'):
            r = quote(); r.pop(key)
            self.assertEqual(c.quotes(r, ITEM, NOW)['status'], 'UNVERIFIED', key)

    def test_crossed_wide_thin_and_high_slippage(self):
        self.assertEqual(c.quotes(quote(bid=12, ask=10), ITEM, NOW)['status'], 'CONFLICTING')
        r = c.quotes(quote(bid=9, ask=10, depth_usd=1, slippage_percent=4), ITEM, NOW)
        self.assertEqual(len(r['flags']), 3)
        self.assertFalse(r['acceptable_metrics'])

    def test_wrong_pool_quote_token_or_expired(self):
        for changes in ({'pool': 'wrong'}, {'quote_token': 'wrong'}, {'expires_at': NOW.isoformat()},
                        {'observed_at': (NOW-dt.timedelta(seconds=121)).isoformat()}):
            self.assertEqual(c.quotes(quote(**changes), ITEM, NOW)['status'], 'UNVERIFIED')

    def test_provider_not_flagged_is_never_security_verification(self):
        fields = dict.fromkeys(('is_honeypot', 'owner_change_balance', 'hidden_owner', 'is_blacklisted', 'cannot_sell_all'), '0')
        self.assertEqual(c.security(record(findings=fields), ITEM, NOW)['status'], 'UNVERIFIED')
        for fake in (False, True, 'safe', [], {}):
            self.assertEqual(c.security(record(findings={'is_honeypot': fake}), ITEM, NOW)['status'], 'UNVERIFIED')
        fields['is_honeypot'] = '1'
        review = c.review(dict(ITEM, research_records={'security': record(findings=fields)}), NOW)
        self.assertEqual(review['security']['status'], 'HIGH CONCERN')
        self.assertEqual(scanner.decision_summary(dict(ITEM, evidence_review=review))[0], 'DISCARD')

    def test_malformed_records_fail_closed(self):
        for value in (None, [], 'invalid', 1):
            r = c.review(dict(ITEM, research_records=value), NOW)
            self.assertFalse(r['buy_eligible'])
        for value in (None, {}, 'bad'):
            self.assertEqual(c.supply(value, ITEM, NOW)['max_supply']['status'], 'UNVERIFIED')


class OfflineFileTests(unittest.TestCase):
    def test_optional_file_absent_and_malformed(self):
        with patch.dict(os.environ, ORACLE_EVIDENCE_FILE=''):
            self.assertEqual(research_records.load_for(ITEM)[0], {})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'records.json'
            with patch.dict(os.environ, ORACLE_EVIDENCE_FILE=str(path)):
                for data in ('bad', '[]', '{"schema_version":2}', '{"schema_version":1,"tokens":[]}'):
                    path.write_text(data)
                    self.assertEqual(research_records.load_for(ITEM)[0], {})
                entry = dict(network=ITEM['network'], contract=ITEM['token_address'], pool=ITEM['address'], records={'supply': supplies()})
                path.write_text(json.dumps(dict(schema_version=1, tokens=[entry])))
                self.assertEqual(len(research_records.load_for(ITEM)[0]['supply']), 2)
                path.write_text(json.dumps(dict(schema_version=1, tokens=[entry, entry])))
                self.assertEqual(research_records.load_for(ITEM)[0], {})


class HardeningTests(unittest.TestCase):
    def test_provenance_rejects_nonstring_origins(self):
        for value in ({}, [], True, 1):
            self.assertFalse(c.provenance(record(origin=value), ITEM, NOW))

    def test_huge_numbers_and_boolean_values_are_rejected(self):
        for value in ('1e999999', '9'*101, True, False, 'NaN', '-Infinity'):
            self.assertIsNone(c.numeric(value))

    def test_malformed_supply_payloads_are_unknown(self):
        for value in (None, [], 1, 'bad'):
            self.assertEqual(c.supply([record(values=value)], ITEM, NOW)['total_supply']['status'], 'UNVERIFIED')

    def test_offline_security_record_cannot_hide_live_provider_flags(self):
        item = dict(ITEM, security_provider_evidence=dict(source_url='https://fixture.invalid',
                    retrieved_utc=NOW.isoformat(), findings={'is_honeypot': '1'}, values={}))
        combined = research_records.combine(item, {'security': record(findings={'is_honeypot': '0'})})
        self.assertEqual(c.review(dict(item, research_records=combined), NOW)['provider_security']['status'], 'HIGH CONCERN')

    def test_forged_authenticated_quote_never_validates_execution(self):
        value = dict(ITEM, execution_evidence=dict(network='base', token_address=ITEM['token_address'],
            pool_address=ITEM['address'], verified=True, provider_authenticated=True,
            provider='fixture', quote_id='fake', direction='BUY', amount_in=100,
            amount_out=100, slippage_percent=0, observed_at=NOW.isoformat()))
        self.assertFalse(scanner.validate_execution_evidence(value))


class IndependenceAndThresholdTests(unittest.TestCase):
    def test_common_provider_mirrors_do_not_corroborate(self):
        rows = supplies()
        rows[0]['source_url'] = 'https://api.coingecko.com/report'
        rows[1]['source_url'] = 'https://api.geckoterminal.com/report'
        self.assertEqual(c.supply(rows, ITEM, NOW)['max_supply']['status'], 'UNVERIFIED')

    def test_configurable_depth_and_concentration_thresholds(self):
        rows = [dict(address='a', balance=100)]
        value = dict(ITEM, research_records={'execution': quote(depth_usd=2000),
                                           'holders': record(complete=True, total_supply=100, holders=rows)})
        with patch.dict(os.environ, ORACLE_MIN_DEPTH_USD='5000', ORACLE_TOP10_WARNING='1'):
            r = c.review(value, NOW)
        self.assertIn('Thin executable depth', r['execution']['flags'])
        self.assertFalse(r['holders']['excessive'])

    def test_bad_thresholds_use_finite_defaults(self):
        for bad in ('NaN', 'Infinity', '-1', 'true', '1e999999'):
            with patch.dict(os.environ, ORACLE_MIN_DEPTH_USD=bad):
                self.assertEqual(c.setting('ORACLE_MIN_DEPTH_USD', 1000), 1000)
