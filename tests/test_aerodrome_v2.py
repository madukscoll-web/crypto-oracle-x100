import unittest
from onchain import verify_pair
PAIR='0x'+'1'*40
TOKEN='0x'+'2'*40
QUOTE='0x'+'3'*40
FACTORY='0x420dd381b31aef6683db6b902084cb0ffece40da'
IMPLEMENTATION='0x'+'4'*40
word=lambda x:'0x'+format(x,'064x')
addr=lambda x:'0x'+x[2:].zfill(64)

class RpcFixture:
    chain=8453
    block={'number':'0x1'}
    def __init__(self):self.stable=0;self.canonical=PAIR;self.clone=True;self.requests=[]
    def call(self,method,params):
        return '0x363d3d373d3d3d363d73'+IMPLEMENTATION[2:]+'5af43d82803e903d91602b57fd5bf3' if self.clone else '0x1234'
    def read(self,target,selector,args=''):
        self.requests.append((target,selector,args))
        return {'0dfe1681':addr(TOKEN),'d21220a7':addr(QUOTE),'c45a0155':addr(FACTORY),
                '22be3de1':word(self.stable),'5c60da1b':addr(IMPLEMENTATION),'79bc57d5':addr(self.canonical),
                '18160ddd':word(1000),'0902f1ac':word(10)+word(20)[2:]+word(1)[2:]}[selector]
    def balance(self,*args):return 1

class AeroTests(unittest.TestCase):
    def test_volatile_pool_uses_reviewed_bool_key_and_clone(self):
        rpc=RpcFixture();metrics=verify_pair(rpc,PAIR,TOKEN)
        self.assertEqual(metrics['protocol'],'AerodromeV2');self.assertFalse(metrics['stable_pool'])
        self.assertFalse(metrics['lock_coverage_complete'])
        self.assertTrue(any(target==FACTORY and selector=='79bc57d5' and args.endswith('0'*64) for target,selector,args in rpc.requests))
    def test_stable_pool_uses_true_key(self):
        rpc=RpcFixture();rpc.stable=1
        self.assertTrue(verify_pair(rpc,PAIR,TOKEN)['stable_pool'])
        self.assertEqual(rpc.requests[5][2][-64:],format(1,'064x'))
    def test_noncanonical_clone_rejected(self):
        rpc=RpcFixture();rpc.clone=False
        with self.assertRaisesRegex(ValueError,'clone'):verify_pair(rpc,PAIR,TOKEN)
    def test_factory_mismatch_rejected(self):
        rpc=RpcFixture();rpc.canonical=QUOTE
        with self.assertRaisesRegex(ValueError,'recognize'):verify_pair(rpc,PAIR,TOKEN)

if __name__=='__main__':unittest.main()
