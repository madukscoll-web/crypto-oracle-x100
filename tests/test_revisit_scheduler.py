import datetime as dt
import unittest
from unittest.mock import patch

import crypto_oracle_scanner as scanner
import revisit_scheduler

NOW = dt.datetime(2026, 11, 8, 12, tzinfo=dt.timezone.utc)


def record(at=NOW, setup='WAIT'):
    return {'network': 'base', 'pool_address': 'fixture',
            'observed_at': at.isoformat(), 'setup': setup}


class RevisitSchedulerTests(unittest.TestCase):
    def test_priority_credit_is_bounded_and_ties_are_deterministic(self):
        rows = {'ordinary': record(), 'priority': record(setup='PRIORITY VERIFY'),
                'old': record(NOW-dt.timedelta(hours=2))}
        self.assertEqual([k for k, _ in revisit_scheduler.select(rows, 3, now=NOW)],
                         ['old', 'priority', 'ordinary'])

    def test_failed_attempts_rotate_without_successful_evidence(self):
        rows = {str(i): record(NOW-dt.timedelta(days=1)) for i in range(8)}
        selected = []
        for hour in range(4):
            selected.extend(k for k, _ in revisit_scheduler.select(
                rows, 2, now=NOW+dt.timedelta(hours=hour)))
        self.assertEqual(len(set(selected)), 8)
        self.assertTrue(all(r['observed_at'] == (NOW-dt.timedelta(days=1)).isoformat()
                            for r in rows.values()))

    def test_continuing_priority_retries_do_not_starve_ordinary_pool(self):
        rows = {'priority': record(setup='PRIORITY VERIFY'), 'ordinary': record()}
        selections = [revisit_scheduler.select(rows, 1, now=NOW+dt.timedelta(hours=i))[0][0]
                      for i in range(4)]
        self.assertIn('ordinary', selections)
        self.assertIn('priority', selections)

    def test_excluded_and_malformed_records_do_not_consume_slots(self):
        rows = {'selected': record(), 'bad': {}, 'none': None, 'eligible': record()}
        result = revisit_scheduler.select(rows, 1, excluded={'selected'}, now=NOW)
        self.assertEqual([k for k, _ in result], ['eligible'])
        self.assertNotIn('revisit_attempted_at', rows['selected'])

    def test_attempt_and_evidence_freshness_override_old_observation(self):
        rows = {'recent': record(NOW-dt.timedelta(days=10)),
                'old': record(NOW-dt.timedelta(hours=2))}
        rows['recent']['evidence_checked_at'] = NOW.isoformat()
        self.assertEqual(revisit_scheduler.select(rows, 1, now=NOW)[0][0], 'old')

    def test_invalid_limits_and_naive_time_rejected(self):
        for limit in (True, 0, 13, '3'):
            with self.assertRaises(ValueError):
                revisit_scheduler.select({}, limit, now=NOW)
        with self.assertRaises(ValueError):
            revisit_scheduler.select({}, 1, now=dt.datetime(2026, 11, 8))

    def test_successful_transition_retains_attempt_marker(self):
        rows = {'fixture': record()}
        revisit_scheduler.select(rows, 1, now=NOW)
        item = {'key': 'fixture', 'observed_at': NOW.isoformat(), 'score': 50,
                'network': 'base', 'address': 'fixture'}
        with patch.object(scanner, 'setup_assessment', return_value=('WAIT', 'fixture')):
            scanner.watchlist_transition(item, rows)
        self.assertEqual(rows['fixture']['revisit_attempted_at'], NOW.isoformat())


if __name__ == '__main__':
    unittest.main()
