import unittest
from urllib.parse import parse_qs, urlsplit

from reversal_universe import collect


NOW = 1800000000


def pair(base, **changes):
    row = dict(id=base+'_USDT', base=base, quote='USDT', type='normal',
               trade_status='tradable', st_tag=False, buy_start=1, sell_start=1)
    row.update(changes)
    return row


class UniverseTests(unittest.TestCase):
    def source(self, rows, volumes=None):
        self.calls = []
        def fetch(url):
            self.calls.append(url)
            endpoint = urlsplit(url)
            if endpoint.path.endswith('/spot/currency_pairs'):
                return rows
            if endpoint.path.endswith('/spot/tickers'):
                return volumes if volumes is not None else [
                    dict(currency_pair=row['id'], quote_volume='2000000') for row in rows]
            if '/spot/currency_pairs/' in endpoint.path:
                return next(row for row in rows if row['id'] == endpoint.path.rsplit('/', 1)[-1])
            if endpoint.path.endswith('/spot/candlesticks'):
                args = parse_qs(endpoint.query)
                period = 604800 if args['interval'] == ['7d'] else 86400
                return [[str(NOW-(100-i)*period), '1000', str(100+i*.1),
                         str(101+i*.1), str(99+i*.1), str(100+i*.1), '10']
                        for i in range(100)]
            raise AssertionError('Unexpected endpoint: '+url)
        return fetch

    def test_rotation_covers_deferred_pairs_and_two_timeframes(self):
        fetch = self.source([pair('LINK'), pair('ONDO'), pair('RENDER')])
        first = collect(fetch=fetch, now=NOW, batch_size=2)
        second = collect(fetch=fetch, now=NOW, batch_size=2, cursor=first['next_cursor'])
        self.assertEqual(first['coverage']['deferred_pairs'], 1)
        self.assertEqual(first['status_counts'], {'RESEARCH_ONLY': 4})
        self.assertEqual({r['interval'] for r in first['results']}, {'1d', '1w'})
        self.assertEqual({r['pair'] for r in first['results']+second['results']},
                         {'LINK_USDT', 'ONDO_USDT', 'RENDER_USDT'})
        self.assertFalse(first['buy_authorized'])
        self.assertFalse(first['telegram_eligible'])

    def test_excluded_instruments_and_inactive_pairs_never_fetch_candles(self):
        fetch = self.source([pair('USDC'), pair('WBTC'), pair('BTC'), pair('LINK3L'),
                             pair('LINK', trade_status='untradable'),
                             pair('ONDO', delisting_time=NOW+1)])
        result = collect(fetch=fetch, now=NOW)
        self.assertEqual(result['coverage']['selected_pairs'], 0)
        self.assertEqual(len(self.calls), 2)

    def test_missing_malformed_and_duplicate_turnover_is_unknown(self):
        fetch = self.source([pair('LINK'), pair('ONDO'), pair('RENDER')], [
            dict(currency_pair='LINK_USDT', quote_volume='nan'),
            dict(currency_pair='ONDO_USDT', quote_volume='3000000'),
            dict(currency_pair='ONDO_USDT', quote_volume='3000000')])
        result = collect(fetch=fetch, now=NOW)
        self.assertEqual(result['coverage']['unknown_turnover'], 3)
        self.assertFalse(result['results'])

    def test_provider_outage_is_unknown_and_cursor_does_not_advance(self):
        def outage(url):
            raise OSError('fixture outage')
        result = collect(fetch=outage, now=NOW, cursor=7)
        self.assertEqual(result['coverage']['universe_status'], 'UNAVAILABLE')
        self.assertEqual(result['next_cursor'], 7)
        self.assertFalse(result['orders_allowed'])

    def test_stale_or_incomplete_history_never_becomes_watch(self):
        source = self.source([pair('LINK')])
        def fetch(url):
            if '/spot/candlesticks?' in url:
                return []
            return source(url)
        result = collect(fetch=fetch, now=NOW)
        self.assertEqual(result['coverage']['unavailable'], 2)
        self.assertEqual(result['coverage']['technical_watches'], 0)
