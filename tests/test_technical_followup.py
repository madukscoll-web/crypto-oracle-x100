import copy
import datetime as dt
import unittest
from unittest.mock import patch
import technical_followup as f

NOW = 1800000000
PAIR = 'BNB_USDT'

def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()

def receipt():
    return {'delivered_at': iso(NOW-3600), 'interval': '1w', 'entry_trigger': 110, 'invalidation': 80}


def fetch(now, midpoint=100):
    def get(url):
        if '/currency_pairs/' in url:
            return {'id': PAIR, 'base': 'BNB', 'quote': 'USDT', 'type': 'normal', 'trade_status': 'tradable', 'st_tag': False}
        return {'current': int(now*1000), 'update': int(now*1000),
                'asks': [[str(midpoint+.1), '100']], 'bids': [[str(midpoint-.1), '100']]}
    return get


class FollowupTests(unittest.TestCase):
    def run_sample(self, state, now=NOW, midpoint=100, transport=None):
        return f.collect({PAIR: receipt()}, state, transport or fetch(now, midpoint), now, [PAIR])

    def test_existing_alert_starts_at_fresh_observation_not_old_receipt(self):
        state = {'version': 1, 'hypotheses': {}}
        report = self.run_sample(state)
        row = next(iter(state['hypotheses'].values()))
        self.assertEqual(row['monitoring_started_at'], iso(NOW))
        self.assertEqual(row['original_alert_entry_price'], 'UNKNOWN_NOT_RECONSTRUCTED')
        self.assertFalse(report['buy_authorized'])
        self.assertEqual(report['hypotheses'][0]['strategy_return'], 'UNKNOWN')
        self.assertTrue(all(x['status'] == 'PENDING' for x in report['hypotheses'][0]['horizons']))
        old = copy.deepcopy(state)
        self.run_sample(state)
        self.assertEqual(state, old)

    def test_horizon_is_price_change_not_pnl_and_late_sample_is_not_return(self):
        state = {'version': 1, 'hypotheses': {}}
        self.run_sample(state)
        report = self.run_sample(state, NOW+86400, 110)
        horizon = report['hypotheses'][0]['horizons'][0]
        self.assertEqual(horizon['status'], 'OBSERVED_PRICE_CHANGE_ONLY')
        self.assertEqual(float(horizon['midpoint_change_percent']), 10)
        state = {'version': 1, 'hypotheses': {}}
        self.run_sample(state)
        report = self.run_sample(state, NOW+2*86400, 110)
        self.assertEqual(report['hypotheses'][0]['horizons'][0]['status'], 'NO_TIMELY_SAMPLE')
        self.assertNotIn('midpoint_change_percent', report['hypotheses'][0]['horizons'][0])

    def test_stale_book_outage_and_capacity_preserve_history(self):
        state = {'version': 1, 'hypotheses': {}}
        self.run_sample(state)
        old = copy.deepcopy(state)
        report = self.run_sample(state, NOW+3600, transport=fetch(NOW))
        self.assertTrue(report['errors']); self.assertEqual(state, old)
        with patch.object(f, 'MAX_SAMPLES', 1):
            report = self.run_sample(state, NOW+3600)
            self.assertEqual(report['outcomes'][PAIR], 'SAMPLE_CAPACITY_REACHED')
        self.assertEqual(state, old)

    def test_sampled_breach_does_not_claim_stop_fill(self):
        state = {'version': 1, 'hypotheses': {}}
        report = self.run_sample(state, midpoint=70)
        self.assertTrue(report['hypotheses'][0]['sampled_invalidation_breach'])
        self.assertEqual(report['hypotheses'][0]['entry_execution'], 'NOT_ASSUMED')
        self.assertEqual(report['hypotheses'][0]['between_sample_path'], 'UNKNOWN')

    def test_unknown_pair_never_fetched_or_admitted(self):
        report = f.collect({PAIR: receipt()}, {'version': 1, 'hypotheses': {}},
                           lambda _: self.fail('No unauthorized pair'), NOW, [])
        self.assertEqual(report['outcomes'], {})
