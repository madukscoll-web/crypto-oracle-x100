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



class InvalidationDeliveryBudgetTests(unittest.TestCase):
    def state(self):
        seed = {'version': 1, 'hypotheses': {}}
        f.collect({PAIR: receipt()}, seed, fetch(NOW, 70), NOW, [PAIR])
        template = next(iter(seed['hypotheses'].values()))
        state = {'version': 1, 'hypotheses': {}}
        for offset in range(3):
            row = copy.deepcopy(template)
            row['alert']['delivered_at'] = iso(NOW-3600-offset)
            key, _ = f.identity(PAIR, row['alert'])
            state['hypotheses'][key] = row
        return state

    def test_success_and_failure_attempts_both_stop_at_two(self):
        for accepted in (True, False):
            with self.subTest(accepted=accepted):
                state = self.state()
                sent, saved = [], []
                def sender(notice):
                    sent.append(notice)
                    return accepted
                result = f.deliver_invalidations(state, sender,
                    lambda snapshot: saved.append(copy.deepcopy(snapshot)), now=NOW, allowed=[PAIR])
                self.assertEqual(len(sent), 2)
                self.assertEqual(result['attempted'], 2)
                self.assertEqual(result['delivered'], 2 if accepted else 0)
                self.assertEqual(result['failed'], 0 if accepted else 2)
                self.assertEqual(len(saved), 2 if accepted else 0)
                self.assertEqual(sum(bool(row.get('invalidation_notified_at'))
                                     for row in state['hypotheses'].values()), 2 if accepted else 0)

    def test_invalid_budget_is_rejected_before_transport(self):
        for cap in (0, 3, True):
            with self.assertRaises(ValueError):
                f.deliver_invalidations(self.state(), lambda _: self.fail('No send'),
                                        lambda _: None, now=NOW, allowed=[PAIR], max_per_run=cap)


class InvalidationIsolationTests(unittest.TestCase):
    state = InvalidationDeliveryBudgetTests.state
    def test_stale_provider_book_does_not_abort_other_hypotheses(self):
        state = self.state()
        first = next(iter(state['hypotheses'].values()))
        raw = first['samples'][-1]['raw_book']
        raw['update'] -= 60000
        first['samples'][-1]['raw_sha256'] = f.hashlib.sha256(f.canonical(raw)).hexdigest()
        sent = []
        result = f.deliver_invalidations(state, lambda notice: sent.append(notice) or True,
                                        lambda _: None, now=NOW, allowed=[PAIR])
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['delivered'], 2)
        self.assertEqual(len(sent), 2)
        self.assertNotIn('invalidation_notified_at', first)

    def test_tampered_book_is_isolated_and_never_delivered(self):
        state = self.state()
        first = next(iter(state['hypotheses'].values()))
        first['samples'][-1]['raw_sha256'] = 'invalid'
        result = f.deliver_invalidations(state, lambda _: True, lambda _: None,
                                        now=NOW, allowed=[PAIR])
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['delivered'], 2)
        self.assertNotIn('invalidation_notified_at', first)

    def test_persistence_failure_still_surfaces(self):
        def fail(_):
            raise OSError('state storage unavailable')
        with self.assertRaises(OSError):
            f.deliver_invalidations(self.state(), lambda _: True, fail,
                                    now=NOW, allowed=[PAIR])


class SnapshotRefreshTests(unittest.TestCase):
    run_sample = FollowupTests.run_sample
    def test_one_stale_book_is_refreshed_before_sampling(self):
        calls = []
        def transport(url):
            if '/currency_pairs/' in url:
                return fetch(NOW)(url)
            calls.append(url)
            return fetch(NOW-60 if len(calls)==1 else NOW)(url)
        state = {'version': 1, 'hypotheses': {}}
        report = self.run_sample(state, transport=transport)
        self.assertEqual(len(calls), 2)
        self.assertEqual(report['errors'], {})
        self.assertEqual(report['outcomes'][PAIR], 'OBSERVED')

    def test_persistently_stale_book_is_bounded_and_preserves_state(self):
        calls = []
        def transport(url):
            calls.append(url)
            return fetch(NOW-60)(url)
        state = {'version': 1, 'hypotheses': {}}
        report = self.run_sample(state, transport=transport)
        self.assertEqual(len(calls), 3)
        self.assertEqual(report['errors'][PAIR], 'ValueError')
        self.assertEqual(state['hypotheses'], {})


class MalformedHypothesisTests(unittest.TestCase):
    state = InvalidationDeliveryBudgetTests.state

    def test_malformed_row_does_not_abort_fresh_invalidations(self):
        state = self.state()
        state['hypotheses'] = {'corrupt':None, **state['hypotheses']}
        result=f.deliver_invalidations(state,lambda _:True,lambda _:None,now=NOW,allowed=[PAIR])
        self.assertEqual(result['delivered'],2)
        self.assertIn('corrupt',result['errors'])

    def test_missing_source_does_not_send_or_abort_siblings(self):
        state=self.state()
        first=next(iter(state['hypotheses'].values()))
        del first['samples'][-1]['source_url']
        result=f.deliver_invalidations(state,lambda _:True,lambda _:None,now=NOW,allowed=[PAIR])
        self.assertEqual(result['delivered'],2)
        self.assertEqual(len(result['errors']),1)
        self.assertNotIn('invalidation_notified_at',first)

    def test_corrupt_retained_row_is_reported_without_erasing_it(self):
        state={'version':1,'hypotheses':{'corrupt':None}}
        result=f.collect({},state,lambda _:None,NOW,[])
        self.assertIn('corrupt',result['errors'])
        self.assertIn('corrupt',state['hypotheses'])


class CachedInvalidationFreshnessTests(unittest.TestCase):
    def test_expired_retained_samples_are_stale_not_validation_errors(self):
        state=InvalidationDeliveryBudgetTests().state()
        result=f.deliver_invalidations(state,lambda _:self.fail('Expired sample must not send'),
                                       lambda _:self.fail('No state advancement'),now=NOW+31,allowed=[PAIR])
        self.assertEqual(result['stale'],3)
        self.assertEqual(result['errors'],{})
        self.assertEqual(result['attempted'],0)
