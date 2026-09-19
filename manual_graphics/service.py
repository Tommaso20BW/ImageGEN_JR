"""Dedicated manually-started 30-minute Telegram Mini App service."""
import copy
import os
import queue
import secrets
import signal
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .catalog import Catalog
from .render import Renderer
from .telegram import (
    DeliveryUncertain,
    Telegram,
    TelegramError,
    authorized,
)
from .webapp_payload import parse_webapp_update


class Service:
    def __init__(self, telegram, renderer, catalog, chat_id):
        self.telegram = telegram
        self.renderer = renderer
        self.catalog = catalog
        self.chat_id = str(chat_id)

        self.offset = 0
        self.state = {'status': 'idle'}
        self.session = secrets.token_urlsafe(18)

        self.worker = None
        self.results = queue.Queue()
        self.stopped = False
        self.generated_message_ids = []
        self.bot_message_ids = []
        self.launcher_message_id = None

    def _remember_bot_message(self, message_id):
        try:
            if message_id:
                self.bot_message_ids.append(int(message_id))
        except (TypeError, ValueError):
            pass

    def _prompt(self, text):
        try:
            message_id = self.telegram.prompt(text)
        except TelegramError:
            return None
        self._remember_bot_message(message_id)
        return message_id

    def receive(self):
        updates = self.telegram.poll(self.offset)

        for update in updates:
            uid = int(update['update_id'])
            self.offset = max(self.offset, uid + 1)

            if not authorized(update, self.chat_id):
                continue

            message = update.get('message') or {}
            if not message.get('web_app_data'):
                continue

            new_state, effects = parse_webapp_update(
                self.state,
                update,
                self.catalog,
                time.time(),
                expected_session=self.session,
            )
            self.state = new_state

            for effect in effects:
                self._prompt(effect['text'])

            message_id = message.get('message_id')
            if message_id:
                try:
                    self.telegram.delete(message_id)
                except TelegramError:
                    pass

    def _start_render(self):
        data = copy.deepcopy(self.state['data'])
        request_id = self.state['id']
        self.state['status'] = 'rendering'

        print(
            f"INFO IMAGEGEN: render {data['kind']} | id={request_id}",
            flush=True,
        )

        def work():
            try:
                png = self.renderer.render(data)
                self.results.put((request_id, png, None))
            except Exception as exc:
                self.results.put(
                    (request_id, None, f'{type(exc).__name__}: {exc}')
                )

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def rendering(self):
        if self.state.get('status') == 'ready' and self.worker is None:
            self._start_render()

        if self.worker is None:
            return

        try:
            request_id, png, error = self.results.get_nowait()
        except queue.Empty:
            return

        self.worker = None

        if self.state.get('id') != request_id:
            return

        if error:
            self.state['status'] = 'failed'
            print(f'ERROR IMAGEGEN: {error}', flush=True)
            self._prompt('Grafica non generata. Riapri la Mini App e riprova.')
            return

        self.state['status'] = 'sending'

        try:
            message_id = self.telegram.document(
                png,
                f"{self.state['data']['kind']}-{request_id}.png",
            )
        except DeliveryUncertain:
            self.state['status'] = 'uncertain'
            self._prompt('Invio incerto: controlla se il PNG è arrivato.')
        except TelegramError:
            self.state['status'] = 'failed'
            self._prompt('Telegram ha rifiutato il PNG. Riapri la Mini App e riprova.')
        else:
            self.state.update(
                status='completed',
                message_id=message_id,
            )
            self.generated_message_ids.append(int(message_id))
            print(
                f'INFO IMAGEGEN: PNG inviato | id={request_id}',
                flush=True,
            )

    def cleanup(self):
        for message_id in reversed(self.generated_message_ids):
            try:
                self.telegram.delete(message_id)
            except TelegramError:
                pass

        for message_id in reversed(self.bot_message_ids):
            try:
                self.telegram.delete(message_id)
            except TelegramError:
                pass

        if self.launcher_message_id:
            try:
                self.telegram.delete(self.launcher_message_id)
            except TelegramError:
                pass

        cleanup_message_id = None
        try:
            cleanup_message_id = self.telegram.remove_keyboard()
        except TelegramError:
            pass

        if cleanup_message_id:
            try:
                self.telegram.delete(cleanup_message_id)
            except TelegramError:
                pass

    def run(self, duration=1800):
        webapp_url = os.environ.get(
            'MANUAL_GRAPHICS_WEBAPP_URL',
            '',
        ).strip()
        if not webapp_url:
            raise RuntimeError('MANUAL_GRAPHICS_WEBAPP_URL mancante')

        self.offset = self.telegram.initial_offset()

        parts = urlsplit(webapp_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['session'] = self.session
        launch_url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

        self.launcher_message_id = self.telegram.webapp_launcher(launch_url)
        deadline = time.monotonic() + min(1800, max(1, duration))

        try:
            while not self.stopped and time.monotonic() < deadline:
                self.receive()
                self.rendering()
        finally:
            self.cleanup()


def main():
    token = os.environ.get('MANUAL_GRAPHICS_TELEGRAM_TOKEN', '')
    chat_id = os.environ.get('MANUAL_GRAPHICS_TELEGRAM_CHAT_ID', '')

    telegram = Telegram(token, chat_id)
    telegram.validate_private_chat()

    service = Service(
        telegram,
        Renderer(),
        Catalog(),
        chat_id,
    )

    def stop(*_):
        service.stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    service.run()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(
            f'ERROR IMAGEGEN: {type(exc).__name__}: {exc}',
            flush=True,
        )
        raise SystemExit(1)
