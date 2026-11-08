import datetime as dt
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

import oracle_http as http


class RateRecoveryTests(unittest.TestCase):
    def setUp(self):
        http._LAST_REQUEST.clear()
        http._COOLDOWN_UNTIL.clear()
        self.addCleanup(http._LAST_REQUEST.clear)
        self.addCleanup(http._COOLDOWN_UNTIL.clear)

    def test_gecko_requests_use_conservative_shared_host_pacing(self):
        http._LAST_REQUEST['api.geckoterminal.com'] = 100
        with patch.object(http.time, 'monotonic', return_value=102), patch.object(http.time, 'sleep') as sleep, patch.object(http.urllib.request, 'urlopen', return_value=io.StringIO('{}')):
            http.get_json('https://api.geckoterminal.com/api/v2/networks/base/new_pools')
        sleep.assert_called_once_with(6.0)

    def test_exhausted_429_suppresses_other_resources_but_not_other_hosts(self):
        error = urllib.error.HTTPError('https://limited.test/a', 429, '', {}, None)
        with patch.object(http.time, 'monotonic', return_value=100), patch.object(http.urllib.request, 'urlopen', side_effect=error) as send:
            with self.assertRaises(urllib.error.HTTPError):
                http.get_json('https://limited.test/a', retries=0)
            with self.assertRaises(http.ProviderRateLimited):
                http.get_json('https://limited.test/b')
            self.assertEqual(send.call_count, 1)
        with patch.object(http.time, 'monotonic', return_value=101), patch.object(http.urllib.request, 'urlopen', return_value=io.StringIO('{}')):
            self.assertEqual(http.get_json('https://other.test/a'), {})

    def test_long_retry_after_is_not_truncated_or_retried_early(self):
        error = urllib.error.HTTPError('https://limited.test/a', 429, '', {'Retry-After': '180'}, None)
        with patch.object(http.time, 'monotonic', return_value=100), patch.object(http.time, 'sleep') as sleep, patch.object(http.urllib.request, 'urlopen', side_effect=error) as send:
            with self.assertRaises(urllib.error.HTTPError):
                http.get_json('https://limited.test/a')
            self.assertEqual(http._COOLDOWN_UNTIL['limited.test'], 280)
            send.assert_called_once()
            sleep.assert_not_called()

    def test_default_rate_limit_defers_without_spending_candidate_budget(self):
        url = 'https://api.geckoterminal.com/api/v2/networks/base/new_pools'
        error = urllib.error.HTTPError(url, 429, '', {}, None)
        with patch.object(http.time, 'monotonic', return_value=100), patch.object(http.time, 'sleep') as sleep, patch.object(http.urllib.request, 'urlopen', side_effect=error) as send:
            with self.assertRaises(urllib.error.HTTPError):
                http.get_json(url)
            with self.assertRaises(http.ProviderRateLimited):
                http.get_json('https://api.geckoterminal.com/api/v2/networks/solana/new_pools')
            self.assertEqual(http._COOLDOWN_UNTIL['api.geckoterminal.com'], 160)
            send.assert_called_once()
            sleep.assert_not_called()
        # Another provider remains usable without waiting on GeckoTerminal.
        with patch.object(http.time, 'monotonic', return_value=101), patch.object(http.time, 'sleep') as sleep, patch.object(http.urllib.request, 'urlopen', return_value=io.StringIO('{}')):
            self.assertEqual(http.get_json('https://api.dexscreener.com/latest/dex/tokens/test'), {})
            sleep.assert_not_called()

    def test_transient_service_failure_still_retries(self):
        error = urllib.error.HTTPError('https://transient.test/a', 503, '', {}, None)
        with patch.object(http.time, 'monotonic', side_effect=[100, 100, 100, 112, 112]), patch.object(http.time, 'sleep') as sleep, patch.object(http.urllib.request, 'urlopen', side_effect=[error, io.StringIO('{}')]) as send:
            self.assertEqual(http.get_json('https://transient.test/a'), {})
            self.assertEqual(send.call_count, 2)
            sleep.assert_called_once_with(12)

    def test_expired_cooldown_can_recover_with_fresh_response(self):
        http._COOLDOWN_UNTIL['limited.test'] = 100
        with patch.object(http.time, 'monotonic', return_value=101), patch.object(http.urllib.request, 'urlopen', return_value=io.StringIO(json.dumps({'data': []}))):
            self.assertEqual(http.get_json('https://limited.test/a'), {'data': []})
        self.assertNotIn('limited.test', http._COOLDOWN_UNTIL)

    def test_http_date_and_malformed_retry_after(self):
        future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=180)
        import email.utils
        self.assertGreater(http.rate_limit_delay({'Retry-After': email.utils.format_datetime(future)}), 170)
        for value in ('NaN', 'inf', '-1', 'bad'):
            self.assertEqual(http.rate_limit_delay({'Retry-After': value}), 60)


if __name__ == '__main__':
    unittest.main()

