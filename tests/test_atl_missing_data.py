import copy
import datetime as dt
import unittest
from unittest import mock

import atl_onchain
import gate_history as gh
from atl_evidence import dossier, format_research_html, distance_text, DETAILS
from atl_hourly_research import enrich

try:
    from test_gate_history import NOW, AT, TOKEN, DAY, TODAY, inputs, gate_meta, venue
except ImportError:  # pragma: no cover
    from tests.test_gate_history import NOW, AT, TOKEN, DAY, TODAY, inputs, gate_meta, venue

CONTRACT = TOKEN.lower()
LOW_DAY = '2025-06-01'


def entry(**over):
    base = dict(network='eth', contract=CONTRACT, source='evm_rpc', observed_at=AT, identity='VERIFIED',
                total_supply='1000000000', decimals=18, security_status='UNKNOWN',
                security_reason='Token has an active owner wallet; what the owner can change is unverified',
                facts=['Contract code exists on-chain at the pinned block', 'On-chain total supply: 1000000000'])
    base.update(over)
    return base


def build(onchain=None, venue_block=None, provider_low='.99'):
    observation, details, chart = inputs(provider_low)
    return dossier(observation, details, chart, observed_at=AT, now=NOW.timestamp(), gate_evidence=gate_meta(),
                   venue=venue_block, onchain=onchain)


def intraday(low='0.98', day=LOW_DAY, covered=24):
    return dict(pair='EX_USDT', day=day, source_url='https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=EX_USDT&interval=1h',
                observed_at=AT, minimum_price_usd=low, minimum_at='2025-06-01T05:00:00+00:00',
                hours_covered=covered, hours_expected=24, scope='x')


class OnchainDossierTests(unittest.TestCase):
    def test_verified_facts_are_shown_and_gap_is_narrowed_without_granting_authority(self):
        d = build([entry()])
        self.assertTrue(d['telegram_research_eligible'])
        self.assertFalse(d['buy_authorized']); self.assertFalse(d['orders_allowed'])
        self.assertFalse(d['history']['lifetime_verified'])
        self.assertIn('Contract code exists on-chain at the pinned block', d['verified_facts'])
        self.assertNotIn('On-chain contract identity/security not independently verified', d['gaps'])
        self.assertTrue(any(g.startswith('On-chain security review incomplete') for g in d['gaps']))
        html = format_research_html(d)
        self.assertIn('Checked by the bot', html)

    def test_no_onchain_evidence_leaves_the_old_gap(self):
        d = build(None)
        self.assertIn('On-chain contract identity/security not independently verified', d['gaps'])
        self.assertEqual(d['verified_facts'], [])
        self.assertNotIn('Checked by the bot', format_research_html(d))

    def test_unverified_identity_never_removes_the_gap(self):
        d = build([entry(identity='UNVERIFIED', facts=[], total_supply=None)])
        self.assertIn('On-chain contract identity/security not independently verified', d['gaps'])
        self.assertEqual(d['verified_facts'], [])

    def test_security_fail_withholds(self):
        d = build([entry(security_status='FAIL', security_reason='Upgradeable proxy (EIP-1967 implementation set)')])
        self.assertFalse(d['telegram_research_eligible'])
        self.assertTrue(any('On-chain red flag' in g for g in d['gaps']))

    def test_provider_supply_above_onchain_total_withholds(self):
        self.assertFalse(build([entry(total_supply='100000000')])['telegram_research_eligible'])   # provider says 200,000,000
        self.assertTrue(build([entry(total_supply='1000000000')])['telegram_research_eligible'])

    def test_wrong_stale_or_malformed_evidence_is_rejected_not_trusted(self):
        for bad in ([entry(contract='0x' + '9' * 40)], [entry(observed_at=(NOW - dt.timedelta(hours=5)).isoformat())],
                    [entry(security_status='SAFE')], [entry(identity='MAYBE')], [entry(total_supply='-5')],
                    [entry(total_supply='nan')], [entry(facts=['x'] * 7)], [entry(identity='UNVERIFIED', facts=['claim'])],
                    'text', [], [entry(), entry(), entry()]):
            d = build(bad)
            self.assertEqual(d['verified_facts'], [], bad)
            self.assertIsNone(d['onchain_evidence'])
            self.assertTrue(any('On-chain evidence rejected' in g for g in d['gaps']))
            self.assertIn('On-chain contract identity/security not independently verified', d['gaps'])

    def test_replay_input_round_trips(self):
        d = build([entry()])
        source = d['_source_input']
        again = dossier(source['observation'], source['details'], source['chart'], observed_at=source['observed_at'],
                        now=NOW.timestamp(), gate_evidence=source['gate_evidence'], venue=source['venue'], onchain=source['onchain'])
        self.assertEqual(again['verified_facts'], d['verified_facts'])


