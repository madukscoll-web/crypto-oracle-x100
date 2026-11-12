import datetime as dt
import random
import unittest

import pattern_lab as lab

NOW = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)
ADDR = '0x' + 'ab' * 20


def item(key='base:0x1', **over):
    base = dict(key=key, network='base', token_address=ADDR, base_token_price_usd=1.0, liquidity=50000,
                volume=100000, trades=300, buy_share=0.55, change_h1=2.0, change_h24=10.0, age_hours=5, score=60,
                verification=dict(contract_security=dict(status='UNKNOWN')))
    base.update(over)
    return base


def synthetic(count, win_if, seed=1):
    """Rows with measured 24h outcomes; win_if(features) decides the planted winners."""
    rng = random.Random(seed)
    data = {'version': 1, 'rows': {}}
    for i in range(count):
        t0 = NOW - dt.timedelta(hours=400 - i * 0.5)
        f = lab.features(item(liquidity=rng.uniform(5000, 500000), volume=rng.uniform(1000, 900000),
                              trades=rng.randint(5, 900), buy_share=rng.random(), change_h1=rng.uniform(-40, 80),
                              change_h24=rng.uniform(-60, 200), age_hours=rng.uniform(0.2, 48), score=rng.randint(10, 90)))
        win = win_if(f, rng)
        price = 1.3 if win else 0.6
        data['rows'][f'base:0x{i:040x}'] = dict(t0=t0.isoformat(), price0=1.0, token_address=ADDR, features=f,
            obs=[dict(at=(t0 + dt.timedelta(hours=25)).isoformat(), price=price, liquidity=60000, horizon=24, age_hours=25)])
    return data


class CaptureTests(unittest.TestCase):
    def test_first_sight_only_and_never_rewritten(self):
        data = {'version': 1, 'rows': {}}
        self.assertTrue(lab.capture(data, item(), NOW))
        before = dict(data['rows']['base:0x1'])
        self.assertFalse(lab.capture(data, item(liquidity=1), NOW))
        self.assertEqual(data['rows']['base:0x1'], before)

    def test_unverified_or_unpriced_or_malformed_are_not_recorded(self):
        data = {'version': 1, 'rows': {}}
        for bad in (item(token_address='UNVERIFIED'), item(base_token_price_usd=0), item(base_token_price_usd=True),
                    item(base_token_price_usd='nan'), item(key=''), item(key='nocolon')):
            self.assertFalse(lab.capture(data, bad, NOW))
        self.assertEqual(data['rows'], {})

    def test_missing_values_stay_none_not_zero(self):
        f = lab.features(item(liquidity=None, volume='junk'))
        self.assertIsNone(f['liquidity'])
        self.assertIsNone(f['volume_to_liquidity'])
        self.assertEqual(f['goplus'], 'UNKNOWN')

    def test_per_run_and_total_caps(self):
        data = {'version': 1, 'rows': {}}
        added = [0]
        for i in range(10):
            lab.capture(data, item(key=f'base:0x{i}'), NOW, limit=3, added=added)
        self.assertEqual(len(data['rows']), 3)
        original = lab.MAX_ROWS
        lab.MAX_ROWS = 3
        try:
            self.assertFalse(lab.capture(data, item(key='base:0xnew'), NOW))
        finally:
            lab.MAX_ROWS = original


class OutcomeTests(unittest.TestCase):
    def row(self, price, liquidity=60000, horizon=24):
        return dict(t0=NOW.isoformat(), price0=1.0, token_address=ADDR, features={},
                    obs=[dict(at=NOW.isoformat(), price=price, liquidity=liquidity, horizon=horizon)])

    def test_net_of_cost_and_unexitable_is_total_loss(self):
        self.assertAlmostEqual(lab.outcome(self.row(1.5)), 50.0 - lab.ASSUMED_COST_PERCENT)
        self.assertEqual(lab.outcome(self.row(3.0, liquidity=100)), -100.0)
        self.assertEqual(lab.outcome(self.row(3.0, liquidity=None)), -100.0)

    def test_unmeasured_is_none_and_wrong_horizon_ignored(self):
        self.assertIsNone(lab.outcome(dict(t0=NOW.isoformat(), price0=1.0, obs=[])))
        self.assertIsNone(lab.outcome(self.row(2.0, horizon=72), horizon=24))


