import copy
import datetime as dt
import email.utils
import unittest
from unittest.mock import patch
import news_context as news
import project_context

NOW = 1793900000


def feed(title='Avalanche announces protocol update', age=60, link='https://example.com/story?utm_source=x'):
    date = email.utils.format_datetime(dt.datetime.fromtimestamp(NOW-age, dt.timezone.utc))
    return ('<rss><channel><item><title>'+title+'</title><link>'+link+
            '</link><pubDate>'+date+'</pubDate></item></channel></rss>').encode()


def profile(name='Avalanche'):
    result = project_context.empty({'venue':'Gate Spot','pair':'AVAX_USDT'},NOW)
    result['provider_metadata'] = {'name':name}
    return result


class NewsContextTests(unittest.TestCase):
    def test_shared_fetch_budget(self):
        calls=[]
        result=news.collect(lambda url: calls.append(url) or feed(), NOW)
        for _ in range(30): news.attach(profile(), result)
        self.assertEqual(calls, list(news.FEEDS.values()))
        self.assertFalse(result['buy_authorized'])
        self.assertFalse(result['orders_allowed'])

    def test_duplicate_headlines_and_tracking_links(self):
        result=news.collect(lambda _:feed(),NOW)
        self.assertEqual(len(result['articles']),1)
        self.assertEqual(result['articles'][0]['url'],'https://example.com/story')

    def test_stale_future_and_missing_dates(self):
        for age in (news.MAX_AGE+1, -1):
            self.assertEqual(news.parse(feed(age=age),'fixture',NOW),[])
        self.assertEqual(news.parse(b'<rss><channel><item><title>x</title></item></channel></rss>','fixture',NOW),[])

    def test_outages_are_not_clean_news_checks(self):
        def fail(_): raise OSError('unavailable')
        result=news.collect(fail,NOW)
        p=profile();news.attach(p,result)
        self.assertEqual(result['status'],'UNAVAILABLE')
        self.assertIn('UNAVAILABLE',p['news_context']['status'])
        self.assertIn('not a clean news check',news.summary(p))

    def test_matches_never_authenticate_contracts_or_dimensions(self):
        p=profile();before=copy.deepcopy(p['dimensions'])
        news.attach(p,news.collect(lambda _:feed(),NOW))
        self.assertEqual(p['news_context']['status'],'POSSIBLE_NAME_MATCH')
        self.assertFalse(p['buy_authorized'])
        self.assertFalse(p['orders_allowed'])
        self.assertEqual(p['dimensions'],before)
        self.assertIn('CONTRACT_UNVERIFIED',p['news_context']['articles'][0]['match_status'])

    def test_symbols_common_names_and_substrings(self):
        for name in ('AVAX','NEAR','Render','AvalancheX',''):
            p=profile(name);news.attach(p,news.collect(lambda _:feed(),NOW))
            self.assertEqual(p['news_context']['articles'],[])

    def test_unresolved_identity(self):
        p=profile();p['status']='IDENTITY_UNRESOLVED'
        news.attach(p,news.collect(lambda _:feed(),NOW))
        self.assertEqual(p['news_context']['articles'],[])

    def test_entities_large_and_malformed_feeds(self):
        for data in (b'<!DOCTYPE rss><rss/>', b'x'*(news.MAX_BYTES+1), b'<rss>'):
            self.assertEqual(news.collect(lambda _:data,NOW)['status'],'UNAVAILABLE')

    def test_unsafe_links(self):
        for url in ('javascript:alert(1)','http://example.com','https://user:pass@example.com','https://example.com:5000'):
            self.assertIsNone(news.safe_link(url))

    def test_summary_identity_guard_and_telegram_budget(self):
        p=profile();news.attach(p,news.collect(lambda _:feed(),NOW))
        text=project_context.summary(p,expected={'pair':'AVAX_USDT'})
        self.assertIn('NEWS:',text)
        self.assertIn('not approval',text)
        self.assertLessEqual(len(text.encode('utf-16-le'))//2,1350)
        self.assertNotIn('Avalanche',project_context.summary(p,expected={'pair':'BCH_USDT'}))

    def test_canonical_admission_unchanged(self):
        import canonical_outcomes
        item={'network':'eth','token_address':'0x'+'a'*40,'project_context':profile()}
        before=canonical_outcomes.assess(item)
        news.attach(item['project_context'],news.collect(lambda _:feed(),NOW))
        self.assertEqual(canonical_outcomes.assess(item),before)

    def test_unapproved_feed_rejected_before_network(self):
        with patch.object(news.urllib.request,'urlopen') as request:
            with self.assertRaises(ValueError):news.fetch_feed('https://arbitrary.example')
            request.assert_not_called()

    def test_real_technical_message_keeps_disclosures_and_length(self):
        from test_project_context import watch_fixture, currency, payload, cache, WATCH_NOW
        import technical_watch
        report, fetch = watch_fixture()
        row = report['results'][0]
        row['pair'] = 'AVAX_USDT'
        row['project_context'] = project_context.for_gate('AVAX_USDT', currency(), lambda _:payload(), cache(), NOW)
        news.attach(row['project_context'], news.collect(lambda _:feed(), NOW))
        screened = technical_watch.screen(row, row['research'], technical_watch.PublicGate(fetch),
            [dict(currency='AVAX', delisted=False, trade_disabled=False, chains=[])], set(), lambda:WATCH_NOW)
        message = technical_watch.message(row, row['research'], screened)
        self.assertIn('NEWS:', message)
        self.assertIn('NOT APPROVED FOR PURCHASE', message)
        self.assertLessEqual(len(message.encode('utf-16-le'))//2, 3900)