class IntradayTests(unittest.TestCase):
    def with_intraday(self, **kw):
        block = venue()
        block['intraday'] = intraday(**kw)
        return build(None, block)

    def test_clean_hourly_low_is_a_checked_fact_and_narrows_the_gap(self):
        d = self.with_intraday()
        self.assertTrue(d['telegram_research_eligible'])
        self.assertTrue(any('Gate hourly low on the provider low date' in f for f in d['verified_facts']))
        self.assertIn('Independent circulating supply (vesting and unlocks) required', d['gaps'])
        self.assertFalse(any('Intraday low coverage' in g for g in d['gaps']))

    def test_hourly_trade_below_provider_low_withholds(self):
        d = self.with_intraday(low='0.50')
        self.assertFalse(d['telegram_research_eligible'])
        self.assertTrue(d['history']['conflicting'])

    def test_wrong_day_or_bad_values_are_rejected(self):
        for kw in (dict(day='2021-05-05'), dict(covered=0), dict(covered=25), dict(low='0')):
            d = self.with_intraday(**kw)
            self.assertIsNone(d['venue_history'], kw)
            self.assertTrue(any('Gate venue history rejected' in g for g in d['gaps']), kw)

    def test_without_intraday_the_old_gap_text_stays(self):
        d = build(None, venue())
        self.assertIn('Intraday low coverage and independent circulating supply required', d['gaps'])


class CollectIntradayTests(unittest.TestCase):
    DAYSTART = TODAY - 10 * DAY

    def hour(self, i, low, t=None):
        t = self.DAYSTART + i * 3600 if t is None else t
        return [str(t), '10', str(low), str(low * 2), str(low), str(low), '1', 'true']

    def test_finds_lowest_hour_and_counts_coverage(self):
        rows = [self.hour(i, 5.0) for i in range(24)]
        rows[7] = self.hour(7, 1.5)
        result = gh.collect_intraday(lambda url: rows, 'EX_USDT', self.DAYSTART + 100, now=NOW.timestamp())
        self.assertEqual((result['minimum_price_usd'], result['hours_covered']), ('1.5', 24))
        self.assertIn('interval=1h', result['source_url'])

    def test_rejects_uncompleted_day_duplicates_malformed_and_empty(self):
        with self.assertRaises(ValueError):
            gh.collect_intraday(lambda url: [], 'EX_USDT', TODAY, now=NOW.timestamp())
        dup = [self.hour(1, 2.0), self.hour(1, 2.0)]
        for rows in (dup, 'x', [['bad']], [], [self.hour(0, 0)]):
            with self.assertRaises(ValueError):
                gh.collect_intraday(lambda url, r=rows: r, 'EX_USDT', self.DAYSTART, now=NOW.timestamp())

    def test_ignores_rows_outside_the_day(self):
        rows = [self.hour(3, 4.0), self.hour(0, 0.1, t=self.DAYSTART - 3600), self.hour(0, 0.1, t=self.DAYSTART + DAY)]
        result = gh.collect_intraday(lambda url: rows, 'EX_USDT', self.DAYSTART, now=NOW.timestamp())
        self.assertEqual((result['minimum_price_usd'], result['hours_covered']), ('4.0', 1))