class RepriceTests(unittest.TestCase):
    def setup(self):
        data = {'version': 1, 'rows': {}}
        lab.capture(data, item(), NOW - dt.timedelta(hours=25))
        return data

    def payload(self, address='0x1', token=ADDR, price='2.0', liquidity='60000'):
        return dict(data=[dict(attributes=dict(address=address, base_token_price_usd=price, reserve_in_usd=liquidity),
                               relationships=dict(base_token=dict(data=dict(id='base_' + token))))])

    def test_prices_inside_window_and_tags_horizon(self):
        data = self.setup()
        report = lab.reprice(data, lambda url: self.payload(), NOW)
        self.assertEqual(report['priced'], 1)
        self.assertEqual(data['rows']['base:0x1']['obs'][0]['horizon'], 24)

    def test_late_price_is_not_tagged_as_the_horizon(self):
        data = {'version': 1, 'rows': {}}
        lab.capture(data, item(), NOW - dt.timedelta(hours=60))   # 24h window closed at 36h
        report = lab.reprice(data, lambda url: self.payload(), NOW)
        self.assertEqual(report['priced'], 0)
        self.assertIsNone(lab.outcome(data['rows']['base:0x1']))

    def test_identity_mismatch_not_spliced(self):
        data = self.setup()
        report = lab.reprice(data, lambda url: self.payload(token='0x' + 'cd' * 20), NOW)
        self.assertEqual((report['identity_mismatch'], report['priced']), (1, 0))

    def test_missing_pool_becomes_vanished_after_three_and_counts_as_loss(self):
        data = self.setup()
        for i in range(3):
            lab.reprice(data, lambda url: dict(data=[]), NOW + dt.timedelta(hours=i))
        self.assertEqual(data['rows']['base:0x1']['status'], 'VANISHED')
        self.assertEqual(lab.outcome(data['rows']['base:0x1']), -100.0)

    def test_provider_failures_stop_without_raising(self):
        for error, label in ((OSError('down'), 'PROVIDER_ERROR'), (ValueError('bad'), 'PROVIDER_ERROR')):
            data = self.setup()
            def fetch(url, error=error):
                raise error
            self.assertEqual(lab.reprice(data, fetch, NOW)['stopped'], label)
        data = self.setup()
        self.assertEqual(lab.reprice(data, lambda url: dict(data='x'), NOW)['stopped'], 'MALFORMED_RESPONSE')

    def test_batch_budget_respected(self):
        data = {'version': 1, 'rows': {}}
        for i in range(100):
            lab.capture(data, item(key=f'base:0x{i:040x}'), NOW - dt.timedelta(hours=25))
        calls = []
        lab.reprice(data, lambda url: calls.append(url) or dict(data=[]), NOW, max_batches=2)
        self.assertEqual(len(calls), 2)


class StudyTests(unittest.TestCase):
    def test_small_sample_reports_no_pattern(self):
        report = lab.study(synthetic(50, lambda f, r: f['score'] > 50))
        self.assertTrue(report['conclusion'].startswith('INSUFFICIENT SAMPLE'))
        self.assertEqual(report['patterns'], [])

    def test_planted_pattern_is_found_out_of_sample(self):
        # high buy_share wins 90% of the time; everything else wins 25%
        report = lab.study(synthetic(900, lambda f, r: r.random() < (0.9 if f['buy_share'] > 0.67 else 0.25)))
        features = {(p['feature'], p['level']) for p in report['patterns']}
        self.assertIn(('buy_share', 'high'), features)
        self.assertTrue(all(p['test_n'] >= lab.MIN_BUCKET and p['lift_vs_base'] >= lab.MIN_LIFT for p in report['patterns']))

    def test_pure_noise_yields_no_pattern(self):
        for seed in range(5):
            report = lab.study(synthetic(900, lambda f, r: r.random() < 0.4, seed=seed))
            self.assertEqual(report['patterns'], [], seed)
            self.assertIn('No feature separated', report['conclusion'])

    def test_pattern_present_only_in_training_period_is_rejected(self):
        counter = {'n': 0}
        def win(f, r):
            counter['n'] += 1
            early = counter['n'] <= 630                       # first 70% = training period
            return r.random() < (0.9 if early and f['buy_share'] > 0.67 else 0.3)
        report = lab.study(synthetic(900, win))
        self.assertNotIn(('buy_share', 'high'), {(p['feature'], p['level']) for p in report['patterns']})

    def test_wilson_interval_basics(self):
        low, high = lab.wilson(50, 100)
        self.assertTrue(low < 0.5 < high)
        self.assertEqual(lab.wilson(0, 0), (0.0, 1.0))

    def test_summary_line_never_claims_profit(self):
        line = lab.summary_line(lab.study(synthetic(50, lambda f, r: True)))
        self.assertIn('INSUFFICIENT SAMPLE', line)


class StorageTests(unittest.TestCase):
    def test_roundtrip_and_corrupt_file_rejected(self):
        import pathlib, tempfile
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'p.json'
            self.assertEqual(lab.load(path)['rows'], {})
            data = {'version': 1, 'rows': {}}
            lab.capture(data, item(), NOW)
            lab.save(data, path)
            self.assertEqual(lab.load(path), data)
            path.write_text('[]')
            with self.assertRaises(ValueError):
                lab.load(path)


if __name__ == '__main__':
    unittest.main()
