import unittest
from onchain import Rpc, collect, FACTORY, ZERO, DEAD, verify_pair

TOKEN, PAIR, OTHER, OWNER = ('0x' + c * 40 for c in 'abcd')
def word(n): return '0x' + format(n, '064x')
def addr(a): return '0x' + a[2:].zfill(64)

class ChainTests(unittest.TestCase):
    def rpc(self, mutate=None):
        def transport(req):
            method, params = req['method'], req['params']
            if method == 'eth_chainId': result = '0x1'
            elif method == 'eth_getBlockByNumber': result = dict(number='0x10', hash='0x'+'e'*64, timestamp=hex(1000))
            elif method == 'eth_getCode': result = '0x1234'
            elif method == 'eth_call':
                to, data = params[0]['to'], params[0]['data']
                selector = data[2:10]
                if selector == '0dfe1681': result = addr(TOKEN)
                elif selector == 'd21220a7': result = addr(OTHER)
                elif selector == 'c45a0155': result = addr(FACTORY)
                elif selector == 'e6a43905': result = addr(PAIR)
                elif selector == '18160ddd': result = word(10000 if to == PAIR else 1000)
                elif selector == '0902f1ac': result = word(10) + word(20)[2:] + word(990)[2:]
                elif selector == '70a08231':
                    owner = '0x' + data[-40:]
                    result = word(({ZERO: 1000, DEAD: 8000} if to == PAIR else {ZERO: 0, DEAD: 100, OWNER: 200}).get(owner, 0))
                else: raise AssertionError(selector)
                self.assertEqual(params[-1], '0x10')
            else: raise AssertionError(method)
            raw = dict(id=req['id'], jsonrpc='2.0', result=result)
            return mutate(req, raw) if mutate else raw
        return Rpc('eth', transport)

    def test_canonical_pair_burn_coverage_is_not_timelock_proof(self):
        rpc = self.rpc(); rpc.snapshot(now=1001)
        result = verify_pair(rpc, PAIR, TOKEN)
        self.assertAlmostEqual(result['burned_lp_fraction'], .9)
        self.assertFalse(result['lock_coverage_complete'])
        rpc.unchanged()

    def test_wrong_chain_and_stale_head_rejected(self):
        with self.assertRaises(ValueError): self.rpc().snapshot(now=1300)
        with self.assertRaises(ValueError):
            self.rpc(lambda q, r: dict(r, result='0x38') if q['method']=='eth_chainId' else r).snapshot(now=1001)

    def test_wrong_factory_rejected(self):
        rpc = self.rpc(lambda q,r: dict(r,result=addr(OWNER)) if q['method']=='eth_call' and q['params'][0]['data']=='0xc45a0155' else r)
        rpc.snapshot(now=1001)
        with self.assertRaises(ValueError): verify_pair(rpc, PAIR, TOKEN)

    def test_reorg_rejected(self):
        rpc = self.rpc(); rpc.snapshot(now=1001)
        original = rpc.transport
        rpc.transport = lambda q: dict(original(q), result=dict(rpc.block, hash='0x'+'f'*64))
        with self.assertRaises(ValueError): rpc.unchanged()

    def test_rpc_writes_not_allowed(self):
        with self.assertRaises(ValueError): self.rpc().call('eth_sendRawTransaction', ['0x1234'])

    def test_balances_do_not_establish_beneficial_ownership(self):
        from onchain import holder_concentration
        rpc = self.rpc(); rpc.snapshot(now=1001)
        result = holder_concentration(rpc, TOKEN, [{'address': OWNER}])
        self.assertAlmostEqual(result['largest_observed_wallet_fraction'], 200/900)
        self.assertEqual(result['beneficial_cluster_upper_bound_fraction'], 1)
        self.assertFalse(result['verified_beneficial_ownership'])
