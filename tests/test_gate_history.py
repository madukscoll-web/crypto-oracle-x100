import copy
import datetime as dt
import unittest
from decimal import Decimal

import gate_history as gh
from atl_evidence import dossier, format_research, format_research_html, DETAILS
from atl_hourly_research import enrich

NOW = dt.datetime(2026, 11, 8, 3, tzinfo=dt.timezone.utc)
AT = NOW.isoformat()
TOKEN = '0x' + '1' * 40
DAY = gh.DAY
TODAY = int(NOW.timestamp()) // DAY * DAY


def candle(day_offset, low, high=None, closed=True):
    t = TODAY - day_offset * DAY
    high = high if high is not None else low * 1.5
    return [str(t), '1000', str(low * 1.2), str(high), str(low), str(low * 1.1), '10', 'true' if closed else 'false']


def rows(first_offset, last_offset, low=2.0):
    return [candle(o, low) for o in range(first_offset, last_offset - 1, -1)]


class FakeGate:
    def __init__(self, pages, book=None):
        self.pages = list(pages); self.urls = []; self.book = book

    def __call__(self, url):
        self.urls.append(url)
        if '/order_book' in url:
            if isinstance(self.book, Exception):
                raise self.book
            return self.book
        return self.pages.pop(0) if self.pages else []


GOOD_BOOK = {'bids': [['0.99', '1000'], ['0.98', '1000']], 'asks': [['1.01', '1000'], ['1.02', '1000']]}


class CollectTests(unittest.TestCase):
    def test_short_history_ends_at_first_candle_in_one_page(self):
        get = FakeGate([rows(400, 1)])
        h = gh.collect(get, 'EX_USDT', now=NOW.timestamp())
        self.assertEqual((h['pages'], h['candles'], h['reaches_first_candle']), (1, 400, True))
        self.assertEqual(h['coverage'], 'GATE_SPOT_DAILY_SINCE_FIRST_CANDLE')
        self.assertFalse(h['venue_lifetime_complete'])

    def test_long_history_pages_back_until_listing(self):
        get = FakeGate([rows(990, 1), rows(1500, 991)])
        h = gh.collect(get, 'EX_USDT', now=NOW.timestamp())
        self.assertEqual((h['pages'], h['reaches_first_candle']), (2, True))
        self.assertEqual(h['candles'], 990 + 510)

    def test_page_cap_marks_history_truncated(self):
        get = FakeGate([rows(990, 1), rows(1980, 991), rows(2970, 1981)])
        h = gh.collect(get, 'EX_USDT', now=NOW.timestamp(), max_pages=3)
        self.assertFalse(h['reaches_first_candle'])
        self.assertEqual(h['coverage'], 'GATE_SPOT_DAILY_TRUNCATED')

    def test_minimum_uses_intraday_low_and_date(self):
        page = rows(100, 1, low=3.0)
        page[50] = candle(50, 0.25)
        h = gh.collect(FakeGate([page]), 'EX_USDT', now=NOW.timestamp())
        self.assertEqual(Decimal(h['minimum_price_usd']), Decimal('0.25'))
        self.assertTrue(h['minimum_at'].startswith(dt.datetime.fromtimestamp(TODAY - 50 * DAY, dt.timezone.utc).date().isoformat()))

    def test_open_candle_and_bad_lows_ignored_but_malformed_rows_rejected(self):
        page = rows(10, 1) + [candle(0, 0.001, closed=False)]
        page.append([str(TODAY - 20 * DAY), '1', '1', '1', '0', '1', '1', 'true'])  # zero low
        h = gh.collect(FakeGate([page]), 'EX_USDT', now=NOW.timestamp())
        self.assertEqual(h['candles'], 10)
        self.assertEqual(Decimal(h['minimum_price_usd']), Decimal('2.0'))
        for bad in ([['x']], 'nope', [[1, 2, 3, 'NaN', 'NaN', 6]]):
            with self.assertRaises(ValueError):
                gh.collect(FakeGate([bad]), 'EX_USDT', now=NOW.timestamp())

    def test_empty_history_and_bad_pair_rejected(self):
        with self.assertRaises(ValueError):
            gh.collect(FakeGate([[]]), 'EX_USDT', now=NOW.timestamp())
        for pair in ('ex_usdt', 'EX_BTC', 'EX_USDT&x=1', '', None):
            with self.assertRaises(ValueError):
                gh.candle_url(pair, 0, 1)

    def test_duplicate_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            gh.collect(FakeGate([[candle(5, 1), candle(5, 1)]]), 'EX_USDT', now=NOW.timestamp())


