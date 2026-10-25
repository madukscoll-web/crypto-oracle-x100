"""Deployment preflight. getMe/getChat are read-only; --send-test is explicit.

Never print token, chat ID, usernames, raw Telegram error bodies or request URLs.
The test message is an operational diagnostic and cannot be mistaken for BUY.
Docs: https://core.telegram.org/bots/api
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request


def request(token, method, data):
    req = urllib.request.Request('https://api.telegram.org/bot' + token + '/' + method,
                                 data=urllib.parse.urlencode(data).encode(), method='POST')
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def validate(env, send_test=False, transport=request):
    result = dict(observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                  configured=False, bot_authenticated=False, chat_accessible=False,
                  delivery_confirmed=False, status='BLOCKED', reason='Missing Telegram bot token or destination')
    token, chat = (env.get(k, '').strip() for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'))
    if not token or not chat:
        return result
    result['configured'] = True
    try:
        bot = transport(token, 'getMe', {})
        if bot.get('ok') is not True or bot.get('result', {}).get('is_bot') is not True:
            raise ValueError('Bot not authenticated')
        result['bot_authenticated'] = True
        target = transport(token, 'getChat', {'chat_id': chat})
        if target.get('ok') is not True or not isinstance(target.get('result'), dict):
            raise ValueError('Chat unavailable')
        chat_type = target['result'].get('type')
        returned_chat_id = str(target['result'].get('id', ''))
        if not returned_chat_id or chat_type not in ('private', 'group', 'supergroup', 'channel'):
            raise ValueError('Malformed chat result')
        # @channel identifiers may resolve to a numeric ID, but numeric configured
        # destinations must match exactly. Never let a response redirect delivery.
        if not chat.startswith('@') and returned_chat_id != chat:
            raise ValueError('Destination mismatch')
        result['chat_accessible'] = True
        result.update(status='PREFLIGHT_OK', reason='Bot and destination checked; delivery not attempted')
        if send_test:
            response = transport(token, 'sendMessage', {'chat_id': chat, 'text':
                'CRYPTO-ORACLE deployment validation: notification delivery test. NO BUY SIGNAL. Automated trading remains disabled.'})
            delivered = response.get('result') or {}
            if response.get('ok') is not True or not delivered.get('message_id') or str(delivered.get('chat', {}).get('id')) != returned_chat_id:
                raise ValueError('Delivery not confirmed for configured destination')
            result.update(status='DELIVERY_CONFIRMED', delivery_confirmed=True,
                          reason='Telegram confirmed diagnostic message delivery; this is not a trade signal')
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        result.update(status='BLOCKED', reason='Telegram authentication, destination access or delivery confirmation failed')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--send-test', action='store_true')
    parser.add_argument('--output', default='telegram_validation.json')
    args = parser.parse_args()
    result = validate(os.environ, args.send_test)
    pathlib.Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if result['status'] in ('PREFLIGHT_OK', 'DELIVERY_CONFIRMED') else 1

if __name__ == '__main__':
    raise SystemExit(main())
