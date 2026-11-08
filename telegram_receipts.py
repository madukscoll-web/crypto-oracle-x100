"""Strict Telegram Bot API receipt checks. No admission or message authority."""


def confirmed(response, destination):
    if not isinstance(response, dict) or response.get('ok') is not True:
        return False
    result = response.get('result')
    if not isinstance(result, dict):
        return False
    message_id, chat = result.get('message_id'), result.get('chat')
    if type(message_id) is not int or message_id <= 0 or not isinstance(chat, dict):
        return False
    chat_id = chat.get('id')
    if type(chat_id) is not int or chat_id == 0 or not isinstance(destination, str):
        return False
    if destination.startswith('@'):
        username = chat.get('username')
        return isinstance(username, str) and bool(username) and '@'+username.casefold() == destination.casefold()
    return str(chat_id) == destination
