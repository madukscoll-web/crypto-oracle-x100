"""Synthetic adversarial fixtures; no assertions of live provider verification."""
import unittest
import adverse_evidence
import canonical_outcomes
import evidence_audit
import hourly_evidence
import investment_gates
import opportunity_alerts
from test_opportunity_alerts import candidate, NOW


class AdverseEvidenceTests(unittest.TestCase):
    def test_relabelled_raw_security_failure_still_rejects_everywhere(self):
        item = candidate()
        record = item['verification']['contract_security']
        record['status'] = 'PASS'
        record['raw']['result'][item['token_address']]['is_honeypot'] = '1'
        self.assertTrue(hourly_evidence.adverse(item))
        self.assertEqual(evidence_audit.audit(item)['checks']['contract_security'], 'FAIL')
        self.assertEqual(canonical_outcomes.assess(item, now=NOW)['outcome'], 'REJECT')
        self.assertFalse(investment_gates.assess(item)['buy_eligible'])

    def test_relabelled_exact_pool_sell_failure_is_not_watch(self):
        item = candidate()
        raw = {'token': {'address': item['token_address']}, 'chain': {'id': 8453},
               'pairAddress': item['address'], 'honeypotResult': {'isHoneypot': True}}
        item['verification']['sellability'] = {
            'source': 'honeypot', 'url': 'https://api.honeypot.is/v2/IsHoneypot',
            'raw': raw, 'status': 'PASS'}
        self.assertEqual(opportunity_alerts.classify(item, now=NOW)['classification'], 'REJECT')
        raw['pairAddress'] = '0x' + '9' * 40
        self.assertNotIn('sellability', adverse_evidence.findings(item))
        raw['pairAddress'] = item['address']
        raw['chain']['id'] = 1
        self.assertNotIn('sellability', adverse_evidence.findings(item))

    def test_every_adverse_check_blocks_all_research_classifiers(self):
        for name in adverse_evidence.CHECKS:
            for status in adverse_evidence.ADVERSE:
                with self.subTest(name=name, status=status):
                    item = candidate()
                    item['verification'][name] = {'status': status, 'reason': 'Synthetic adverse fixture'}
                    self.assertTrue(hourly_evidence.adverse(item))
                    self.assertEqual(evidence_audit.audit(item)['research_status'], 'REJECT')
                    classification = opportunity_alerts.classify(item, now=NOW)
                    self.assertEqual(classification['classification'], 'REJECT')
                    self.assertIsNone(opportunity_alerts.plan(item, classification, {}, now=NOW))
                    self.assertEqual(canonical_outcomes.assess(item, now=NOW)['outcome'], 'REJECT')
                    result = investment_gates.assess(item)
                    self.assertFalse(result['buy_eligible'])
                    self.assertEqual(result['security'], 'HIGH CONCERN')

    def test_forged_pass_records_cannot_authorize_buy(self):
        item = candidate()
        item['verification'] = {name: {'status': 'PASS', 'verified': True}
                                for name in adverse_evidence.CHECKS}
        item.update(buy_eligible=True, buy_authorized=True, score=100)
        self.assertFalse(evidence_audit.audit(item)['trade_ready'])
        self.assertFalse(canonical_outcomes.assess(item, now=NOW)['buy_authorized'])

    def test_provider_outages_are_unknown_not_rejection_or_approval(self):
        for value in (None, True, float('nan'), float('inf'), -1, 'unavailable'):
            with self.subTest(value=value):
                result = evidence_audit.audit({'liquidity': value, 'volume': value})
                self.assertEqual(result['checks']['market_depth'], 'UNKNOWN')
                self.assertFalse(result['trade_ready'])
        result = evidence_audit.audit({})
        self.assertEqual(result['checks']['market_depth'], 'UNKNOWN')
        self.assertEqual(result['research_status'], 'INVESTIGATE')

    def test_known_zero_market_depth_is_failure(self):
        self.assertEqual(evidence_audit.audit({'liquidity': 0, 'volume': 0})['checks']['market_depth'], 'FAIL')

    def test_malformed_records_do_not_crash_or_hide_adverse_siblings(self):
        for malformed in (['unexpected'], 'PASS', True):
            item = candidate()
            item['verification'] = malformed
            self.assertFalse(evidence_audit.audit(item)['trade_ready'])
            self.assertFalse(opportunity_alerts.classify(item, now=NOW)['eligible_for_buy'])
            item['verification'] = {'holders': malformed, 'liquidity': {'status': 'FAILED'}}
            self.assertEqual(opportunity_alerts.classify(item, now=NOW)['classification'], 'REJECT')
            self.assertEqual(canonical_outcomes.assess(item, now=NOW)['outcome'], 'REJECT')

    def test_malformed_identity_does_not_hide_existing_adverse_evidence(self):
        item = candidate()
        item['network'] = ['base']
        item['verification']['liquidity'] = {'status': 'FAILED'}
        self.assertTrue(hourly_evidence.adverse(item))
        self.assertEqual(canonical_outcomes.assess(item, now=NOW)['outcome'], 'REJECT')

