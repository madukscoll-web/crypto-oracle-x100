import unittest

import gate_listings as gl


def pair(base, quote='USDT', status='tradable', kind='normal'):
    return dict(id=f'{base}_{quote}', base=base, quote=quote, trade_status=status, type=kind)


class GateListingsTests(unittest.TestCase):
    def test_only_tradable_usdt_pairs_count(self):
        pairs = [pair('SOL'), pair('ABC', quote='BTC'), pair('OLD', status='untradable'), pair('SEI'), pair('PRE', kind='premarket')]
        self.assertEqual(gl.tradable_usdt_bases(pairs), ['SEI', 'SOL'])

    def test_unreadable_input_never_reports_a_venue(self):
        for bad in (None, [], {}, 'x', [pair('A'), 'oops'], [dict(base='A')]):
            with self.assertRaises(ValueError):
                gl.tradable_usdt_bases(bad)

    def test_no_usdt_pairs_refuses_empty_venue(self):
        with self.assertRaises(ValueError):
            gl.tradable_usdt_bases([pair('A', quote='BTC')])

    def test_check_is_case_insensitive_and_defaults_to_not_listed(self):
        self.assertEqual(gl.check(['SEI'], ['sei', 'Zano']), {'SEI': 'TRADABLE', 'ZANO': 'NOT_LISTED'})

    def test_only_the_public_gate_host_is_allowed(self):
        self.assertTrue(gl.allowed(gl.URL))
        for url in ('http://api.gateio.ws/x', 'https://evil.example/api.gateio.ws', 'https://user:p@api.gateio.ws/x'):
            self.assertFalse(gl.allowed(url))
        with self.assertRaises(ValueError):
            gl.fetch('https://evil.example/x')

    def test_main_prints_summary_bases_and_checks(self):
        lines = []
        gl.main(['sei', 'zano'], fetcher=lambda: [pair('SEI'), pair('BTC')], out=lines.append)
        self.assertTrue(lines[0].startswith('GATE_LISTINGS '))
        self.assertIn('GATE_BASES BTC SEI', lines)
        self.assertIn('GATE_CHECK SEI TRADABLE', lines)
        self.assertIn('GATE_CHECK ZANO NOT_LISTED', lines)

    def test_failure_propagates_instead_of_printing_a_guess(self):
        def boom():
            raise OSError('network down')
        with self.assertRaises(OSError):
            gl.main([], fetcher=boom, out=lambda _: None)


if __name__ == '__main__':
    unittest.main()
