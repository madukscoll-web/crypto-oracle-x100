import unittest

import token_probe as tp


class TokenProbeTests(unittest.TestCase):
    def test_abi_string_decodes_dynamic_and_bytes32(self):
        dynamic = '0x' + '20'.rjust(64, '0') + '05'.rjust(64, '0') + b'GROVE'.hex().ljust(64, '0')
        self.assertEqual(tp.abi_string(dynamic), 'GROVE')
        self.assertEqual(tp.abi_string('0x' + b'ABC'.hex().ljust(64, '0')), 'ABC')
        self.assertIsNone(tp.abi_string('0x'))
        self.assertIsNone(tp.abi_string(None))

    def test_only_reviewed_hosts_are_fetched(self):
        for url in ('http://api.gopluslabs.io/x', 'https://evil.example/x', 'https://api.gopluslabs.io.evil.example/x'):
            with self.assertRaises(ValueError):
                tp.get_json(url)

    def test_invalid_address_is_refused_before_any_call(self):
        calls = []
        orig = tp.rpc_facts
        tp.rpc_facts = lambda *a: calls.append(a)
        try:
            with self.assertRaises(ValueError):
                tp.main(['0x123'], out=lambda _: None)
        finally:
            tp.rpc_facts = orig
        self.assertEqual(calls, [])

    def test_failures_become_unknown_never_clear(self):
        lines = []
        def boom(*a):
            raise OSError('down')
        orig = (tp.rpc_facts, tp.goplus, tp.dexscreener)
        tp.rpc_facts = tp.goplus = tp.dexscreener = boom
        try:
            tp.main(['0x' + '1' * 40], out=lines.append)
        finally:
            tp.rpc_facts, tp.goplus, tp.dexscreener = orig
        self.assertTrue(all('UNKNOWN' in l for l in lines[1:]))
        self.assertEqual(len(lines), 8)

    def test_goplus_no_data_is_reported_as_no_data(self):
        orig = tp.get_json
        tp.get_json = lambda url: dict(code=1, result={})
        try:
            self.assertEqual(tp.goplus(1, '0x' + '1' * 40)['status'], 'NO_DATA')
        finally:
            tp.get_json = orig


if __name__ == '__main__':
    unittest.main()
