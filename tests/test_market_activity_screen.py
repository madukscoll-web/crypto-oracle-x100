import unittest
import market_corroboration as market


def pair(liquidity=50000,volume=100000):
    return dict(chainId='base',pairAddress='0xpool',baseToken={'address':'0xtoken'},
                priceUsd='0.1',liquidity={'usd':liquidity},volume={'h24':volume})


class MarketActivityTests(unittest.TestCase):
    def test_liquidity_floor_preserves_stricter_existing_policy_and_no_crash(self):
        for liquidity in (0,9999,10000,49999):
            result=market.market_activity_screen(pair(liquidity))
            self.assertEqual(result['status'],'BELOW_LIQUIDITY_FLOOR')
            self.assertTrue(result['warnings'])
            self.assertFalse(market.evaluate_tokenomics_and_security(pair(liquidity))[0])
        self.assertEqual(market.market_activity_screen(pair())['status'],'METRICS_ONLY_PASS')

    def test_anomaly_boundary_is_not_security_approval(self):
        self.assertEqual(market.market_activity_screen(pair(volume=2500000))['status'],'METRICS_ONLY_PASS')
        result=market.market_activity_screen(pair(volume=2500001))
        self.assertEqual(result['status'],'VOLUME_ANOMALY')
        self.assertFalse(market.evaluate_tokenomics_and_security(pair(volume=2500001))[0])
        for p in (pair(),pair(volume=2500001)):
            result=market.market_activity_screen(p)
            self.assertEqual(result['security_status'],'UNVERIFIED')
            self.assertEqual(result['executable_depth_status'],'UNKNOWN')
            self.assertFalse(result['buy_authorized']);self.assertFalse(result['orders_allowed'])

    def test_malformed_missing_boolean_and_nonfinite_values_stay_unknown(self):
        for p in (None,[],{},dict(liquidity=2),dict(liquidity={},volume=[])):
            self.assertEqual(market.market_activity_screen(p)['status'],'UNKNOWN')
        for value in (None,True,False,'bad','NaN',float('inf'),-1):
            for p in (pair(liquidity=value),pair(volume=value)):
                self.assertEqual(market.market_activity_screen(p)['status'],'UNKNOWN',p)
        self.assertEqual(market.market_activity_screen(pair('50000','0'))['volume_24h_usd'],0)

    def test_exact_pair_only_no_highest_liquidity_substitution(self):
        item=dict(network='base',address='0xpool',token_address='0xtoken',base_token_price_usd=.1)
        wrong=pair(1e10);wrong['baseToken']['address']='0xother'
        result=market.check(item,lambda _:dict(pairs=[wrong,pair(volume=2500001)]))
        self.assertEqual(result['status'],'CORROBORATED')
        self.assertEqual(result['market_activity_screen']['status'],'VOLUME_ANOMALY')
        wrong['baseToken']['address']='0xtoken';wrong['chainId']='solana'
        self.assertEqual(market.check(item,lambda _:dict(pairs=[wrong]))['status'],'CONFLICTING')

    def test_price_corroboration_does_not_promote_missing_market_evidence(self):
        item=dict(network='base',address='0xpool',token_address='0xtoken',base_token_price_usd=.1)
        p=pair();p.pop('liquidity')
        result=market.check(item,lambda _:dict(pairs=[p]))
        self.assertEqual(result['status'],'CORROBORATED')
        self.assertEqual(result['market_activity_screen']['status'],'UNKNOWN')
