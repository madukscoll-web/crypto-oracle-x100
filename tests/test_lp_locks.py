import hashlib
import unittest
from lp_locks import inspect, analyze
from onchain import ZERO, DEAD
PAIR='0x'+'a'*40;LOCK='0x'+'b'*40;BENEFICIARY='0x'+'c'*40
class FakeRpc:
    block=dict(number='0x10',timestamp=hex(1000))
    def call(self,*args):return '0x1234'
    def read(self,contract,selector):
        return {'fc0c546a':'0x'+PAIR[2:].zfill(64),'38af3eed':'0x'+BENEFICIARY[2:].zfill(64),
                'b91d4001':'0x'+format(1000+31*86400,'064x')}[selector]
    def balance(self,*args):return 80
class LockTests(unittest.TestCase):
    def descriptor(self):
        return dict(standard='openzeppelin_token_timelock',address=LOCK,
                    runtime_sha256=hashlib.sha256(bytes.fromhex('1234')).hexdigest(),
                    review_source_url='https://review.example/source')
    def test_exact_bytecode_token_expiry_balance(self):
        result=inspect(FakeRpc(),PAIR,self.descriptor())
        self.assertEqual(result['locked_lp_base_units'],'80')
        self.assertFalse(result['independent_source_review_verified'])
    def test_changed_bytecode_wrong_token_and_short_lock_rejected(self):
        d=self.descriptor();d['runtime_sha256']='0'*64
        with self.assertRaises(ValueError):inspect(FakeRpc(),PAIR,d)
        with self.assertRaises(ValueError):inspect(FakeRpc(),LOCK,self.descriptor())
        with self.assertRaises(ValueError):inspect(FakeRpc(),PAIR,self.descriptor(),horizon_seconds=32*86400)
    def test_duplicates_do_not_double_count_coverage(self):
        pair=dict(pair=PAIR,burned_lp_balances={ZERO:'10',DEAD:'0'},total_lp_base_units='100')
        d=self.descriptor();result=analyze(FakeRpc(),pair,[d,d])
        self.assertEqual(result['covered_lp_fraction'],.9)
        self.assertEqual(len(result['errors']),1)
        self.assertFalse(result['complete_lock_inventory_verified'])
