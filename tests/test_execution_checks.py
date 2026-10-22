import unittest
from execution_checks import collect
A,B,T = ('0x'+c*40 for c in 'abc')

class ExecutionCheckTests(unittest.TestCase):
    def quotes(self):
        def leg(sell):return dict(raw=dict(blockNumber='100',sellToken=sell,sellAmount='10',allowanceTarget=T,
            issues=dict(allowance=None),transaction=dict(to=T,data='0x1234',value='0',gas='10',gasPrice='1')))
        return dict(status='LIMITED',raw=[leg(A),leg(B)])
    def rpc(self, balance):
        class Fake:
            url='https://rpc.example';chain=1;calls=[]
            def snapshot(self):return dict(number='0x64')
            def balance(self,*args):return balance
            def call(self,method,params):
                if method=='eth_getBalance':return '0x64'
                return '0x1234'
            def read(self,*args):return '0x'+format(100,'064x')
            def unchanged(self):pass
        return Fake()
    def test_both_current_state_calls_are_never_sequential_proof(self):
        r=collect(dict(network='eth'),self.quotes(),T,self.rpc(100))
        self.assertEqual(r['status'],'LIMITED')
        self.assertTrue(all(x['current_state_call_succeeded'] for x in r['raw']['checks']))
        self.assertFalse(r['raw']['sequential']['sequential_simulation_succeeded'])
    def test_unfunded_never_calls_transaction(self):
        r=collect(dict(network='eth'),self.quotes(),T,self.rpc(0))
        self.assertFalse(any(x['current_state_call_succeeded'] for x in r['raw']['checks']))
    def test_missing_or_stale_quotes_block(self):
        self.assertEqual(collect({}, {}, T)['status'],'UNKNOWN')
        quotes=self.quotes();quotes['raw'][0]['raw']['blockNumber']='50'
        self.assertEqual(collect(dict(network='eth'),quotes,T,self.rpc(100))['status'],'UNKNOWN')
