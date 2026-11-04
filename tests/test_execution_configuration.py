import json
import pathlib
import unittest

from execution_configuration import status


class ExecutionConfigurationTests(unittest.TestCase):
    def test_missing_inputs_are_named_without_becoming_execution_evidence(self):
        result = status({})
        self.assertEqual(len(result['missing_or_invalid_names']), 4)
        self.assertFalse(result['buy_authorized'])
        self.assertFalse(result['orders_allowed'])

    def test_configured_values_are_never_emitted(self):
        env = dict(ZEROX_API_KEY='private-fixture-key',
                   ORACLE_TAKER_ADDRESS='0x'+'a'*40,
                   ORACLE_FUNDING_TOKEN='0x'+'b'*40,
                   ORACLE_ORDER_BASE_UNITS='123456')
        result = status(env)
        self.assertEqual(result['status'], 'INPUTS_PRESENT_UNVERIFIED')
        self.assertEqual(result['missing_or_invalid_names'], [])
        for value in env.values():
            self.assertNotIn(value, json.dumps(result))

    def test_zero_addresses_and_invalid_sizes_are_not_ready(self):
        env = dict(ZEROX_API_KEY='fixture', ORACLE_TAKER_ADDRESS='0x'+'0'*40,
                   ORACLE_FUNDING_TOKEN='bad', ORACLE_ORDER_BASE_UNITS='0')
        result = status(env)
        self.assertEqual(len(result['missing_or_invalid_names']), 3)

    def test_production_workflow_forwards_existing_config_to_scanner(self):
        text = pathlib.Path(__file__).resolve().parents[1].joinpath('.github/workflows/main.yml').read_text()
        scanner = text.split('      - name: Run scanner\n', 1)[1].split('      - name:', 1)[0]
        for name in ('ZEROX_API_KEY', 'ORACLE_TAKER_ADDRESS', 'ORACLE_FUNDING_TOKEN', 'ORACLE_ORDER_BASE_UNITS'):
            self.assertIn(name+': ${{', scanner)
            self.assertIn('secrets.'+name, scanner)