class BookTests(unittest.TestCase):
    def test_depth_within_one_percent_and_spread(self):
        b = gh.collect_book(FakeGate([], GOOD_BOOK), 'EX_USDT', now=NOW.timestamp())
        self.assertEqual(b['bid_depth_usdt_1pct'], '990')   # 0.99*1000; 0.98 is outside 1% of mid 1.00
        self.assertEqual(b['ask_depth_usdt_1pct'], '1010')
        self.assertEqual(b['spread_bps'], '200.0')

    def test_crossed_empty_or_malformed_book_rejected(self):
        for book in ({'bids': [['1.1', '1']], 'asks': [['1.0', '1']]}, {'bids': [], 'asks': []}, {'bids': 'x', 'asks': 'y'},
                     {'bids': [['0', '1']], 'asks': [['1', '1']]}, None):
            with self.assertRaises(ValueError):
                gh.collect_book(FakeGate([], book), 'EX_USDT', now=NOW.timestamp())

    def test_book_failure_is_not_fatal_to_history(self):
        result = gh.collect_all(FakeGate([rows(30, 1)], OSError('down')), 'EX_USDT', now=NOW.timestamp())
        self.assertIsNone(result['book']); self.assertEqual(result['book_error'], 'OSError')
        self.assertEqual(result['history']['candles'], 30)


class ValidateTests(unittest.TestCase):
    def evidence(self):
        return gh.collect_all(FakeGate([rows(30, 1)], GOOD_BOOK), 'EX_USDT', now=NOW.timestamp())

    def test_valid_evidence_passes(self):
        gh.validate(self.evidence(), 'EX_USDT', NOW.timestamp())

    def test_tampering_is_rejected(self):
        for mutate in (lambda e: e['history'].update(venue_lifetime_complete=True),
                       lambda e: e['history'].update(pair='OTHER_USDT'),
                       lambda e: e['history'].update(source_urls=['https://evil.test/x']),
                       lambda e: e['history'].update(minimum_price_usd='0'),
                       lambda e: e['history'].update(minimum_price_usd='NaN'),
                       lambda e: e['history'].update(candles=0),
                       lambda e: e['history'].update(observed_at=(NOW - dt.timedelta(hours=5)).isoformat()),
                       lambda e: e['history'].update(minimum_at=(NOW - dt.timedelta(days=900)).isoformat()),
                       lambda e: e['book'].update(pair='OTHER_USDT'),
                       lambda e: e['book'].update(best_bid='0')):
            evidence = self.evidence(); mutate(evidence)
            with self.assertRaises(ValueError):
                gh.validate(evidence, 'EX_USDT', NOW.timestamp())


def inputs(provider_low='.99'):
    observation = dict(provider_id='example', provider_last_updated=AT, indicative_price_usd='1',
                       provider_atl_candidate=dict(source_atl_usd=provider_low, source_atl_date='2025-06-01T00:00:00Z'))
    details = dict(id='example', name='Fixture', symbol='EX', platforms={'ethereum': TOKEN}, categories=['Infrastructure'],
                   market_data=dict(current_price={'usd': 1}, market_cap={'usd': 200000000}, circulating_supply=200000000,
                                    total_volume={'usd': 1000000}, last_updated=AT))
    chart = {'prices': [[int((NOW - dt.timedelta(days=1)).timestamp() * 1000), 1.1], [int(NOW.timestamp() * 1000), 1]]}
    return observation, details, chart


def gate_meta():
    return dict(observed_at=AT, currencies=[dict(currency='EX', delisted=False, trade_disabled=False,
                                                  chains=[dict(name='ETH', addr=TOKEN)])],
                pairs=[dict(id='EX_USDT', base='EX', quote='USDT', trade_status='tradable', type='normal', st_tag=False)])


def venue(low=0.985, first_offset=700):
    page = rows(first_offset, 1, low=3.0)
    page[-5] = candle(5, low)
    return gh.collect_all(FakeGate([page], GOOD_BOOK), 'EX_USDT', now=NOW.timestamp())


