import unittest
from unittest.mock import patch

import altcoin_reversal_production as production
import hourly_evidence
import onchain
from provider_session import Session, ProviderUnavailable


class ProductionResearchTests(unittest.TestCase):
    def test_reversal_outage_is_explicit_and_cannot_authorize(self):
        def outage(*args):
            raise OSError('Unavailable')
        session = Session(transport=outage)
        report = production.collect(session=session)
        self.assertEqual(report['status_counts'], {'UNAVAILABLE': 2})
        self.assertFalse(report['buy_authorized'])
        self.assertFalse(report['orders_allowed'])
        self.assertFalse(report['telegram_eligible'])

    def test_stage_budget_restores_and_other_provider_can_run(self):
        now = [0.]
        collector = hourly_evidence.HourlyEvidence()
        collector.session = Session(clock=lambda: now[0], sleeper=lambda _: None, transport=lambda *args: {})
        def slow():
            now[0] = 8.
            return collector.fetch('https://slow.example/')
        result = collector.stage('slow', slow, seconds=7)
        self.assertEqual(result['status'], 'NOT_CHECKED')
        self.assertEqual(collector.fetch('https://independent.example/'), {})
        self.assertEqual(collector.session.max_seconds, 1200)

    def test_holder_outage_keeps_pinned_lp_observation(self):
        class Rpc:
            url = 'https://rpc.example/'
            calls = []
            def snapshot(self): return {'number': '0x1'}
            def unchanged(self): pass
        lp = {'limitation': 'Partial pool proof'}
        with patch.object(onchain, 'verify_pair', return_value=lp), \
             patch('lp_locks.analyze', return_value={}), \
             patch.object(onchain, 'holder_concentration', side_effect=OSError):
            result = onchain.collect({'network': 'base', 'token_address': '0x'+'1'*40,
                                      'address': '0x'+'2'*40}, rpc=Rpc())
        self.assertEqual(result['raw']['results']['lp']['status'], 'LIMITED')
        self.assertEqual(result['raw']['results']['holders']['status'], 'UNKNOWN')
        self.assertEqual(result['raw']['block'], {'number': '0x1'})
