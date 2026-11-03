"Telegram transport for the dedicated manual graphics bot."
import json
from urllib.parse import urlparse

import requests


class TelegramError(RuntimeError):
    pass


class DeliveryUncertain(TelegramError):
    pass


class NotSent(TelegramError):
    """Telegram non ha ricevuto la foto (troppe richieste o connessione mai aperta):
    riprovare non crea doppioni. retry_after: secondi da aspettare, se Telegram lo dice."""

    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


class NotSent(TelegramError):
    """Telegram non ha ricevuto la foto (troppe richieste o connessione mai aperta):
    riprovare non crea doppioni. retry_after: secondi da aspettare, se Telegram lo dice."""

    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


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

            if response.status_code == 429:
                try:
                    wait = int(response.json().get('parameters', {}).get('retry_after', 0))
                except (ValueError, AttributeError, TypeError):
                    wait = 0
                raise NotSent(f'{method}: troppe richieste', retry_after=wait)

            if response.status_code == 429:
                try:
                    wait = int(response.json().get('parameters', {}).get('retry_after', 0))
                except (ValueError, AttributeError, TypeError):
                    wait = 0
                raise NotSent(f'{method}: troppe richieste', retry_after=wait)

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
        except requests.ConnectTimeout:
            # Connessione mai aperta: la foto non è partita.
            raise NotSent(f'{method}: connessione non riuscita') from None
        except requests.ConnectTimeout:
            # Connessione mai aperta: la foto non è partita.
            raise NotSent(f'{method}: connessione non riuscita') from None
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
        """Tasto "ImageGEN" in basso nella chat (menu della chat), nessun messaggio.
        Alla chiusura reset_menu_button lo toglie. Senza tasto non c'è modo di aprire
        la Mini App: se Telegram lo rifiuta, la sessione si ferma con l'errore."""
        parsed = urlparse(str(url).strip())

        if parsed.scheme != 'https' or not parsed.netloc:
            raise TelegramError('URL Mini App non HTTPS')

        self.call('setChatMenuButton', {
            'chat_id': self.chat_id,
            'menu_button': json.dumps({'type': 'web_app', 'text': 'ImageGEN', 'web_app': {'url': str(url).strip()}}),
        })
        return None

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
