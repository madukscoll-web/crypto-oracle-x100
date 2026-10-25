import unittest
from nft_custody import inspect,collect
A,B,P,M,O=('0x'+c*40 for c in 'abcde')
def word(n):return format(n%(2**256),'064x')
def addr(v):return v[2:].zfill(64)
class NftTests(unittest.TestCase):
    def rpc(self,key=100):
        class Rpc:
            def read(self,to,selector,args=''):
                if selector=='6352211e':return '0x'+addr(O)
                if selector=='081812fc':return '0x'+word(0)
                if selector=='99fbab88':return '0x'+word(0)+word(0)+addr(A)+addr(B)+word(key)+word(-100)+word(100)+word(500)+word(0)*4
        return Rpc()
    def test_tick_spacing_position_custody_is_not_a_fee_tier_or_lock(self):
        pool=dict(token0=A,token1=B,fee_tier_pips=2000,tick_spacing=100)
        result=inspect(self.rpc(),pool,M,1,O)
        self.assertTrue(result['matches_provider_owner']);self.assertEqual(result['tick_lower'],-100)
        self.assertFalse(result['escrow_release_restrictions_verified']);self.assertFalse(result['beneficial_owner_verified'])
        with self.assertRaises(ValueError):inspect(self.rpc(2000),pool,M,1,O)
    def test_malformed_nominations_do_not_trigger_rpc_or_invent_ids(self):
        result=collect({},[None,{'NFT_list':['bad',{}]}])
        self.assertEqual(result['status'],'UNKNOWN')

class EnumerationTests(unittest.TestCase):
    def test_owner_enumeration_is_bounded_and_bound_to_exact_pool(self):
        from unittest.mock import patch
        factory='0x1f98431c8ad98523631ae4a59f267346ea31f984'
        pool=dict(token0=A,token1=B,fee_tier_pips=500,tick_spacing=None,factory=factory)
        class Rpc:
            chain=1;url='https://rpc.example';calls=[]
            def snapshot(self):return dict(number='0x10')
            def balance(self,*args):return 100
            def unchanged(self):pass
            def read(self,to,selector,args=''):
                if selector=='c45a0155':return '0x'+addr(factory)
                if selector=='2f745c59':return '0x'+word(100+int(args[-64:],16))
                return NftTests().rpc(500).read(to,selector,args)
        with patch('nft_custody.verify_v3_pool',return_value=pool):
            result=collect(dict(network='eth',address=P,token_address=A),[dict(address=O,NFT_list=[])],Rpc())
        self.assertEqual(len(result['raw']['owner_enumeration']),2)
        self.assertEqual(len(result['raw']['records']),2)
        self.assertTrue(all(x['status']=='LIMITED' for x in result['raw']['records']))