class CollectorTests(unittest.TestCase):
    class Stub:
        def __init__(self, supply=10 ** 27, code='0x6001', owner_word='0x' + '0' * 64):
            self.block = dict(number='0x10', hash='0xaa')
            self.supply, self.code, self.owner_word = supply, code, owner_word

        def snapshot(self):
            return self.block

        def call(self, method, params):
            if method == 'eth_getCode':
                return self.code
            if method == 'eth_getStorageAt':
                return '0x' + '0' * 64
            raise AssertionError(method)

        def read(self, contract, selector, args=''):
            word = lambda n: '0x' + format(n, '064x')
            return {'313ce567': word(18), '18160ddd': word(self.supply), '8da5cb5b': self.owner_word}[selector]

    def test_evm_collects_identity_supply_and_owner_state(self):
        entries = atl_onchain.collect([dict(network='eth', contract=TOKEN)], now=NOW.timestamp(),
                                      rpc_factory=lambda network: self.Stub())
        e = entries[0]
        self.assertEqual((e['identity'], e['total_supply'], e['decimals']), ('VERIFIED', '1000000000', 18))
        self.assertEqual(e['security_status'], 'LIMITED')
        self.assertTrue(any('renounced' in f for f in e['facts']))

    def test_no_code_at_address_is_unverified(self):
        e = atl_onchain.collect([dict(network='eth', contract=TOKEN)], now=NOW.timestamp(),
                                rpc_factory=lambda network: self.Stub(code='0x'))[0]
        self.assertEqual((e['identity'], e['facts']), ('UNVERIFIED', []))

    def test_failures_become_unverified_entries_never_exceptions(self):
        def boom(network):
            raise OSError('rpc down')
        e = atl_onchain.collect([dict(network='eth', contract=TOKEN)], now=NOW.timestamp(), rpc_factory=boom)[0]
        self.assertEqual((e['identity'], e['security_status']), ('UNVERIFIED', 'UNKNOWN'))

    def test_unsupported_networks_and_bad_contracts_are_skipped_and_count_is_capped(self):
        contracts = [dict(network='arbitrum', contract=TOKEN), dict(network='eth', contract='nonsense'),
                     dict(network='eth', contract=TOKEN)] * 3
        entries = atl_onchain.collect(contracts, now=NOW.timestamp(), rpc_factory=lambda n: self.Stub())
        self.assertLessEqual(len(entries), atl_onchain.MAX_CONTRACTS)

    def test_solana_maps_verified_mint_facts_and_authority_state(self):
        report = dict(onchain=dict(status='LIMITED', checks={
                          'legacy_spl_mint_identity': dict(status='VERIFIED'),
                          'mint_authority_revoked': dict(status='VERIFIED'),
                          'freeze_authority_revoked': dict(status='FAILED')},
                      metrics=dict(total_supply_base_units='1000000000000000', decimals=6)),
                      contract_security=dict(status='FAIL', reason='active freeze authority'))
        mint = '6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN'
        with mock.patch('solana_evidence.collect', return_value=report):
            e = atl_onchain.collect([dict(network='solana', contract=mint)], now=NOW.timestamp(), solana_request=lambda *a: {})[0]
        self.assertEqual((e['identity'], e['total_supply'], e['security_status']), ('VERIFIED', '1000000000', 'FAIL'))
        self.assertTrue(any('Freeze authority ACTIVE' in f for f in e['facts']))
        self.assertTrue(any('Mint authority revoked' in f for f in e['facts']))

    def test_solana_unsupported_mint_is_unverified(self):
        report = dict(onchain=dict(status='UNSUPPORTED', reason='unknown extension'), contract_security=dict(status='UNKNOWN'))
        with mock.patch('solana_evidence.collect', return_value=report):
            e = atl_onchain.collect([dict(network='solana', contract='6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN')],
                                    now=NOW.timestamp(), solana_request=lambda *a: {})[0]
        self.assertEqual((e['identity'], e['facts']), ('UNVERIFIED', []))


