"""Bounded public news context, never evidence for admission or a price signal.

Only fixed publisher feeds are fetched. Article links are displayed, never fetched.
Name matches are explicitly tentative: they do not authenticate a token contract.
"""
import datetime as dt
import email.utils
import html
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = {
    'CoinDesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'Cointelegraph': 'https://cointelegraph.com/rss',
}
MAX_BYTES = 1_000_000
MAX_AGE = 72 * 3600


def clean(value, limit=240):
    value = html.unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))
    value = ''.join(' ' if unicodedata.category(c).startswith('C') else c for c in value)
    return ' '.join(value.split())[:limit]


def safe_link(value):
    try:
        parts = urllib.parse.urlsplit(value)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.port not in (None, 443) or len(value) > 500):
            return None
        return urllib.parse.urlunsplit(('https', parts.netloc, parts.path, '', ''))
    except (ValueError, TypeError):
        return None


def fetch_feed(url):
    if url not in FEEDS.values():
        raise ValueError('Unapproved feed')
    request = urllib.request.Request(url, headers={'User-Agent': 'CRYPTO-ORACLE-X100/1.0',
                                                   'Accept': 'application/rss+xml, application/xml'})
    with urllib.request.urlopen(request, timeout=4) as response:
        # Refuse cross-host redirects, including login or unrelated content.
        if urllib.parse.urlsplit(response.geturl()).hostname != urllib.parse.urlsplit(url).hostname:
            raise ValueError('Feed redirected to another host')
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Feed exceeds size bound')
    return data


def parse(data, source, now):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('Invalid bounded feed')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML entities are not accepted')
    root = ET.fromstring(data)
    articles = []
    for item in root.findall('./channel/item')[:100]:
        try:
            published = email.utils.parsedate_to_datetime(item.findtext('pubDate', ''))
            if published.tzinfo is None or not 0 <= now - published.timestamp() <= MAX_AGE:
                continue
            title = clean(item.findtext('title'), 220)
            link = safe_link(item.findtext('link'))
            if not title or not link:
                continue
            articles.append(dict(title=title, url=link, publisher=source,
                                 published_at=published.astimezone(dt.timezone.utc).isoformat()))
        except (ValueError, TypeError, OverflowError):
            continue
    return articles


def collect(fetch=None, now=None):
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    result = dict(status='UNVERIFIED_NEWS_CONTEXT', articles=[], sources=[],
                  retrieved_at=dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
                  buy_authorized=False, orders_allowed=False,
                  optional_providers={'CryptoPanic': 'NOT_CONFIGURED_ACCESS_UNVERIFIED',
                                      'Messari/Blockworks': 'NOT_CONFIGURED_ACCESS_UNVERIFIED',
                                      'CoinStats': 'NOT_CONFIGURED_ACCESS_UNVERIFIED',
                                      'CoinMarketCap': 'NOT_CONFIGURED_ACCESS_UNVERIFIED'})
    seen_titles, seen_links = set(), set()
    for source, url in FEEDS.items():
        status = dict(publisher=source, feed_url=url, status='UNAVAILABLE', accepted=0)
        try:
            rows = parse((fetch or fetch_feed)(url), source, now)
            status['status'] = 'FETCHED'
            for row in rows:
                key = re.sub(r'\W+', ' ', row['title'].casefold()).strip()
                if key in seen_titles or row['url'] in seen_links:
                    continue
                seen_titles.add(key)
                seen_links.add(row['url'])
                result['articles'].append(row)
                status['accepted'] += 1
        except (OSError, ValueError, TypeError, ET.ParseError) as exc:
            status['error_type'] = type(exc).__name__
        result['sources'].append(status)
    result['articles'].sort(key=lambda row: row['published_at'], reverse=True)
    if not any(s['status'] == 'FETCHED' for s in result['sources']):
        result['status'] = 'UNAVAILABLE'
    return result


def attach(profile, feed):
    """Attach only to a provider-mapped project name; never match ticker alone."""
    if not isinstance(profile, dict):
        return
    name = clean((profile.get('provider_metadata') or {}).get('name'), 80)
    # Short/common names are ambiguous. Leave unknown rather than invent identity.
    ambiguous = {'near', 'base', 'core', 'gas', 'link', 'render', 'world', 'story', 'flow'}
    eligible = (len(name) >= 5 and name.casefold() not in ambiguous
                and profile.get('status') != 'IDENTITY_UNRESOLVED')
    pattern = re.compile(r'(?<!\w)' + re.escape(name) + r'(?!\w)', re.I) if eligible else None
    matches = [dict(row, match_status='PROJECT_NAME_MATCH_CONTRACT_UNVERIFIED')
               for row in feed.get('articles', []) if pattern and pattern.search(row['title'])][:2]
    profile['news_context'] = dict(status=('POSSIBLE_NAME_MATCH' if matches else
        'NO_MATCH_IN_FETCHED_FEEDS' if eligible and feed.get('status') != 'UNAVAILABLE' else
        'IDENTITY_OR_FEED_UNAVAILABLE'), articles=matches, retrieved_at=feed.get('retrieved_at'),
        sources=feed.get('sources', []), buy_authorized=False, orders_allowed=False,
        limitation='Name matches do not authenticate contracts. Repeated coverage is not independent confirmation. '
                   'No matches does not mean no adverse news. Price reaction and primary-source confirmation are UNKNOWN.')


def summary(profile):
    context = (profile or {}).get('news_context') or {}
    rows = context.get('articles') or []
    lines = ['NEWS: ' + context.get('status', 'NOT_CHECKED') + ' (not safety or an entry signal).']
    for row in rows[:1]:
        lines.append(clean(row['publisher'], 30) + ': ' + clean(row['title'], 120))
        lines.append(row['published_at'] + ' | ' + row['url'])
    if rows:
        lines.append('Name match only; contract/catalyst and price reaction unverified.')
    else:
        lines.append('Coverage is limited; absence of a match is not a clean news check.')
    return '\n'.join(lines)


if __name__ == '__main__':
    import json
    import pathlib
    result = collect()
    pathlib.Path('news_source_report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status','sources','optional_providers','buy_authorized','orders_allowed')}))
