import datetime as dt
import unittest
from token_unlocks import analyze, collect
from gas_valuation import cost, collect as gas_collect

NOW = 1800000000
def stamp(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()
class UnlockTests(unittest.TestCase):
    def disclosure(self):
        return dict(network='eth', token_address='0x'+'a'*40, source_url='https://issuer.example/vesting',
                    observed_at=stamp(NOW), circulating_supply_base_units='500', total_supply_base_units='1000',
                    schedules=[dict(id='team',kind='linear',amount_base_units='300',start=stamp(NOW),end=stamp(NOW+30*86400)),
                               dict(id='investors',kind='cliff',amount_base_units='100',start=stamp(NOW+7*86400),end=stamp(NOW+7*86400))])
    def test_cliff_linear_and_dilution(self):
        result = analyze(self.disclosure(),'eth','0x'+'a'*40,NOW)
        self.assertEqual(result['horizons_days']['30']['disclosed_unlock_base_units'],'400')
        self.assertEqual(result['horizons_days']['7']['disclosed_unlock_base_units'],'170')
        self.assertFalse(result['coverage_verified'])
        self.assertIsNone(result['undisclosed_future_dilution_upper_bound'])
    def test_missing_calendar_is_not_zero_unlocks(self):
        self.assertEqual(collect(dict(network='eth',token_address='x'),{'tokens':{}})['status'],'UNKNOWN')
    def test_wrong_identity_stale_duplicates_and_overallocation(self):
        for change in ('identity','stale','duplicate','supply','nan'):
            d=self.disclosure()
            if change=='identity': d['token_address']='other'
            elif change=='stale': d['observed_at']=stamp(NOW-86401)
            elif change=='duplicate': d['schedules'].append(dict(d['schedules'][0]))
            elif change=='supply': d['schedules'][0]['amount_base_units']='1001'
            elif change=='nan': d['schedules'][0]['amount_base_units']='NaN'
            with self.assertRaises(ValueError): analyze(d,'eth','0x'+'a'*40,NOW)

class GasTests(unittest.TestCase):
    def test_gas_excludes_principal_and_prices_total_fee(self):
        raw=dict(transaction=dict(gas='21000',gasPrice='1000000000',value='1000000000000000000'))
        self.assertEqual(cost(raw,'2000','eth')['gas_usd'],'0.042000')
        with self.assertRaises(ValueError): cost(raw,'2000','base')
        raw['totalNetworkFee']='22000000000000'
        self.assertEqual(cost(raw,'2000','base')['gas_usd'],'0.044000')
    def test_expected_fee_may_be_lower_than_gas_limit_budget(self):
        raw=dict(transaction=dict(gas='100',gasPrice='2'),totalNetworkFee='150')
        result=cost(raw,'2000','base')
        self.assertEqual(result['transaction_gas_limit_budget_wei'],'200')
        self.assertEqual(result['expected_or_fallback_network_fee_wei'],'150')
    def test_invalid_nonfinite_negative_and_fractional_costs(self):
        for price in ('nan','-1',True):
            with self.assertRaises(ValueError): cost(dict(transaction=dict(gas='1',gasPrice='1')),price,'eth')
        with self.assertRaises(ValueError): cost(dict(transaction=dict(gas='1.5',gasPrice='1')),'2000','eth')
    def test_price_identity_staleness_and_conflict(self):
        from gas_valuation import WRAPPED
        def fetch(url):
            if 'llama' in url: return {'coins':{'coingecko:ethereum':dict(price=2000,timestamp=NOW,confidence=.99)}}
            return {'data':dict(id='eth_'+WRAPPED['eth'],attributes=dict(price_usd='2001'))}
        self.assertEqual(gas_collect('eth',fetch,NOW)['status'],'LIMITED')
        self.assertEqual(gas_collect('eth',fetch,NOW+301)['status'],'UNKNOWN')
        def conflict(url):
            r=fetch(url)
            if 'llama' not in url:r['data']['attributes']['price_usd']='3000'
            return r
        self.assertEqual(gas_collect('eth',conflict,NOW)['status'],'CONFLICTING')
