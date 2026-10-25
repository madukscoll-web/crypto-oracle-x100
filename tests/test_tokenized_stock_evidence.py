import unittest
from unittest.mock import Mock
from tokenized_stock_evidence import collect,lookup
TOKEN='0xb2000000000000000000004884b426556b92883d'
OTHER='0x'+'1'*40

class StockReferenceTests(unittest.TestCase):
    def rpc(self):
        r=Mock();r.snapshot.return_value={'number':'0x1'};r.calls=[]
        r.read.side_effect=['0x'+format(100000000,'064x'),'0x'+format(8,'064x')]
        return r
    def record(self,**updates):
        r=dict(contract_address=TOKEN,decimals=8,total_supply=1,multiplier=1);r.update(updates);return r
    def test_pagination_uses_exact_contract_not_symbol(self):
        fetch=Mock(side_effect=[{'tokens':[self.record(contract_address=OTHER)],'next_page_token':'next'}, {'tokens':[self.record()]}])
        record,pages=lookup(TOKEN,fetch)
        self.assertEqual(record['contract_address'],TOKEN);self.assertEqual(len(pages),2)
        self.assertIn('page_token=next',fetch.call_args.args[0])
    def test_matching_supply_remains_limited_not_unlock_coverage(self):
        r=collect(dict(network='base',token_address=TOKEN),lambda url:{'tokens':[self.record()]},self.rpc())
        self.assertEqual(r['status'],'LIMITED');self.assertFalse(r['metrics']['complete_supply_unlock_coverage'])
        self.assertFalse(r['metrics']['nav_is_executable_quote'])
    def test_conflict_is_explicit(self):
        r=collect(dict(network='base',token_address=TOKEN),lambda url:{'tokens':[self.record(total_supply=2)]},self.rpc())
        self.assertEqual(r['status'],'CONFLICTING')
    def test_missing_supply_cannot_mean_zero(self):
        row=self.record();del row['total_supply']
        r=collect(dict(network='base',token_address=TOKEN),lambda url:{'tokens':[row]},self.rpc())
        self.assertEqual(r['status'],'UNKNOWN')
    def test_large_supply_difference_of_one_base_unit_is_not_rounded_away(self):
        rpc=self.rpc();rpc.read.side_effect=['0x'+format(10**40+1,'064x'),'0x'+format(8,'064x')]
        r=collect(dict(network='base',token_address=TOKEN),lambda url:{'tokens':[self.record(total_supply='1e32')]},rpc)
        self.assertEqual(r['status'],'CONFLICTING')

    def test_repeated_cursor_is_not_complete_inventory(self):
        with self.assertRaises(ValueError):lookup(TOKEN,lambda url:{'tokens':[],'next_page_token':'repeat'})

if __name__=='__main__':unittest.main()
