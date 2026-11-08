import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import deferred_candidates as queue

NOW = dt.datetime(2026, 11, 8, tzinfo=dt.timezone.utc)


def item(name):
    return {'key': 'base:'+name, 'network': 'base', 'address': name,
            'base_token_price_usd': 123, 'security_verified': True}


class DeferredCandidateTests(unittest.TestCase):
    def test_network_rotation_persists_even_without_discovery_observations(self):
        state = {'version': 1, 'pending': {}}
        networks = ('solana', 'base', 'eth', 'bsc')
        starts = []
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)/'queue.json'
            for _ in range(len(networks)):
                order = queue.network_order(state, networks)
                starts.append(order[0])
                self.assertEqual(set(order), set(networks))
                queue.save(state, path)
                state = queue.load(path)
        self.assertEqual(starts, list(networks))
        self.assertEqual(state['network_cursor'], 0)

    def test_invalid_network_cursor_is_rejected(self):
        for cursor in (-1, True, '1', None, 1.5):
            state = {'version': 1, 'pending': {}, 'network_cursor': cursor}
            with self.assertRaises(ValueError):
                queue.network_order(state, ('base',))
            with tempfile.TemporaryDirectory() as directory:
                path = pathlib.Path(directory)/'queue.json'
                queue.save(state, path)
                with self.assertRaises(ValueError):
                    queue.load(path)

    def test_local_cooldown_skip_does_not_sleep_but_real_requests_remain_paced(self):
        import crypto_oracle_scanner as scanner
        from oracle_http import ProviderRateLimited
        with patch.object(scanner.time, 'sleep') as sleep:
            scanner.pause_after_discovery(ProviderRateLimited('cooldown'))
            sleep.assert_not_called()
            scanner.pause_after_discovery()
            scanner.pause_after_discovery(OSError('remote failure'))
            self.assertEqual(sleep.call_count, 2)
            self.assertTrue(all(call.args == (scanner.REQUEST_DELAY_SECONDS,) for call in sleep.call_args_list))

    def test_persistence_retains_only_identity_not_stale_market_or_security(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)/'queue.json'
            state = queue.load(path)
            queue.prepare(state, [item('pool')], now=NOW)
            queue.save(state, path)
            restored = queue.load(path)
        self.assertEqual(set(restored['pending']['base:pool']),
                         {'network', 'pool_address', 'first_seen_at', 'last_attempt_at'})

    def test_absent_pool_requires_fresh_fetch_before_assessment(self):
        state = {'version': 1, 'pending': {}}
        queue.prepare(state, [item('pool')], now=NOW)
        requested = []
        def fetch(url):
            requested.append(url)
            return {'data': {'fixture': 'fresh'}}
        def inspect(raw, network, mode):
            self.assertEqual((raw, network, mode), ({'fixture': 'fresh'}, 'base', 'tracked'))
            return dict(item('pool'), base_token_price_usd=456)
        selected, report = queue.refresh(state, [], fetch, inspect, 'https://provider.test', now=NOW)
        self.assertEqual(requested, ['https://provider.test/networks/base/pools/pool'])
        self.assertEqual(selected[0]['base_token_price_usd'], 456)
        self.assertEqual(report['fresh_retained'], 1)

    def test_failed_refresh_rotates_without_reusing_discovery_observation(self):
        state = {'version': 1, 'pending': {}}
        queue.prepare(state, [item(str(i)) for i in range(6)], now=NOW)
        attempted = []
        def fail(url):
            attempted.append(url.rsplit('/', 1)[-1])
            raise OSError('offline')
        for hour in range(3):
            selected, report = queue.refresh(state, [], fail, None, 'https://provider.test',
                                             now=NOW+dt.timedelta(hours=hour))
            self.assertEqual(selected, [])
            self.assertEqual(report['refresh_failed'], 2)
        self.assertEqual(len(set(attempted)), 6)
        self.assertEqual(len(state['pending']), 6)

    def test_old_retained_candidates_are_not_starved_by_new_feed_arrivals(self):
        state = {'version': 1, 'pending': {}}
        old = [item('old'+str(i)) for i in range(8)]
        queue.prepare(state, old, now=NOW-dt.timedelta(hours=1))
        assessed = set()
        for hour in range(4):
            new = [item('new'+str(hour))]
            queue.prepare(state, new, now=NOW+dt.timedelta(hours=hour))
            selected, _ = queue.refresh(state, old+new, None, None, '',
                                         now=NOW+dt.timedelta(hours=hour))
            assessed.update(x['key'] for x in selected)
            queue.complete(state, selected)
        self.assertTrue({x['key'] for x in old}.issubset(assessed))

    def test_identity_mismatch_fails_closed_and_preserves_retry(self):
        state = {'version': 1, 'pending': {}}
        queue.prepare(state, [item('expected')], now=NOW)
        selected, report = queue.refresh(state, [], lambda url: {'data': {}},
                                        lambda *args: item('spoofed'), '', now=NOW)
        self.assertEqual(selected, [])
        self.assertEqual(report['refresh_failed'], 1)
        self.assertIn('base:expected', state['pending'])

    def test_loss_of_market_qualification_is_recorded(self):
        state = {'version': 1, 'pending': {}}
        queue.prepare(state, [item('old')], now=NOW)
        selected, report = queue.refresh(state, [], lambda url: {'data': {}},
                                        lambda *args: None, '', now=NOW)
        self.assertEqual(selected, [])
        self.assertEqual(report['no_longer_qualifying'], 1)
        self.assertEqual(state['pending'], {})

    def test_reservation_preserves_capacity_and_exact_token_deduplication(self):
        first = dict(item('first'), discovery_token_hint='base_0xabc')
        duplicate = dict(item('duplicate'), discovery_token_hint='BASE_0xABC')
        selected = queue.prioritize([first], [duplicate, item('other'), item('last')], 2)
        self.assertEqual([row['address'] for row in selected], ['first', 'other'])

    def test_expiry_and_capacity_losses_are_explicit(self):
        state = {'version': 1, 'pending': {}}
        queue.prepare(state, [item(str(i)) for i in range(queue.MAX_ENTRIES+2)], now=NOW)
        report = queue.prepare(state, [item('new')], now=NOW)
        self.assertEqual(report['capacity_deferred'], 1)
        self.assertEqual(len(state['pending']), queue.MAX_ENTRIES)
        report = queue.prepare(state, [], now=NOW+dt.timedelta(days=8))
        self.assertEqual(report['expired'], queue.MAX_ENTRIES)
        self.assertEqual(state['pending'], {})


if __name__ == '__main__':
    unittest.main()
