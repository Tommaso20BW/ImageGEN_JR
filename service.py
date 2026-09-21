"""Dedicated manually-started 10-minute Telegram Mini App service.

ImageGEN receives Mini App payloads through a temporary HTTPS tunnel instead of
Telegram getUpdates. This lets it coexist with LiveScore on the same bot token.
"""
import copy
import hashlib
import json
import os
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
from webapp_payload import parse_webapp_request


SESSION_DURATION_SECONDS = 600
DIRECT_PORT = 8765


class BusyError(RuntimeError):
    """Raised when ImageGEN is already rendering/sending something."""


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

    def _png(self, payload):
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'image/png')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_envelope(self):
        if self.headers.get('X-ImageGEN-Session', '') != self.service.session:
            self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
            return None

        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0

        if length <= 0 or length > 16384:
            self._json(413, {'ok': False, 'error': 'Richiesta non valida.'})
            return None

        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(400, {'ok': False, 'error': 'JSON non valido.'})
            return None

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        path = self.path.rstrip('/')
        if path not in ('/preview', '/submit'):
            self._json(404, {'ok': False, 'error': 'Endpoint non valido.'})
            return

        envelope = self._read_envelope()
        if envelope is None:
            return

        try:
            if path == '/preview':
                png = self.service.preview(envelope)
                self._png(png)
                return

            message_id = self.service.submit(envelope)
            self._json(200, {'ok': True, 'message_id': message_id})

        except BusyError as exc:
            self._json(409, {'ok': False, 'error': str(exc)})
        except ValueError as exc:
            self._json(400, {'ok': False, 'error': str(exc)})
        except DeliveryUncertain:
            self._json(502, {'ok': False, 'error': 'Invio incerto: controlla se la foto è arrivata.'})
        except TelegramError:
            self._json(502, {'ok': False, 'error': 'Telegram ha rifiutato la foto. Riapri ImageGEN e riprova.'})
        except Exception as exc:  # pragma: no cover - defensive fallback
            print(f'ERROR IMAGEGEN: {type(exc).__name__}: {exc}', flush=True)
            self._json(500, {'ok': False, 'error': 'Errore interno ImageGEN.'})


class Service:
    def __init__(self, telegram, renderer, catalog, chat_id):
        self.telegram = telegram
        self.renderer = renderer
        self.catalog = catalog
        self.chat_id = str(chat_id)

        self.session = secrets.token_urlsafe(18)
        self.stopped = False
        self.generated_message_ids = []
        self.bot_message_ids = []
        self.launcher_message_id = None

        self.http_server = None
        self.http_thread = None

        self.operation_lock = threading.Lock()
        self.preview_cache_lock = threading.Lock()
        self.preview_cache = None

    def _remember_bot_message(self, message_id):
        try:
            if message_id:
                self.bot_message_ids.append(int(message_id))
        except (TypeError, ValueError):
            pass

    def _fingerprint(self, data):
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _parse_request(self, envelope):
        return parse_webapp_request(
            envelope,
            self.catalog,
            time.time(),
            expected_session=self.session,
        )

    def _render_and_cache(self, request_state, *, force=False):
        data = copy.deepcopy(request_state['data'])
        fingerprint = self._fingerprint(data)

        with self.preview_cache_lock:
            cached = self.preview_cache
            if (
                not force
                and cached
                and cached.get('fingerprint') == fingerprint
                and cached.get('png')
            ):
                return cached['png'], cached.get('request_id') or request_state['id']

        print(
            f"INFO IMAGEGEN: render {data['kind']} | id={request_state['id']} | mode=preview",
            flush=True,
        )
        png = self.renderer.render(data)

        with self.preview_cache_lock:
            self.preview_cache = {
                'fingerprint': fingerprint,
                'request_id': request_state['id'],
                'data': data,
                'png': png,
                'updated': time.time(),
            }

        return png, request_state['id']

    def preview(self, envelope):
        if not self.operation_lock.acquire(blocking=False):
            raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
        try:
            request_state = self._parse_request(envelope)
            png, _ = self._render_and_cache(request_state)
            return png
        finally:
            self.operation_lock.release()

    def submit(self, envelope):
        if not self.operation_lock.acquire(blocking=False):
            raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
        try:
            request_state = self._parse_request(envelope)
            data = copy.deepcopy(request_state['data'])
            fingerprint = self._fingerprint(data)

            with self.preview_cache_lock:
                cached = self.preview_cache
                if (
                    cached
                    and cached.get('fingerprint') == fingerprint
                    and cached.get('png')
                ):
                    png = cached['png']
                else:
                    png = None

            if png is None:
                print(
                    f"INFO IMAGEGEN: render {data['kind']} | id={request_state['id']} | mode=submit",
                    flush=True,
                )
                png = self.renderer.render(data)
                with self.preview_cache_lock:
                    self.preview_cache = {
                        'fingerprint': fingerprint,
                        'request_id': request_state['id'],
                        'data': data,
                        'png': png,
                        'updated': time.time(),
                    }
            else:
                print(
                    f"INFO IMAGEGEN: submit cached preview | kind={data['kind']} | id={request_state['id']}",
                    flush=True,
                )

            message_id = self.telegram.photo(
                png,
                f"{data['kind']}-{request_state['id']}.png",
            )
            self.generated_message_ids.append(int(message_id))
            print(f"INFO IMAGEGEN: foto PNG inviata | id={request_state['id']}", flush=True)
            return int(message_id)
        finally:
            self.operation_lock.release()

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
        deadline = time.monotonic() + min(SESSION_DURATION_SECONDS, max(1, duration))

        try:
            while not self.stopped and time.monotonic() < deadline:
                time.sleep(0.15)
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
