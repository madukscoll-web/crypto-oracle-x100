import unittest
from unittest.mock import patch
import gate_live_probe as probe

class ProbeTests(unittest.TestCase):
    def test_probe_cannot_authorize_buy_or_call_order_endpoints(self):
        urls=[]
        def fetch(url):
            urls.append(url)
            if url.endswith('/spot/currencies') or url.endswith('/spot/currency_pairs'):return []
            raise OSError('Unavailable')
        with patch.object(probe.supply_evidence,'collect',return_value={'status':'UNKNOWN'}):
            result=probe.run(fetch,probe.COHORT[:1])
        self.assertFalse(result['can_issue_buy'])
        self.assertFalse(result['automated_trading_enabled'])
        self.assertEqual(result['candidates'][0]['gate_spot']['status'],'UNKNOWN')
        self.assertFalse(any('/spot/orders' in u or '/spot/accounts' in u for u in urls))
    def test_catalog_outage_retains_candidate_and_checkpoint(self):
        snapshots=[]
        def fetch(_):raise OSError('Secret transport detail')
        with patch.object(probe.supply_evidence,'collect',return_value={'status':'UNKNOWN'}):
            result=probe.run(fetch,probe.COHORT[:1],lambda r:snapshots.append(len(r['candidates'])))
        self.assertEqual(snapshots,[1]);self.assertEqual(len(result['candidates']),1)
        self.assertNotIn('Secret transport detail',str(result))