class MessageTests(unittest.TestCase):
    def test_missing_data_is_split_into_human_and_other(self):
        html = format_research_html(build([entry()]))
        self.assertIn('Needs a human to confirm', html)
        self.assertIn('Not verified yet', html)
        self.assertIn('First-trade/inception provenance', html.split('Needs a human to confirm')[1].split('Not verified yet')[0])
        self.assertIn('Executable liquidity', html.split('Not verified yet')[1])

    def test_negative_distance_is_explained_not_shown_as_negative_above(self):
        self.assertIn('BELOW the recorded low', distance_text('-1.17'))
        self.assertIn('above the low', distance_text('2.5'))
        self.assertNotIn('Above Low: -', format_research_html(build([entry()])))

    def test_venue_block_shows_new_low_in_words(self):
        block = venue(low=1.05)           # price 1.0 is under the lowest closed daily low
        html = format_research_html(build([entry()], block))
        self.assertIn('BELOW the lowest closed daily low', html)
        self.assertNotIn('Venue Low:</b> -', html)

    def test_compact_mode_drops_only_the_plain_english_block(self):
        d = build([entry()])
        full, compact = format_research_html(d), format_research_html(d, compact=True)
        self.assertIn('In Plain English', full)
        self.assertNotIn('In Plain English', compact)
        self.assertIn('NOT A VERIFIED ALL-TIME LOW', compact)
        self.assertIn('Needs a human to confirm', compact)

    def test_message_stays_within_telegram_limit(self):
        block = venue()
        block['intraday'] = intraday()
        text = format_research_html(build([entry(), entry(network='base')] if False else [entry()], block))
        self.assertLess(len(text.encode('utf-16-le')) // 2, 3900)


class EnrichWiringTests(unittest.TestCase):
    def run_enrich(self, rpc_factory, hourly):
        observation, details, chart = inputs('.99')
        observation['provider_id'] = 'example'

        def fetch(url):
            if url.startswith(DETAILS) and 'market_chart' not in url:
                return details
            if 'market_chart' in url:
                return chart
            if 'interval=1h' in url:
                return hourly
            if '/order_book' in url:
                return {'bids': [['0.99', '1000']], 'asks': [['1.01', '1000']]}
            return [[str(TODAY - o * DAY), '1', '3', '4', '3', '3', '1', 'true'] for o in range(60, 0, -1)]
        result = dict(observations=[observation], research_dossiers=[], enrichment_errors=[], status='OBSERVATIONS_UNVERIFIED')
        enrich(result, {}, fetch, now=NOW, gate_evidence=gate_meta(), rpc_factory=rpc_factory)
        return result

    def test_onchain_and_intraday_reach_the_dossier(self):
        hourly = [[str(int(dt.datetime(2025, 6, 1, h, tzinfo=dt.timezone.utc).timestamp())), '1', '3', '4', '3', '3', '1', 'true']
                  for h in range(24)]
        result = self.run_enrich(lambda network: CollectorTests.Stub(), hourly)
        d = result['research_dossiers'][0]
        self.assertIsNotNone(d['onchain_evidence'])
        self.assertTrue(any('Contract code exists' in f for f in d['verified_facts']))
        self.assertIsNotNone(d['venue_history'].get('intraday'))

    def test_failures_never_block_the_alert(self):
        def boom(network):
            raise OSError('down')
        result = self.run_enrich(boom, [])
        self.assertEqual(len(result['research_dossiers']), 1)
        self.assertTrue(any('Gate hourly low-day candles unavailable' in e['reason'] for e in result['enrichment_errors']))
        d = result['research_dossiers'][0]
        self.assertIn('On-chain contract identity/security not independently verified', d['gaps'])


if __name__ == '__main__':
    unittest.main()
