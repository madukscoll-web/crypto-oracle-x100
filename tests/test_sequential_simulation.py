import unittest
from sequential_simulation import simulate,TRANSFER
A,B,TARGET,TAKER=('0x'+c*40 for c in 'abcd')
def topic(a):return '0x'+a[2:].zfill(64)
def event(token,src,dst,n):return dict(address=token,topics=[TRANSFER,topic(src),topic(dst)],data='0x'+format(n,'064x'))
class SequentialTests(unittest.TestCase):
    def quote(self,sell,buy,amount,out):
        return dict(raw=dict(sellToken=sell,buyToken=buy,sellAmount=str(amount),minBuyAmount=str(out),
                    transaction=dict(to=TARGET,data='0x1234',gas='100000',gasPrice='1',value='0')))
    def rpc(self, bad=False):
        parent=self
        class Rpc:
            block=dict(number='0x10')
            def call(self,method,params):
                parent.assertEqual(method,'eth_simulateV1')
                parent.assertTrue(params[0]['validation'])
                parent.assertNotIn('stateOverrides',str(params))
                def read(n):return dict(status='0x1',returnData='0x'+format(n,'064x'))
                return [dict(calls=[read(0),read(100),
                    dict(status='0x1',gasUsed='0x100',logs=[event(A,TAKER,TARGET,10),event(B,TARGET,TAKER,20)]),
                    read(20),read(90),
                    dict(status='0x1',gasUsed='0x100',logs=[event(B,TAKER,TARGET,20),event(A,TARGET,TAKER,0 if bad else 9)]),
                    read(0),read(99)])]
        return Rpc()
    def test_sequential_state_and_transfer_outputs(self):
        result=simulate(self.rpc(),[self.quote(A,B,10,20),self.quote(B,A,20,9)],TAKER)
        self.assertTrue(result['sequential_simulation_succeeded'])
        self.assertFalse(result['state_overrides_used'])
    def test_success_status_without_actual_sell_output_is_rejected(self):
        with self.assertRaises(ValueError):simulate(self.rpc(True),[self.quote(A,B,10,20),self.quote(B,A,20,9)],TAKER)
