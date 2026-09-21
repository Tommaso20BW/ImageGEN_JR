"""Dedicated manually-started 10-minute Telegram Mini App service.

ImageGEN receives Mini App payloads through a temporary HTTPS tunnel instead of
Telegram getUpdates. This lets it coexist with LiveScore on the same bot token.
"""
import copy
import json
import os
import queue
import secrets
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from canva import CanvaTokenProvider
from catalog import Catalog
from render import Renderer
from telegram import DeliveryUncertain, Telegram, TelegramError
from webapp_payload import parse_webapp_envelope


SESSION_DURATION_SECONDS = 600
DIRECT_PORT = 8765


class _DirectHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _DirectHandler(BaseHTTPRequestHandler):
    server_version = 'ImageGEN/1.0'

    def log_message(self, *_):
        return

    @property
    def service(self):
        return self.server.imagegen_service

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header(
            'Access-Control-Allow-Headers',
            'Content-Type, X-ImageGEN-Session',
        )
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Cache-Control', 'no-store')

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path.rstrip('/') != '/submit':
            self._json(404, {'ok': False, 'error': 'Endpoint non valido.'})
            return

        if self.headers.get('X-ImageGEN-Session', '') != self.service.session:
            self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
            return

        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0

        if length <= 0 or length > 16384:
            self._json(413, {'ok': False, 'error': 'Richiesta non valida.'})
            return

        try:
            raw = self.rfile.read(length)
            envelope = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(400, {'ok': False, 'error': 'JSON non valido.'})
            return

        ok, error = self.service.accept_envelope(envelope)
        if not ok:
            status = 409 if error.startswith('Sto già generando') else 400
            self._json(status, {'ok': False, 'error': error})
            return

        self._json(202, {'ok': True})


class Service:
    def __init__(self, telegram, renderer, catalog, chat_id):
        self.telegram = telegram
        self.renderer = renderer
        self.catalog = catalog
        self.chat_id = str(chat_id)

        self.state = {'status': 'idle'}
        self.state_lock = threading.Lock()
        self.session = secrets.token_urlsafe(18)

        self.worker = None
        self.results = queue.Queue()
        self.stopped = False
        self.generated_message_ids = []
        self.bot_message_ids = []
        self.launcher_message_id = None

        self.http_server = None
        self.http_thread = None

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

    def accept_envelope(self, envelope):
        with self.state_lock:
            new_state, effects = parse_webapp_envelope(
                self.state,
                envelope,
                self.catalog,
                time.time(),
                expected_session=self.session,
            )

            if effects:
                text = str(effects[0].get('text') or 'Richiesta non valida.')
                if text.startswith('Mini App: '):
                    text = text[len('Mini App: '):]
                return False, text

            self.state = new_state
            return True, ''

    def _start_http_server(self):
        try:
            port = int(os.environ.get('IMAGEGEN_DIRECT_PORT', str(DIRECT_PORT)))
        except ValueError:
            port = DIRECT_PORT

        self.http_server = _DirectHTTPServer(
            ('127.0.0.1', port),
            _DirectHandler,
        )
        self.http_server.imagegen_service = self
        self.http_thread = threading.Thread(
            target=self.http_server.serve_forever,
            kwargs={'poll_interval': 0.15},
            daemon=True,
        )
        self.http_thread.start()
        print(f'INFO IMAGEGEN: endpoint locale pronto | port={port}', flush=True)

    def _stop_http_server(self):
        if self.http_server is not None:
            try:
                self.http_server.shutdown()
            except Exception:
                pass
            try:
                self.http_server.server_close()
            except Exception:
                pass
        self.http_server = None
        self.http_thread = None

    def _start_render(self):
        with self.state_lock:
            if self.state.get('status') != 'ready' or self.worker is not None:
                return
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
                    (
                        request_id,
                        None,
                        f'{type(exc).__name__}: {exc}',
                    )
                )

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def rendering(self):
        if self.worker is None:
            self._start_render()

        if self.worker is None:
            return

        try:
            request_id, png, error = self.results.get_nowait()
        except queue.Empty:
            return

        self.worker = None

        with self.state_lock:
            if self.state.get('id') != request_id:
                return

            if error:
                self.state['status'] = 'failed'
                print(f'ERROR IMAGEGEN: {error}', flush=True)
                self._prompt('Grafica non generata. Riapri ImageGEN e riprova.')
                return

            self.state['status'] = 'sending'
            kind = self.state['data']['kind']

        try:
            message_id = self.telegram.photo(
                png,
                f'{kind}-{request_id}.png',
            )
        except DeliveryUncertain:
            with self.state_lock:
                self.state['status'] = 'uncertain'
            self._prompt('Invio incerto: controlla se la foto è arrivata.')
        except TelegramError:
            with self.state_lock:
                self.state['status'] = 'failed'
            self._prompt('Telegram ha rifiutato la foto. Riapri ImageGEN e riprova.')
        else:
            with self.state_lock:
                self.state.update(status='completed', message_id=message_id)
            self.generated_message_ids.append(int(message_id))
            print(f'INFO IMAGEGEN: foto PNG inviata | id={request_id}', flush=True)

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

        try:
            self.telegram.reset_menu_button()
        except TelegramError:
            pass

    def run(self, duration=SESSION_DURATION_SECONDS):
        webapp_url = os.environ.get('MANUAL_GRAPHICS_WEBAPP_URL', '').strip()
        direct_url = os.environ.get('MANUAL_GRAPHICS_DIRECT_URL', '').strip()

        if not webapp_url:
            raise RuntimeError('MANUAL_GRAPHICS_WEBAPP_URL mancante')
        if not direct_url.startswith('https://'):
            raise RuntimeError('MANUAL_GRAPHICS_DIRECT_URL mancante o non HTTPS')

        self._start_http_server()

        parts = urlsplit(webapp_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['session'] = self.session
        query['direct'] = direct_url.rstrip('/') + '/submit'

        launch_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

        try:
            self.telegram.reset_menu_button()
        except TelegramError:
            pass

        self.launcher_message_id = self.telegram.webapp_launcher(launch_url)
        deadline = time.monotonic() + min(
            SESSION_DURATION_SECONDS,
            max(1, duration),
        )

        try:
            while not self.stopped and time.monotonic() < deadline:
                self.rendering()
                time.sleep(0.08)
        finally:
            self._stop_http_server()
            self.cleanup()


def main():
    token = os.environ.get('MANUAL_GRAPHICS_TELEGRAM_TOKEN', '')
    chat_id = os.environ.get('MANUAL_GRAPHICS_TELEGRAM_CHAT_ID', '')

    telegram = Telegram(token, chat_id)
    telegram.validate_private_chat()

    canva = CanvaTokenProvider()
    renderer = Renderer(token_provider=canva.refresh_access_token)

    service = Service(
        telegram,
        renderer,
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
        print(f'ERROR IMAGEGEN: {type(exc).__name__}: {exc}', flush=True)
        raise SystemExit(1)
