"""Telegram transport for the dedicated manual graphics bot."""
import json
from urllib.parse import urlparse

import requests


class TelegramError(RuntimeError):
    pass


class DeliveryUncertain(TelegramError):
    pass


def authorized(update, chat_id):
    message = update.get('message') or {}
    sender = message.get('from') or {}
    chat = message.get('chat') or {}
    return (
        str(sender.get('id')) == str(chat_id)
        and str(chat.get('id')) == str(chat_id)
        and chat.get('type') == 'private'
    )


class Telegram:
    def __init__(self, token, chat_id, session=None):
        if not token or not chat_id:
            raise TelegramError('Configurazione Telegram mancante')
        self.base = f'https://api.telegram.org/bot{token}/'
        self.chat_id = str(chat_id)
        self.session = session or requests.Session()

    def call(self, method, data=None, files=None, timeout=25):
        try:
            response = self.session.post(
                self.base + method,
                data=data,
                files=files,
                timeout=timeout,
            )
            if response.status_code >= 500 and method == 'sendDocument':
                raise DeliveryUncertain('Invio PNG con esito incerto')
            if response.status_code != 200:
                raise TelegramError(f'{method}: HTTP {response.status_code}')
            value = response.json()
            if not value.get('ok'):
                raise TelegramError(f'{method}: richiesta rifiutata')
            return value['result']
        except DeliveryUncertain:
            raise
        except TelegramError:
            raise
        except (requests.RequestException, ValueError, KeyError, TypeError):
            if method == 'sendDocument':
                raise DeliveryUncertain('Invio PNG con esito incerto') from None
            raise TelegramError(f'{method}: connessione non disponibile') from None

    def validate_private_chat(self):
        chat = self.call('getChat', {'chat_id': self.chat_id})
        if chat.get('type') != 'private' or str(chat.get('id')) != self.chat_id:
            raise TelegramError(
                'MANUAL_GRAPHICS_TELEGRAM_CHAT_ID deve essere una chat privata'
            )
        return int(chat['id'])

    def poll(self, offset, timeout=10):
        return self.call(
            'getUpdates',
            {
                'offset': int(offset),
                'timeout': int(timeout),
                'allowed_updates': '["message"]',
            },
            timeout=max(5, int(timeout) + 5),
        )

    def initial_offset(self):
        updates = self.poll(0, timeout=0)
        return max((int(u['update_id']) + 1 for u in updates), default=0)

    def prompt(self, text, keyboard=None):
        data = {
            'chat_id': self.chat_id,
            'text': text,
            'disable_web_page_preview': 'true',
        }
        if keyboard:
            data['reply_markup'] = json.dumps(keyboard)
        return self.call('sendMessage', data)['message_id']

    def reset_menu_button(self):
        return self.call(
            'setChatMenuButton',
            {
                'chat_id': self.chat_id,
                'menu_button': json.dumps({'type': 'default'}),
            },
        )

    def webapp_launcher(self, url):
        parsed = urlparse(str(url).strip())
        if parsed.scheme != 'https' or not parsed.netloc:
            raise TelegramError('URL Mini App non HTTPS')

        keyboard = {
            'keyboard': [[{
                'text': 'Apri ImageGEN',
                'web_app': {'url': str(url).strip()},
            }]],
            'resize_keyboard': True,
            'is_persistent': True,
            'input_field_placeholder': 'ImageGEN',
        }
        return self.prompt('ImageGEN', keyboard)

    def remove_keyboard(self):
        return self.prompt('\u2063', {'remove_keyboard': True})

    def delete(self, message_id):
        return self.call(
            'deleteMessage',
            {
                'chat_id': self.chat_id,
                'message_id': int(message_id),
            },
        )

    def document(self, png, filename='grafica.png'):
        if not png.startswith(b'\x89PNG\r\n\x1a\n'):
            raise TelegramError('Il renderer non ha prodotto un PNG')
        result = self.call(
            'sendDocument',
            {'chat_id': self.chat_id},
            files={'document': (filename, png, 'image/png')},
            timeout=60,
        )
        try:
            return int(result['message_id'])
        except (KeyError, TypeError, ValueError):
            raise DeliveryUncertain(
                'Telegram non ha confermato il messaggio PNG'
            ) from None