class DossierIntegrationTests(unittest.TestCase):
    def build(self, **kw):
        observation, details, chart = inputs(kw.pop('provider_low', '.99'))
        return dossier(observation, details, chart, observed_at=AT, now=NOW.timestamp(), gate_evidence=gate_meta(), **kw)

    def test_valid_venue_history_is_shown_but_changes_no_authority(self):
        d = self.build(venue=venue())
        self.assertTrue(d['telegram_research_eligible'])
        self.assertFalse(d['history']['lifetime_verified'])
        self.assertFalse(d['buy_authorized']); self.assertFalse(d['orders_allowed'])
        self.assertIsNotNone(d['venue_history'])
        self.assertIn('Venue only; not a verified lifetime low', format_research(d))
        html = format_research_html(d)
        self.assertIn('Gate Venue History', html)
        self.assertIn('not a verified lifetime all-time low', html)
        self.assertIn('Gate book bid', html)

    def test_no_venue_leaves_alert_exactly_as_before(self):
        d = self.build()
        self.assertIsNone(d['venue_history'])
        self.assertNotIn('Gate Venue History', format_research_html(d))
        self.assertIn('Liquidity Depth:</b> Unknown', format_research_html(d))

    def test_gate_trading_below_claimed_atl_withholds_alert(self):
        d = self.build(venue=venue(low=0.5))
        self.assertFalse(d['telegram_research_eligible'])
        self.assertTrue(d['history']['conflicting'])
        self.assertTrue(any('Gate venue traded below' in g for g in d['gaps']))

    def test_history_starting_after_reported_low_date_is_disclosed(self):
        d = self.build(venue=venue(first_offset=100))
        self.assertTrue(d['telegram_research_eligible'])
        self.assertTrue(any('begins after the provider-reported low date' in g for g in d['gaps']))

    def test_invalid_or_mismatched_venue_is_rejected_without_granting_anything(self):
        bad = venue(); bad['history']['pair'] = 'OTHER_USDT'
        d = self.build(venue=bad)
        self.assertIsNone(d['venue_history'])
        self.assertTrue(any('Gate venue history rejected' in g for g in d['gaps']))

    def test_venue_without_exact_gate_listing_is_rejected(self):
        observation, details, chart = inputs()
        d = dossier(observation, details, chart, observed_at=AT, now=NOW.timestamp(), venue=venue())
        self.assertIsNone(d['venue_history'])

    def test_replay_input_round_trips(self):
        d = self.build(venue=venue())
        source = d['_source_input']
        again = dossier(source['observation'], source['details'], source['chart'], observed_at=source['observed_at'],
                        now=NOW.timestamp(), gate_evidence=source['gate_evidence'], venue=source['venue'])
        self.assertEqual(again['venue_history'], d['venue_history'])


class EnrichmentTests(unittest.TestCase):
    def run_enrich(self, gate_fetch):
        observation, details, chart = inputs()
        observation['provider_id'] = 'example'
        calls = []

        def fetch(url):
            calls.append(url)
            if url.startswith(DETAILS) and 'market_chart' not in url:
                return details
            if 'market_chart' in url:
                return chart
            return gate_fetch(url)
        result = dict(observations=[observation], research_dossiers=[], enrichment_errors=[],
                      status='OBSERVATIONS_UNVERIFIED')
        state = {}
        enrich(result, state, fetch, now=NOW, gate_evidence=gate_meta())
        return result, calls

    def test_enrichment_fetches_gate_history_for_exact_listing(self):
        pages = [rows(60, 1)]
        result, calls = self.run_enrich(lambda url: GOOD_BOOK if '/order_book' in url else [] if 'interval=1h' in url else pages.pop(0))
        self.assertTrue(any('/spot/candlesticks' in c for c in calls))
        self.assertIsNotNone(result['research_dossiers'][0]['venue_history'])

    def test_gate_outage_does_not_block_the_alert(self):
        def down(url): raise OSError('gate down')
        result, _ = self.run_enrich(down)
        self.assertEqual(len(result['research_dossiers']), 1)
        self.assertIsNone(result['research_dossiers'][0]['venue_history'])
        self.assertTrue(any('Gate venue history unavailable' in e['reason'] for e in result['enrichment_errors']))


if __name__ == '__main__':
    unittest.main()
