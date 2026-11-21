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


def btc(closes):
    return [dict(timestamp=1700000000 + i * H, open=c, close=c, high=c, low=c, volume=1, closed=True)
            for i, c in enumerate(closes)]


class RegimeTests(unittest.TestCase):
    def test_labels_follow_btc_trend_with_fixed_thresholds(self):
        falling = rb.regime_map(btc([100.0] * 24 + [96.0]))
        rising = rb.regime_map(btc([100.0] * 24 + [104.0]))
        flat = rb.regime_map(btc([100.0] * 24 + [101.0]))
        t = 1700000000 + 24 * H
        self.assertEqual((falling[t], rising[t], flat[t]), ('FALLING', 'RISING', 'SIDEWAYS'))
        self.assertEqual(rb.regime_map(btc([100.0] * 10)), {})

    def test_a_label_never_uses_later_candles(self):
        base = [100.0] * 24 + [96.0, 90.0, 80.0]
        changed = base[:25] + [200.0, 300.0]
        a, b = rb.regime_map(btc(base)), rb.regime_map(btc(changed))
        self.assertEqual(a[1700000000 + 24 * H], b[1700000000 + 24 * H])

    def test_baseline_points_share_the_signal_time_convention(self):
        c = candles(80)
        points = rb.baseline_points(c)
        self.assertEqual(points[0][0], c[rb.WARMUP - 1]['timestamp'])
        self.assertEqual([r for _, r in points], rb.baseline_returns(c))


class SliceVerdictTests(unittest.TestCase):
    def test_small_or_degenerate_samples_make_no_claim(self):
        self.assertTrue(rb.slice_verdict([0.1] * 10, [0.0] * 500, 8)[0].startswith('INSUFFICIENT SAMPLE: 10'))
        self.assertTrue(rb.slice_verdict([0.1] * 40, [0.0] * 5, 8)[0].startswith('INSUFFICIENT BASELINE'))
        self.assertTrue(rb.slice_verdict([0.1] * 40, [0.1] * 500, 8)[0].startswith('INSUFFICIENT SAMPLE: no variation'))

    def test_clear_edge_and_clear_loss_are_named_after_correction(self):
        good = [0.05 + 0.001 * (i % 5) for i in range(60)]
        bad = [-0.05 - 0.001 * (i % 5) for i in range(60)]
        base = [0.0 + 0.001 * (i % 7) for i in range(1000)]
        self.assertTrue(rb.slice_verdict(good, base, 8)[0].startswith('EDGE vs baseline after correcting for 8 variants'))
        self.assertTrue(rb.slice_verdict(bad, base, 8)[0].startswith('WORSE than baseline'))

    def test_noise_is_not_an_edge_and_more_variants_raise_the_bar(self):
        base = [0.001 * ((i * 7) % 11 - 5) for i in range(1000)]
        noise = [0.001 * ((i * 3) % 11 - 5) + 0.0005 for i in range(40)]
        self.assertIn('NO MEASURABLE EDGE', rb.slice_verdict(noise, base, 8)[0])
        edge = [0.002 * ((i * 3) % 11 - 5) + 0.0035 for i in range(40)]
        few, many = rb.slice_verdict(edge, base, 1), rb.slice_verdict(edge, base, 5000)
        self.assertTrue(few[0].startswith('EDGE'))
        self.assertIn('NO MEASURABLE EDGE', many[0])
        self.assertEqual(few[1], many[1])


class RegimeReportTests(unittest.TestCase):
    def result(self):
        c = candles(80)
        return dict(results=[row('P%d_USDT' % i, [0.05] * 12, c) for i in range(3)])

    def test_regime_slices_are_reported_with_the_variant_count(self):
        ref = btc([100.0] * 30 + [95.0] * 20 + [100.0] * 30)
        out = rb.summarise(self.result(), '1h', ref, 8)
        self.assertEqual(out['variants_tested'], 8)
        self.assertEqual(out['regime_status'], 'OK')
        self.assertEqual(set(out['regimes']), set(rb.REGIMES))
        self.assertIn('fixed in advance', out['regime_definition'])
        self.assertTrue(all(v['verdict'] for v in out['regimes'].values()))

    def test_missing_reference_gives_unavailable_regimes_not_a_crash(self):
        for ref in (None, [], btc([100.0] * 5)):
            out = rb.summarise(self.result(), '1h', ref, 8)
            self.assertIsNone(out['regimes'])
            self.assertTrue(out['regime_status'].startswith('UNAVAILABLE'))
            self.assertIn('pooled_test', out)

    def test_report_counts_every_pooled_test_and_regime_slice_as_a_variant(self):
        out = rb.report(('LINK_USDT',), ('1h', '4h'), fetch=fake_fetch, now=1700000000 + 101 * H)
        self.assertTrue(all(o['variants_tested'] == 8 for o in out))
        self.assertTrue(all(o['regime_status'] == 'OK' for o in out))

    def test_reference_fetch_failure_does_not_stop_the_report(self):
        def flaky(url):
            if 'BTC_USDT' in url and 'candlesticks' in url:
                raise OSError('boom')
            return fake_fetch(url)
        out = rb.report(('LINK_USDT',), ('1h',), fetch=flaky, now=1700000000 + 101 * H)
        self.assertTrue(out[0]['regime_status'].startswith('UNAVAILABLE'))
        self.assertEqual(out[0]['pairs'][0]['pair'], 'LINK_USDT')

