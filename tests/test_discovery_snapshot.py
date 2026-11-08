"""Reuse fresh feed evidence without extra pool lookups or identity shortcuts."""
import copy
import datetime as dt
import unittest
from unittest.mock import patch

import crypto_oracle_scanner as scanner
from test_missing_market_data import pool, refresh, TOKEN, POOL


class DiscoverySnapshotTests(unittest.TestCase):
    def item(self, age=0):
        raw = refresh()
        item = scanner.inspect(raw['data'], 'base')
        at = (dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=age)).isoformat()
        scanner.discovery_snapshot(item, raw['data'], raw['included'],
            scanner.API+'/networks/base/new_pools?page=1&include=base_token,quote_token', at)
        return item

    def enrich(self, item, fetched=None):
        calls=[]
        def transport(url):
            calls.append(url)
            if '/pools/'+POOL+'?include=' in url:
                if fetched is None:
                    raise OSError('No duplicate pool lookup permitted')
                return copy.deepcopy(fetched)
            raise OSError('Optional evidence unavailable')
        with patch.object(scanner.time,'sleep'):
            scanner.enrich(item,fetch=transport,delay=0)
        return calls

    def test_fresh_included_identity_avoids_pool_get_and_preserves_time(self):
        item=self.item(age=20)
        at=item['_discovery_snapshot']['observed_at']
        calls=self.enrich(item)
        self.assertFalse(any('/pools/'+POOL+'?include=' in url for url in calls))
        self.assertEqual(item['token_address'],TOKEN)
        self.assertEqual(item['observed_at'],at)
        self.assertTrue(item['market_snapshot_reused'])
        self.assertEqual(item['market_raw']['data']['attributes']['address'],POOL)
        self.assertIn('new_pools?',item['market_source_url'])
        self.assertFalse(item['sellability_verified'])

    def test_stale_or_future_snapshot_falls_back_to_refresh(self):
        for age in (121,-10):
            with self.subTest(age=age):
                item=self.item(age=age)
                calls=self.enrich(item,refresh())
                self.assertEqual(sum('/pools/'+POOL+'?include=' in u for u in calls),1)
                self.assertFalse(item['market_snapshot_reused'])

    def test_unbound_or_ambiguous_token_objects_cannot_replace_refresh(self):
        for mutation in ('missing','address','chain','duplicate','pool','source'):
            with self.subTest(mutation=mutation):
                item=self.item()
                snap=item['_discovery_snapshot']; raw=snap['payload']
                if mutation=='missing':raw['included']=[]
                if mutation=='address':raw['included'][0]['attributes']['address']='0x'+'3'*40
                if mutation=='chain':raw['included'][0]['id']='eth_'+TOKEN
                if mutation=='duplicate':raw['included']*=2
                if mutation=='pool':raw['data']['attributes']['address']='0x'+'4'*40
                if mutation=='source':snap['source_url']='https://untrusted.example/api/v2/networks/base/new_pools'
                calls=self.enrich(item,refresh())
                self.assertEqual(sum('/pools/'+POOL+'?include=' in u for u in calls),1)
                self.assertFalse(item['market_snapshot_reused'])
                self.assertEqual(item['token_address'],TOKEN)

    def test_missing_fresh_measurements_never_inherit_discovery_values(self):
        item=self.item()
        del item['_discovery_snapshot']['payload']['data']['attributes']['volume_usd']
        self.enrich(item)
        self.assertIsNone(item['volume'])
        self.assertEqual(item['token_address'],TOKEN)
        self.assertFalse(scanner.research_alert_eligible(item))

    def test_bare_hint_does_not_authorize_cached_identity(self):
        item=self.item()
        item.pop('_discovery_snapshot')
        item['discovery_token_hint']='base_'+TOKEN
        self.enrich(item)
        self.assertEqual(item['token_address'],'UNVERIFIED')

    def test_malformed_capture_does_not_abort_discovery(self):
        item=self.item()
        raw=pool()
        raw['relationships']={'base_token':'malformed'}
        scanner.discovery_snapshot(item,raw,[],scanner.API+'/networks/base/new_pools',
            dt.datetime.now(dt.timezone.utc).isoformat())
        self.assertNotIn('_discovery_snapshot',item)
        calls=self.enrich(item,refresh())
        self.assertEqual(sum('/pools/'+POOL+'?include=' in u for u in calls),1)
