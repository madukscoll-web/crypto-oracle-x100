"""No-network tests for the fee-adjusted reversal backtest report."""
import unittest

import reversal_backtest_report as rb
from altcoin_reversal_cli import run

H = 3600


def candles(n=80, step=0.0, start=100.0):
    return [dict(timestamp=1700000000 + i * H, open=start + i * step, close=start + i * step,
                 high=start + i * step + 1, low=start + i * step - 1, volume=10, closed=True) for i in range(n)]


def row(pair, signals, base_candles):
    return dict(pair=pair, status='RESEARCH_ONLY', candle_count=len(base_candles), candles=base_candles,
                backtest=dict(observations=[dict(signal_at=1700000000 + k * 20 * H, net_return=r) for k, r in enumerate(signals)]))


class HelperTests(unittest.TestCase):
    def test_overlapping_signals_count_once_per_horizon(self):
        signals = [dict(signal_at=1700000000 + i * H, net_return=0.01) for i in range(25)]
        kept = rb.independent(signals, H)
        self.assertEqual([s['signal_at'] for s in kept], [1700000000, 1700000000 + 10 * H, 1700000000 + 20 * H])
        self.assertEqual(rb.independent([], H), [])

    def test_baseline_uses_next_open_and_horizon_close_net_of_cost(self):
        flat = rb.baseline_returns(candles(80))
        self.assertTrue(flat and all(abs(r + 0.004) < 1e-12 for r in flat))
        rising = rb.baseline_returns(candles(80, step=1.0))
        self.assertTrue(all(r > flat[0] for r in rising))
        self.assertEqual(rb.baseline_returns(candles(60)), [])

    def test_stats_handle_empty_and_hit_rate(self):
        self.assertEqual(rb.stats([]), dict(n=0, hit_rate=None, median_net=None))
        self.assertEqual(rb.stats([0.1, -0.1, 0.2])['hit_rate'], 0.6667)


class SummariseTests(unittest.TestCase):
    def result(self, per_pair, extra=()):
        return dict(results=[row('P%d_USDT' % i, s, candles()) for i, s in enumerate(per_pair)] + list(extra))

    def test_below_thirty_independent_signals_is_insufficient_never_a_conclusion(self):
        out = rb.summarise(self.result([[0.05] * 5, [0.05] * 5]), '1h')
        self.assertTrue(out['verdict'].startswith('INSUFFICIENT SAMPLE: 10 independent signals'))
        self.assertFalse(out['buy_authorized'])
        self.assertFalse(out['orders_allowed'])

    def test_thirty_signals_reports_signal_versus_baseline(self):
        out = rb.summarise(self.result([[0.02] * 10] * 3), '1h')
        self.assertTrue(out['verdict'].startswith('MEASURED:'))
        self.assertIn('not a forecast', out['verdict'])
        self.assertEqual(out['pooled_signal']['n'], 30)
        self.assertGreater(out['pooled_baseline']['n'], 0)

    def test_unavailable_pairs_are_listed_not_counted(self):
        bad = dict(pair='X_USDT', status='UNAVAILABLE', reason='ValueError: Excluded pair')
        out = rb.summarise(self.result([[0.01]], extra=[bad]), '4h')
        self.assertEqual(out['skipped'], [dict(pair='X_USDT', reason='ValueError: Excluded pair')])
        self.assertEqual(len(out['pairs']), 1)

    def test_no_usable_pairs_is_insufficient_not_a_crash(self):
        out = rb.summarise(dict(results=[dict(pair='X_USDT', status='UNAVAILABLE')]), '1h')
        self.assertIn('INSUFFICIENT SAMPLE: 0', out['verdict'])


def fake_fetch(url):
    if '/spot/currency_pairs/' in url:
        pair = url.rsplit('/', 1)[1]
        return dict(id=pair, base=pair[:-5], quote='USDT', type='normal', trade_status='tradable', st_tag=False,
                    buy_start=1, sell_start=1)
    if '/spot/candlesticks' in url:
        return [[str(1700000000 + i * H), '1000', str(100 + i * .1), str(101 + i * .1), str(99 + i * .1), str(100 + i * .1), '10']
                for i in range(100)]
    raise AssertionError('Unexpected public endpoint: ' + url)


class EndToEndTests(unittest.TestCase):
    def test_report_runs_on_mocked_gate_and_stays_research_only(self):
        out = rb.report(('LINK_USDT', 'USDC_USDT'), ('1h',), fetch=fake_fetch, now=1700000000 + 101 * H)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['pairs'][0]['pair'], 'LINK_USDT')
        self.assertEqual([s['pair'] for s in out[0]['skipped']], ['USDC_USDT'])
        self.assertIn('INSUFFICIENT SAMPLE', out[0]['verdict'])
        self.assertFalse(out[0]['buy_authorized'])

    def test_cli_default_still_drops_observations_and_candles(self):
        row_ = run(['LINK_USDT'], '1h', fetch=fake_fetch, now=1700000000 + 101 * H)['results'][0]
        self.assertNotIn('observations', row_['backtest'])
        self.assertNotIn('candles', row_)
        kept = run(['LINK_USDT'], '1h', fetch=fake_fetch, now=1700000000 + 101 * H, keep_observations=True)['results'][0]
        self.assertIn('observations', kept['backtest'])
        self.assertEqual(len(kept['candles']), 100)

    def test_workflow_is_read_only_and_manual_or_branch_triggered(self):
        import pathlib
        text = (pathlib.Path(__file__).resolve().parents[1] / '.github/workflows/reversal-backtest.yml').read_text()
        self.assertIn('contents: read', text)
        self.assertNotIn('schedule:', text)
        self.assertNotIn('secrets.', text)
