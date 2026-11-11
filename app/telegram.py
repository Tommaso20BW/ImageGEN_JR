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


def _jpeg(png):
    """PNG -> JPEG qualità 95 senza sottocampionamento del colore. Telegram ricomprime comunque
    ogni foto in JPEG: a parità di risultato il file da caricare pesa meno della metà."""
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.open(io.BytesIO(png)).convert('RGB').save(out, 'JPEG', quality=95, subsampling=0, optimize=True)
    return out.getvalue()


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

    def call(self, method, data=None, files=None, timeout=25, fresh=False):
        """fresh: connessione nuova, chiusa subito dopo. Per l'invio delle foto: una connessione
        rimasta aperta da tempo e chiusa da Telegram faceva restare l'invio appeso fino al timeout."""
        session = requests.Session() if fresh else self.session
        try:
            response = session.post(
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
        finally:
            if fresh:
                session.close()

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

    def photo(self, png, filename='grafica.png', caption=None):
        """Invia la foto Telegram: PNG (bytes) oppure il file_id di una foto già inviata.
        caption: testo HTML sotto la foto. Se Telegram lo rifiuta (HTTP 400: la foto non è
        partita) la foto riparte senza testo e self.caption_dropped diventa True.
        In self.last_photo restano i file_id (grande e miniatura) della foto mandata."""
        if not isinstance(png, str) and not png.startswith(b'\x89PNG\r\n\x1a\n'):
            raise TelegramError('Il renderer non ha prodotto un PNG')
        jpeg = None if isinstance(png, str) else _jpeg(png)

        def send(text):
            data = {'chat_id': self.chat_id}
            if text:
                data.update(caption=text, parse_mode='HTML')
            # Connessione: 10 s per aprirla; poi fino a 45 s per caricare la foto e avere la risposta.
            if jpeg is None:
                return self.call('sendPhoto', {**data, 'photo': png}, timeout=(10, 45), fresh=True)
            return self.call('sendPhoto', data,
                             files={'photo': (filename.rsplit('.', 1)[0] + '.jpg', jpeg, 'image/jpeg')},
                             timeout=(10, 45), fresh=True)

        self.caption_dropped = False
        try:
            result = send(caption)
        except TelegramError as exc:
            if not caption or type(exc) is not TelegramError or 'HTTP 400' not in str(exc):
                raise
            self.caption_dropped = True
            result = send(None)

        try:
            message_id = int(result['message_id'])
        except (KeyError, TypeError, ValueError):
            raise DeliveryUncertain(
                'Telegram non ha confermato il messaggio foto'
            ) from None
        sizes = [s for s in (result.get('photo') or []) if isinstance(s, dict) and s.get('file_id')]
        sizes.sort(key=lambda s: int(s.get('width') or 0))
        small = next((s for s in sizes if int(s.get('width') or 0) >= 240), sizes[0] if sizes else {})
        self.last_photo = {'file_id': sizes[-1]['file_id'] if sizes else '',
                           'thumb_id': small.get('file_id', '')}
        return message_id

    def download(self, file_id, limit=20 * 1024 * 1024):
        """Scarica un file Telegram (foto già inviata) dal suo file_id."""
        info = self.call('getFile', {'file_id': file_id})
        path = info.get('file_path') if isinstance(info, dict) else None
        if not path:
            raise TelegramError('getFile: file non disponibile')
        try:
            response = self.session.get(self.base.replace('/bot', '/file/bot', 1) + path, timeout=30)
        except requests.RequestException:
            raise TelegramError('download: connessione non disponibile') from None
        if response.status_code != 200 or len(response.content) > limit:
            raise TelegramError(f'download: HTTP {response.status_code}')
        return response.content

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
