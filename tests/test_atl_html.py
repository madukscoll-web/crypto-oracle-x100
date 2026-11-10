import unittest
from html.parser import HTMLParser
from atl_evidence import format_research_html, dossier
from test_atl_evidence import build, inputs, NOW, AT


class Tags(HTMLParser):
    def __init__(self):
        super().__init__();self.tags=[];self.stack=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag);self.stack.append(tag)
        assert not attrs
    def handle_endtag(self,tag):
        assert self.stack.pop()==tag


class ATLHTMLTests(unittest.TestCase):
    def test_provider_markup_cannot_inject_tags_or_hide_warnings(self):
        d=build();d['name']='<a href="evil">Coin & Co</a>'
        d['gaps'].append('<b>Forged approval</b>')
        message=format_research_html(d);parser=Tags();parser.feed(message)
        self.assertFalse(parser.stack)
        self.assertLessEqual(set(parser.tags),{'b','i','code'})
        self.assertIn('&lt;a href=&quot;evil&quot;&gt;',message)
        self.assertIn('• &lt;b&gt;Forged approval&lt;/b&gt;',message)
        self.assertIn('NOT A VERIFIED ALL-TIME LOW • NOT A BUY SIGNAL',message)

    def test_money_preserves_provider_scale_and_small_prices(self):
        d=build();d.update(price_usd='0.0000001234',volume_24h_usd='104802398',circulating_market_cap_usd='315745924')
        message=format_research_html(d)
        for value in ('$0.0000001234','$104,802,398','$315,745,924','01 Jan 2020 00:00 UTC','08 Nov 2026 03:00 UTC'):
            self.assertIn(value,message)
        self.assertIn('bounded 365-day request, not full lifetime',message)
        self.assertLess(len(message.encode('utf-16-le'))//2,3900)

    def test_absent_chart_and_volume_stay_unknown(self):
        observation,details,_=inputs();details['market_data'].pop('total_volume')
        d=dossier(observation,details,{},observed_at=AT,now=NOW.timestamp())
        message=format_research_html(d)
        self.assertIn('24h Volume:</b> Unknown',message)
        self.assertIn('Historical Coverage:</b> Unavailable',message)
        self.assertIn('Liquidity Depth:</b> Unknown',message)
        for gap in d['gaps']:
            self.assertIn(gap,message)
