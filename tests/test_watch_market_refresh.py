import copy
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as scanner
from test_opportunity_alerts import candidate,TOKEN

class WatchRefreshTests(unittest.TestCase):
    def test_missing_fresh_volume_cannot_inherit_old_discovery_volume(self):
        item=candidate()
        payload={'data':{'attributes':{'base_token_price_usd':'0.04','reserve_in_usd':'300000','transactions':{'h1':{'buys':60,'sells':40}},'price_change_percentage':{'h1':'-2','h24':'8'}},'relationships':{'base_token':{'data':{'id':'base_'+TOKEN}}}},'included':[{'type':'token','id':'base_'+TOKEN,'attributes':{'address':TOKEN,'symbol':'FIXTURE'}}]}
        def fetch(url):
            if '?include=' in url:return copy.deepcopy(payload)
            raise OSError('fixture unavailable')
        with patch.object(scanner.time,'sleep'):
            scanner.enrich(item,fetch=fetch,delay=0)
        self.assertIsNone(item['volume']);self.assertEqual(item['liquidity'],300000)
        self.assertEqual(item['base_token_price_usd'],.04);self.assertEqual(item['trades'],100)
        self.assertEqual(item['market_raw'],payload)

if __name__=='__main__':unittest.main()
