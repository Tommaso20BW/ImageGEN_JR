"Telegram transport for the dedicated manual graphics bot."
import json
from urllib.parse import urlparse

import requests

import step_summary


# Session message: bold title + italic line, both with custom emoji (offsets in UTF-16 units).
SESSION_TITLE = "🎨 ImageGEN · JR"
SESSION_LINE = "Sessione attiva per almeno 10min."
SESSION_TEXT = f"{SESSION_TITLE}\n\n⏳ {SESSION_LINE}"


def _u16(text):
    """Lunghezza in unità UTF-16, come la contano le entità di Telegram."""
    return len(text.encode('utf-16-le')) // 2


# Corsivo su tutta la riga, calcolato dal testo (prima era fisso a 26 e "10min." restava fuori).
_LINE_AT = _u16(SESSION_TEXT) - _u16(SESSION_LINE)
SESSION_ENTITIES = [
    {'type': 'bold', 'offset': 0, 'length': _u16(SESSION_TITLE)},
    {'type': 'custom_emoji', 'offset': 0, 'length': 2, 'custom_emoji_id': '5431456208487716895'},
    {'type': 'custom_emoji', 'offset': _LINE_AT - 2, 'length': 1, 'custom_emoji_id': '5451732530048802485'},
    {'type': 'italic', 'offset': _LINE_AT, 'length': _u16(SESSION_LINE)},
]


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

            step_summary.record(method, data, has_image=bool(files),
                                ok=response.status_code == 200)

            if response.status_code >= 500 and method in {
                'sendPhoto',
                'sendDocument',
            }:
                raise DeliveryUncertain('Invio immagine con esito incerto')

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
            if method in {'sendPhoto', 'sendDocument'}:
                raise DeliveryUncertain(
                    'Invio immagine con esito incerto'
                ) from None

            raise TelegramError(
                f'{method}: connessione non disponibile'
            ) from None

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
        return max(
            (int(update['update_id']) + 1 for update in updates),
            default=0,
        )

    def prompt(self, text, keyboard=None, entities=None, silent=False):
        data = {
            'chat_id': self.chat_id,
            'text': text,
            'disable_web_page_preview': 'true',
        }

        if silent:
            data['disable_notification'] = 'true'

        if entities:
            data['entities'] = json.dumps(entities)

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

        # Pulsante sotto il messaggio + tasto menu della chat (niente tastiera): alla chiusura
        # basta cancellare il messaggio e rimettere il menu normale, senza inviare nulla
        # (una tastiera si toglie solo con un messaggio, che fa sempre notifica).
        url = str(url).strip()
        keyboard = {'inline_keyboard': [[{'text': 'Apri ImageGEN', 'web_app': {'url': url}}]]}
        try:
            self.call('setChatMenuButton', {
                'chat_id': self.chat_id,
                'menu_button': json.dumps({'type': 'web_app', 'text': 'ImageGEN', 'web_app': {'url': url}}),
            })
        except TelegramError:
            pass
        return self.prompt(SESSION_TEXT, keyboard, SESSION_ENTITIES)

    def delete(self, message_id):
        return self.call(
            'deleteMessage',
            {
                'chat_id': self.chat_id,
                'message_id': int(message_id),
            },
        )

    def delete_many(self, message_ids):
        """Delete up to 100 messages per call (deleteMessages skips missing ones)."""
        ids = [int(value) for value in message_ids]
        for start in range(0, len(ids), 100):
            self.call(
                'deleteMessages',
                {
                    'chat_id': self.chat_id,
                    'message_ids': json.dumps(ids[start:start + 100]),
                },
            )
        return True

    def photo(self, png, filename='grafica.png'):
        """Invia il PNG come foto Telegram, come il Live Score originale."""
        if not png.startswith(b'\x89PNG\r\n\x1a\n'):
            raise TelegramError('Il renderer non ha prodotto un PNG')

        result = self.call(
            'sendPhoto',
            {'chat_id': self.chat_id},
            files={
                'photo': (
                    filename,
                    png,
                    'image/png',
                )
            },
            timeout=60,
        )

        try:
            return int(result['message_id'])
        except (KeyError, TypeError, ValueError):
            raise DeliveryUncertain(
                'Telegram non ha confermato il messaggio foto'
            ) from None

    # Lasciato per compatibilità, ma ImageGEN non lo usa più.
    def document(self, png, filename='grafica.png'):
        if not png.startswith(b'\x89PNG\r\n\x1a\n'):
            raise TelegramError('Il renderer non ha prodotto un PNG')

        result = self.call(
            'sendDocument',
            {'chat_id': self.chat_id},
            files={
                'document': (
                    filename,
                    png,
                    'image/png',
                )
            },
            timeout=60,
        )

        try:
            return int(result['message_id'])
        except (KeyError, TypeError, ValueError):
            raise DeliveryUncertain(
                'Telegram non ha confermato il messaggio PNG'
            ) from None
