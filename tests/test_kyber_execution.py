import datetime as dt
import unittest
from kyber_execution import collect
A,B,T=('0x'+x*40 for x in 'abc')
class ExecutionTests(unittest.TestCase):
    def quotes(self):
        def leg(a,b):return dict(raw=dict(data=dict(routeSummary=dict(tokenIn=a,tokenOut=b,timestamp=str(int(dt.datetime.now(dt.timezone.utc).timestamp())),gasPrice='2'))),
            build_response=dict(data=dict(amountIn='100',amountOut='100',gas='100',transactionValue='0',routerAddress=T,data='0x12345678')),
            metrics=dict(policy_minimum_output_base_units='99'))
        return dict(status='LIMITED',raw=[leg(A,B),leg(B,A)])
    def rpc(self):
        class Rpc:
            chain=1;url='https://rpc.example';calls=[]
            def snapshot(self):return dict(number='0x10')
            def call(self,method,params):
                if method=='eth_gasPrice':return '0x2'
                if method=='eth_getBalance':return '0x12c' # 300 wei: enough for one 200-wei leg, not both
                if method=='eth_getCode':return '0x1234'
                raise AssertionError('Unexpected simulation before aggregate funding checks')
            def balance(self,*args):return 1000
            def read(self,*args):return '0x'+format(1000,'064x')
            def unchanged(self):pass
        return Rpc()
    def test_combined_gas_budget_prevents_false_funding_pass(self):
        result=collect(dict(network='eth'),self.quotes(),T,self.rpc())
        self.assertEqual(result['status'],'LIMITED')
        self.assertFalse(result['metrics']['native_gas_budget_sufficient'])
        self.assertFalse(result['raw']['sequential']['sequential_simulation_succeeded'])
    def test_reference_routes_cannot_become_execution_proof(self):
        self.assertEqual(collect({},dict(status='LIMITED',raw=[{},{}]),T)['status'],'UNKNOWN')
