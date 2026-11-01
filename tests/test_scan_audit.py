"""Accounting populations and silent-alert policy regressions."""
import copy
import unittest
from unittest.mock import patch

import crypto_oracle_scanner as scanner
import scan_audit
from test_missing_market_data import pool
from evidence_coverage import GATES


class AuditTests(unittest.TestCase):
    def test_unknown_flow_is_rejected_by_shared_rules(self):
        value = pool()
        del value['attributes']['transactions']['h1']['sells']
        self.assertEqual(scan_audit.discovery_reason(value, 'base', 'new_pools'), 'missing_or_invalid_sells')
        self.assertIsNone(scanner.inspect(value, 'base'))

    def test_rejections_identify_first_failed_stage(self):
        value = pool()
        value['attributes']['reserve_in_usd'] = '1'
        value['attributes']['volume_usd']['h24'] = '1'
        self.assertEqual(scan_audit.discovery_reason(value, 'base', 'new_pools'), 'liquidity_missing_or_below_minimum')
        del value['attributes']['pool_created_at']
        self.assertEqual(scan_audit.discovery_reason(value, 'base', 'new_pools'), 'missing_pool_creation_time')

    def test_population_reconciles_duplicates_revisits_and_overlapping_blockers(self):
        rows = [dict(assessment=dict(decision='WAIT / VERIFY', blockers=['x', 'x', 'y']),
                     verification={gate: dict(status='UNKNOWN') for gate in GATES},
                     risk_category='WAIT / VERIFY'),
                dict(assessment=dict(decision='AVOID / HIGH CONCERN', blockers=['x']),
                     verification={'contract_security': dict(status='FAIL')},
                     risk_category='AVOID / HIGH CONCERN')]
        report = scan_audit.summarize({'qualified_unique_pool': 2, 'qualified_duplicate_pool': 1,
                                      'missing_pool_creation_time': 4},
                                     {'ineligible': 1, 'already_delivered': 1},
                                     [{'key': 'a'}, {'key': 'b'}],
                                     [{'key': 'a'}, {'key': 'revisit'}], rows)
        self.assertEqual(report['discovery_observation_count'], 7)
        self.assertEqual(report['discovery_pools_not_selected'], 1)
        self.assertEqual(report['security_rejections'], 1)
        self.assertEqual(report['assessed_blocker_counts'], {'x': 2, 'y': 1})
        self.assertEqual(sum(report['notification_outcomes'].values()), report['assessed_candidates'])
        for states in report['evidence_states'].values():
            self.assertEqual(sum(states.values()), 2)
        self.assertEqual(report['evidence_states']['contract_security'], {'UNKNOWN': 1, 'FAILED': 1})

    def test_operational_message_contains_only_aggregates(self):
        import json
        import telegram_notify
        report = dict(status='completed', completed_at='2026-11-01T00:00:00Z', observations=317,
                      candidates=55, alerts_delivered=0, warnings=[],
                      filter_audit=dict(assessed_candidates=6, notification_outcomes={'ineligible': 6}),
                      discarded_token='NEVER_DISPLAY_THIS_TOKEN')
        with patch.object(telegram_notify.pathlib.Path, 'read_text', return_value=json.dumps(report)):
            message = telegram_notify.workflow_message('success')
        self.assertIn('Assessed: 6; ineligible: 6', message)
        self.assertNotIn('NEVER_DISPLAY_THIS_TOKEN', message)
