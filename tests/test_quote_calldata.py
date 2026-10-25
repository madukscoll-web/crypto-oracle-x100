import unittest
from quote_calldata import decode,SELECTOR
A,B,T=('0x'+c*40 for c in 'abc')
def w(n):return format(n,'064x')
def a(v):return v[2:].zfill(64)
def encoded(permit=0):
    desc=a(A)+a(B)+w(352)+w(384)+w(416)+w(448)+a(T)+w(100)+w(99)+w(512)+w(480)
    desc+=w(0)*4+w(permit)
    execution=a(T)+a(T)+w(160)+w(192)+w(704)+w(0)+desc+w(0)
    return SELECTOR+w(32)+execution
class CalldataTests(unittest.TestCase):
    def test_decodes_actual_policy_fields_without_claiming_execution(self):
        result=decode(encoded())
        self.assertEqual(result['src_token'],A);self.assertEqual(result['recipient'],T)
        self.assertEqual(result['amount_base_units'],'100');self.assertEqual(result['minimum_return_base_units'],'99')
        self.assertEqual(result['fee_amounts_base_units'],[])
    def test_unknown_selector_invalid_offset_and_permit_fail_closed(self):
        for data in ('0x12345678'+encoded()[10:],SELECTOR+w(0),encoded(1)):
            with self.assertRaises(ValueError):decode(data)
