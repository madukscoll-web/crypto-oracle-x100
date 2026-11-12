import unittest
import adverse_evidence
import onchain

TOKEN = '0x' + 'ab' * 20
OWNER = '0x' + 'cd' * 20
WORD = lambda a: '0x' + a[2:].rjust(64, '0')
ZERO_WORD = '0x' + '0' * 64


class Stub:
    """Minimal pinned-block RPC double."""
    def __init__(self, storage=ZERO_WORD, owner=WORD(OWNER), code='0x', fail_storage=False, fail_owner=False):
        self.block = dict(number='0x10')
        self.storage, self.owner, self.code = storage, owner, code
        self.fail_storage, self.fail_owner = fail_storage, fail_owner
        self.methods = []

    def call(self, method, params):
        self.methods.append(method)
        if method == 'eth_getStorageAt':
            if self.fail_storage:
                raise ValueError('Invalid RPC response')
            return self.storage
        if method == 'eth_getCode':
            return self.code
        raise AssertionError(method)

    def read(self, contract, selector, args=''):
        self.methods.append('read:' + selector)
        if self.fail_owner:
            raise ValueError('Invalid RPC response')
        return self.owner


class OwnerControlTests(unittest.TestCase):
    def test_proxy_fails_and_is_adverse(self):
        result = onchain.owner_control(Stub(storage=WORD('0x1234')), TOKEN)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('Upgradeable proxy', result['reason'])
        self.assertTrue(adverse_evidence.findings(dict(verification=dict(owner_control=result))))

    def test_active_owner_is_unknown_not_clear(self):
        eoa = onchain.owner_control(Stub(code='0x'), TOKEN)
        self.assertEqual((eoa['status'], eoa['metrics']['owner_kind']), ('UNKNOWN', 'EOA'))
        contract = onchain.owner_control(Stub(code='0x6001'), TOKEN)
        self.assertEqual((contract['status'], contract['metrics']['owner_kind']), ('UNKNOWN', 'CONTRACT'))

    def test_renounced_is_limited_never_verified(self):
        for owner in (ZERO_WORD, WORD(onchain.DEAD)):
            result = onchain.owner_control(Stub(owner=owner), TOKEN)
            self.assertEqual(result['status'], 'LIMITED')
            self.assertIn('not ruled out', result['reason'])

    def test_unreadable_answers_are_unknown_never_renounced(self):
        self.assertEqual(onchain.owner_control(Stub(fail_owner=True), TOKEN)['status'], 'UNKNOWN')
        self.assertEqual(onchain.owner_control(Stub(owner=ZERO_WORD, fail_storage=True), TOKEN)['status'], 'UNKNOWN')

    def test_malformed_storage_and_owner_words_do_not_pass(self):
        self.assertEqual(onchain.owner_control(Stub(owner=ZERO_WORD, storage='nonsense'), TOKEN)['status'], 'UNKNOWN')
        self.assertEqual(onchain.owner_control(Stub(owner='0x12'), TOKEN)['status'], 'UNKNOWN')

    def test_invalid_token_address_raises(self):
        with self.assertRaises(ValueError):
            onchain.owner_control(Stub(), 'not-an-address')

    def test_only_read_methods_used_and_getstorageat_allowlisted(self):
        stub = Stub(owner=ZERO_WORD)
        onchain.owner_control(stub, TOKEN)
        self.assertTrue(set(stub.methods) <= {'eth_getStorageAt', 'eth_getCode', 'read:8da5cb5b'})
        rpc = onchain.Rpc('eth', transport=lambda payload: dict(id=payload['id'], result=ZERO_WORD))
        self.assertEqual(rpc.call('eth_getStorageAt', [TOKEN, '0x0', 'latest']), ZERO_WORD)
        with self.assertRaises(ValueError):
            rpc.call('eth_sendRawTransaction', ['0x00'])


if __name__ == '__main__':
    unittest.main()
