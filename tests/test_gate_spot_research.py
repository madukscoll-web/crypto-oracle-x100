import copy
import unittest
from gate_spot_research import PublicGate,analyze_book,analyze_candles
from asset_identity import key
NOW=1800000000
TOKEN='0x'+'1'*40


def pair():
    return dict(id='SAME_USDT',base='SAME',quote='USDT',type='normal',trade_status='tradable',buy_start=0,sell_start=0,st_tag=False,precision=2,fee='0.2')


def book():return dict(current=NOW*1000,update=NOW*1000-1,asks=[['10','100'],['11','100']],bids=[['9.99','100'],['9.98','100']])


def candles():
    end=NOW//300*300-300
    return [[str(end-(20-i)*300),'100','10','11','9','10','10','true'] for i in range(21)]

class GateTests(unittest.TestCase):
    def client(self,mutate=None):
        currency=dict(currency='SAME',delisted=False,trade_disabled=False,chains=[dict(name='ETH',addr=TOKEN)])
        wallet=[dict(chain='ETH',contract_address=TOKEN,is_disabled=0,is_deposit_disabled=0,is_withdraw_disabled=0)]
        data={'/spot/currencies':[currency],'/spot/currency_pairs':[pair()],'/wallet/currency_chains':wallet,'/spot/currency_pairs/SAME_USDT':pair()}
        if mutate:mutate(data)
        def fetch(url):
            path=url.split('/api/v4')[1].split('?')[0]
            if path=='/spot/candlesticks':return candles()
            if path=='/spot/order_book':return book()
            return copy.deepcopy(data[path])
        gate=PublicGate(fetch);gate.catalog();gate.catalog_at=NOW
        return gate
    def asset(self,network='eth',token=TOKEN):return dict(network=network,token_address=token,asset_key=key(network,token),token_symbol='NOT_THE_GATE_SYMBOL')
    def test_exact_contract_not_ticker_confirms_normal_spot(self):
        self.assertEqual(self.client().eligibility(self.asset(),NOW)['status'],'CONFIRMED_SPOT')
        self.assertNotEqual(self.client().eligibility(self.asset('base'),NOW)['status'],'CONFIRMED_SPOT')
        self.assertNotEqual(self.client().eligibility(self.asset(token='0x'+'2'*40),NOW)['status'],'CONFIRMED_SPOT')
    def test_native_blank_contract_does_not_alias_wrapped_token(self):
        gate=self.client(lambda d:d['/spot/currencies'][0]['chains'][0].update(addr=''))
        self.assertEqual(gate.eligibility(self.asset(),NOW)['status'],'UNKNOWN')
    def test_wallet_and_spot_contract_disagreement_is_conflict(self):
        gate=self.client(lambda d:d['/wallet/currency_chains'][0].update(contract_address='0x'+'2'*40))
        self.assertEqual(gate.eligibility(self.asset(),NOW)['status'],'CONFLICTING')
    def test_disabled_premarket_unstarted_st_and_missing_states_block(self):
        for updates in (dict(type='premarket'),dict(trade_status='buyable'),dict(buy_start=NOW+100),dict(st_tag=True),dict(type=None),dict(sell_start=None),dict(delisting_time=NOW+100)):
            gate=self.client(lambda d:d['/spot/currency_pairs/SAME_USDT'].update(updates))
            self.assertNotEqual(gate.eligibility(self.asset(),NOW)['status'],'CONFIRMED_SPOT',updates)
        gate=self.client(lambda d:d['/spot/currencies'][0].update(trade_disabled=True))
        self.assertNotEqual(gate.eligibility(self.asset(),NOW)['status'],'CONFIRMED_SPOT')
    def test_ambiguous_duplicate_currency_and_stale_catalog_do_not_pass(self):
        def duplicate(d):
            other=copy.deepcopy(d['/spot/currencies'][0]);other['currency']='OTHER';d['/spot/currencies'].append(other)
        self.assertNotEqual(self.client(duplicate).eligibility(self.asset(),NOW)['status'],'CONFIRMED_SPOT')
        self.assertNotEqual(self.client().eligibility(self.asset(),NOW+301)['status'],'CONFIRMED_SPOT')
    def test_no_account_order_or_write_endpoint(self):
        gate=self.client()
        for path in ('/spot/orders','/spot/accounts','/wallet/deposit_address','/futures/usdt/contracts'):
            with self.assertRaises(ValueError):gate.get(path)
    def test_public_research_is_conditional_never_executable_or_fee_complete(self):
        gate=self.client();eligibility=gate.eligibility(self.asset(),NOW)
        report=gate.research(eligibility,now=NOW)
        self.assertFalse(report['orders_allowed']);self.assertFalse(report['book']['executable_quote_verified'])
        self.assertEqual(report['public_pair_fee_percent'],'0.2');self.assertIn('UNKNOWN',report['fees'])
        self.assertEqual(report['conditional_plan']['candidate_limit_price'],'9.00')
        rejected=gate.research(eligibility,excluded=True,now=NOW)
        self.assertEqual(rejected['conditional_plan']['status'],'BLOCKED');self.assertIsNone(rejected['conditional_plan']['candidate_limit_price'])
    def test_book_spread_and_size_specific_depth_are_exact_and_bounded(self):
        result=analyze_book(book(),'100',NOW)
        self.assertTrue(result['buy_depth_sufficient']);self.assertTrue(result['sell_depth_sufficient']);self.assertEqual(result['buy_vwap'],'10')
        self.assertEqual(result['quote_currency'],'USDT (not assumed USD)')
        partial=analyze_book(book(),'999999',NOW)
        self.assertFalse(partial['buy_depth_sufficient']);self.assertIsNone(partial['buy_vwap'])
    def test_stale_future_crossed_unsorted_nonfinite_and_missing_timestamp_books_rejected(self):
        for updates in (dict(current=(NOW-31)*1000),dict(update=(NOW+100)*1000),dict(bids=[['11','1']]),dict(asks=[['11','1'],['10','1']]),dict(asks=[['nan','1']]),dict(current=None)):
            raw=book();raw.update(updates)
            with self.assertRaises(ValueError):analyze_book(raw,'100',NOW)
    def test_candles_use_correct_fields_and_only_closed_fresh_contiguous_data(self):
        result=analyze_candles(candles(),NOW)
        self.assertEqual(result['support'],'9');self.assertEqual(result['resistance'],'11')
        for bad in ('open','schema','duplicate','gap','future'):
            rows=candles()
            if bad=='open':rows[-1][-1]='false'
            if bad=='schema':rows[-1]=rows[-1][:-1]
            if bad=='duplicate':rows[-1]=rows[-2]
            if bad=='gap':rows[-1][0]=str(int(rows[-1][0])-600)
            if bad=='future':rows[-1][0]=str(NOW+600)
            self.assertEqual(analyze_candles(rows,NOW)['status'],'UNKNOWN',bad)

if __name__=='__main__':unittest.main()
