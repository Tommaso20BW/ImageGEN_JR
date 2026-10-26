"""Dedicated manually-started 10-minute Telegram Mini App service.

ImageGEN receives Mini App payloads through a temporary HTTPS tunnel instead of
Telegram getUpdates. This lets it coexist with LiveScore on the same bot token.
"""
import copy
import hashlib
import io
import json
import os
import secrets
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from catalog import Catalog
from logo_bundle import build_team_bundle
from render import Renderer
from telegram import DeliveryUncertain, Telegram, TelegramError
from webapp_payload import parse_webapp_request
from graphics.common import overlay_preview
from graphics.starting_xi import MAX_PHOTO_BYTES, check_photo


SESSION_DURATION_SECONDS = 600
MAX_PHOTOS = 8
# Campi che spostano o cambiano solo le foto: non cambiano la sagoma dell'editor.
PHOTO_FIELDS = ('frame', 'photo_id', 'person_id', 'person_frame')
LOCK_WAIT_SECONDS = 75        # un nuovo tentativo aspetta la richiesta ancora in corso
RESEND_GUARD_SECONDS = 45     # stessa grafica reinviata entro 45 s = doppione (rete persa)
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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
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

    def _png(self, payload, content_type='image/png'):
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', content_type)
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

    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path.rstrip('/') == '/fixtures':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            self._json(200, {'ok': True, 'matches': self.service.fixtures(query.get('from', ''), query.get('to', ''))})
            return
        if parts.path.rstrip('/') == '/fixture':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            self._json(200, {'ok': True, 'fixture': self.service.fixture(query.get('opponent', ''), query.get('side', ''))})
            return
        if parts.path.rstrip('/') == '/kit':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            self._json(200, {'ok': True, 'kit': self.service.kit(query.get('event', ''), query.get('league', ''))})
            return
        if parts.path.rstrip('/') == '/overlay':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            try:
                self._png(self.service.overlay(query.get('name', ''), query.get('kit', '')))
            except (KeyError, ValueError, OSError):
                self._json(404, {'ok': False, 'error': 'Modello non trovato.'})
            return
        if parts.path.rstrip('/') == '/cutout':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            try:
                self._png(self.service.cutout_preview(query.get('id', '')))
            except ValueError as exc:
                self._json(404, {'ok': False, 'error': str(exc)})
            return
        if parts.path.rstrip('/') == '/progress':
            token = dict(parse_qsl(parts.query)).get('session', '')
            if token != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            self._json(200, {'ok': True, 'stage': self.service.progress_stage})
            return
        if parts.path.rstrip('/') != '/catalog':
            self._json(404, {'ok': False, 'error': 'Endpoint non valido.'})
            return
        token = dict(parse_qsl(parts.query)).get('session', '')
        if token != self.service.session:
            self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
            return
        body = self.service.catalog_bundle
        if not body:
            self._json(503, {'ok': False, 'error': 'Catalogo non pronto.'})
            return
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _upload(self):
        if self.headers.get('X-ImageGEN-Session', '') != self.service.session:
            self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_PHOTO_BYTES:
            self._json(413, {'ok': False, 'error': 'Foto troppo grande (max 12 MB).'})
            return
        try:
            self._json(200, {'ok': True, **self.service.store_photo(self.rfile.read(length))})
        except ValueError as exc:
            self._json(400, {'ok': False, 'error': str(exc)})

    def do_POST(self):
        path = self.path.rstrip('/')
        if path == '/upload':
            self._upload()
            return
        if path not in ('/preview', '/submit', '/close', '/ghost'):
            self._json(404, {'ok': False, 'error': 'Endpoint non valido.'})
            return

        envelope = self._read_envelope()
        if envelope is None:
            return

        try:
            if path == '/close':
                if (
                    envelope.get('action') != 'close'
                    or str(envelope.get('session', '')) != self.service.session
                ):
                    self._json(400, {'ok': False, 'error': 'Richiesta di chiusura non valida.'})
                    return

                # Conferma prima la richiesta alla Mini App; subito dopo il loop
                # principale termina e parte lo stesso cleanup usato a scadenza.
                self._json(200, {'ok': True, 'closed': True})
                self.service.request_stop()
                return

            if path == '/ghost':
                self._png(self.service.ghost(envelope))
                return

            if path == '/preview':
                # Al telefono va un JPEG leggero; a Telegram resta il PNG.
                self._png(self.service.preview_jpeg(self.service.preview(envelope)), 'image/jpeg')
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
        self.catalog_bundle = None

        self.http_server = None
        self.http_thread = None

        self.operation_lock = threading.Lock()
        self.preview_cache_lock = threading.Lock()
        self.preview_cache = None
        # Passo reale del render in corso, letto dalla Mini App tramite GET /progress.
        self.progress_stage = 'idle'
        # Foto caricate dalla Mini App (solo in memoria, per questa sessione).
        self.photos = {}
        self.overlays = {}
        self.preview_cutouts = {}
        self.preview_jpeg_cache = {}
        self.ghost_cache = {}
        self.recent_sends = {}
        self.renderer.photos = self.photos

    def store_photo(self, raw):
        width, height = check_photo(raw)
        photo_id = hashlib.sha256(raw).hexdigest()[:16]
        self.photos[photo_id] = raw
        while len(self.photos) > MAX_PHOTOS:
            self.photos.pop(next(iter(self.photos)))
        print(f'INFO IMAGEGEN: foto caricata | id={photo_id} | {width}x{height}', flush=True)
        return {'photo_id': photo_id, 'width': width, 'height': height}

    def cutout_preview(self, photo_id):
        """Persona scontornata, ridotta per l'editor (l'invio usa quella piena)."""
        from PIL import Image
        if photo_id not in self.preview_cutouts:
            with Image.open(io.BytesIO(self.renderer.cutout(photo_id))) as image:
                image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                out = io.BytesIO()
                image.save(out, 'PNG')
            self.preview_cutouts[photo_id] = out.getvalue()
            while len(self.preview_cutouts) > MAX_PHOTOS:
                self.preview_cutouts.pop(next(iter(self.preview_cutouts)))
        return self.preview_cutouts[photo_id]

    def overlay(self, name, kit):
        key = (name, kit)
        if key not in self.overlays:
            self.overlays[key] = overlay_preview(name, kit)
        return self.overlays[key]

    def _set_stage(self, stage):
        self.progress_stage = str(stage)

    def request_stop(self):
        """End the active session immediately and let run() perform normal cleanup."""
        if not self.stopped:
            print('INFO IMAGEGEN: chiusura richiesta dalla Mini App', flush=True)
        self.stopped = True

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
        self._set_stage('render')
        png = self.renderer.render(data, progress=self._set_stage)

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
        # Un nuovo tentativo aspetta quello in corso e poi riusa l'anteprima già pronta.
        if not self.operation_lock.acquire(timeout=LOCK_WAIT_SECONDS):
            raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
        try:
            request_state = self._parse_request(envelope)
            png, _ = self._render_and_cache(request_state)
            return png
        finally:
            self._set_stage('idle')
            self.operation_lock.release()

    def ghost(self, envelope):
        """Grafica senza foto, trasparente e leggera: l'editor la mostra sopra la foto."""
        data = self._parse_request(envelope)['data']
        key = self._fingerprint({k: v for k, v in data.items() if k not in PHOTO_FIELDS})
        if self.ghost_cache.get('key') != key:
            if not self.operation_lock.acquire(timeout=LOCK_WAIT_SECONDS):
                raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
            try:
                self.ghost_cache = {'key': key, 'png': self.renderer.render(data, ghost=True)}
            finally:
                self.operation_lock.release()
        return self.ghost_cache['png']

    def _remember_shirts(self, lineup):
        """Numeri nuovi o cambiati della Starting XI inviata -> repository."""
        try:
            import logo_bundle
            import shirt_numbers
            from livescore.graphics import goal as g
            updates = shirt_numbers.changes(lineup, g.load_players(), shirt_numbers.load())
            if updates and shirt_numbers.save(updates):
                logo_bundle.SHIRT_NUMBERS.update(updates)
        except Exception as exc:
            print(f'WARN IMAGEGEN: numeri di maglia non salvati: {type(exc).__name__}: {exc}', flush=True)

    def fixtures(self, start, end):
        """Partite Juventus fra due date (AAAA-MM-GG, ora italiana), dal calendario ESPN."""
        try:
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo

            import fixtures
            from graphics.common import _logo_rows, asset_dir
            rome = ZoneInfo('Europe/Rome')
            begin = datetime.fromisoformat(start).replace(tzinfo=rome) if start else None
            stop = datetime.fromisoformat(end).replace(tzinfo=rome) + timedelta(days=1) if end else None
            return fixtures.matches(_logo_rows(str(asset_dir())), begin, stop)
        except Exception as exc:
            print(f'WARN IMAGEGEN: calendario ESPN non disponibile: {type(exc).__name__}: {exc}', flush=True)
            return []

    def kit(self, event_id, league):
        """Maglia della Juventus nella partita ESPN (partite giocate), '' se non si sa."""
        try:
            import fixtures
            return fixtures.kit(event_id, league)
        except Exception as exc:
            print(f'WARN IMAGEGEN: maglia non trovata su ESPN: {type(exc).__name__}: {exc}', flush=True)
            return ''

    def fixture(self, opponent, side):
        """Stadio, data e ora della partita contro l'avversario (calendario ESPN)."""
        try:
            import fixtures
            from graphics.common import _logo_rows, asset_dir, normalize
            names = [opponent]
            for row in _logo_rows(str(asset_dir())):
                if normalize(row.get('name')) == normalize(opponent):
                    names += list(row.get('aliases') or [])
            home = {'home': True, 'away': False}.get(side)
            return fixtures.find(names, home=home)
        except Exception as exc:
            print(f'WARN IMAGEGEN: partita non trovata su ESPN: {type(exc).__name__}: {exc}', flush=True)
            return None

    def preview_jpeg(self, png):
        """Anteprima per il telefono: JPEG ~10 volte più leggero del PNG."""
        key = hashlib.sha256(png).hexdigest()
        if self.preview_jpeg_cache.get('key') != key:
            from PIL import Image
            out = io.BytesIO()
            Image.open(io.BytesIO(png)).convert('RGB').save(out, format='JPEG', quality=88, optimize=True)
            self.preview_jpeg_cache = {'key': key, 'jpeg': out.getvalue()}
        return self.preview_jpeg_cache['jpeg']

    def submit(self, envelope):
        # Un nuovo tentativo della Mini App (rete instabile) aspetta il primo invece di fallire.
        if not self.operation_lock.acquire(timeout=LOCK_WAIT_SECONDS):
            raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
        try:
            request_state = self._parse_request(envelope)
            data = copy.deepcopy(request_state['data'])
            fingerprint = self._fingerprint(data)

            # Stessa grafica appena inviata (risposta persa per strada): niente doppione.
            sent = self.recent_sends.get(fingerprint)
            if sent and time.time() - sent[1] < RESEND_GUARD_SECONDS:
                print(f"INFO IMAGEGEN: invio già fatto, non ripeto | kind={data['kind']}", flush=True)
                return sent[0]

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
            self.recent_sends[fingerprint] = (int(message_id), time.time())
            if data['kind'] == 'xi':
                threading.Thread(target=self._remember_shirts, args=(data['lineup'],), daemon=True).start()
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

    def _delete_messages(self, message_ids):
        """Delete messages in bulk; on failure retry one by one."""
        ids = []
        for message_id in message_ids:
            try:
                value = int(message_id)
            except (TypeError, ValueError):
                continue
            if value and value not in ids:
                ids.append(value)
        if not ids:
            return

        try:
            self.telegram.delete_many(ids)
            print(f'INFO IMAGEGEN: messaggi cancellati | n={len(ids)}', flush=True)
            return
        except TelegramError:
            pass

        failed = 0
        for message_id in ids:
            for attempt in range(3):
                try:
                    self.telegram.delete(message_id)
                    break
                except TelegramError:
                    if attempt < 2:
                        time.sleep(1.5)
            else:
                failed += 1
        print(
            f'INFO IMAGEGEN: messaggi cancellati | n={len(ids) - failed} | falliti={failed}',
            flush=True,
        )

    def cleanup(self):
        # Se un render/invio è ancora in corso, lo si lascia finire: così anche
        # la foto appena inviata finisce nell'elenco e viene cancellata.
        locked = self.operation_lock.acquire(timeout=75)
        try:
            self._cleanup_messages()
        finally:
            if locked:
                self.operation_lock.release()

    def _cleanup_messages(self):
        self._delete_messages([
            *reversed(self.generated_message_ids),
            *reversed(self.bot_message_ids),
            self.launcher_message_id,
        ])

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

        # Catalogo fresco + loghi incorporati, pronto prima che la Mini App si apra.
        try:
            self.catalog_bundle = build_team_bundle()
        except Exception as exc:
            print(f'WARN IMAGEGEN: pacchetto loghi non disponibile: {type(exc).__name__}: {exc}', flush=True)

        self._start_http_server()
        # Browser per le grafiche acceso subito: la prima anteprima non aspetta l'avvio.
        threading.Thread(target=_warm_up_renderer, daemon=True).start()
        threading.Thread(target=_warm_up_cutout, daemon=True).start()

        parts = urlsplit(webapp_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['session'] = self.session
        query['direct'] = direct_url.rstrip('/') + '/submit'
        # Scadenza in ms epoch, per il timer della Mini App (stessa durata del loop qui sotto).
        session_seconds = min(SESSION_DURATION_SECONDS, max(1, duration))
        query['expires'] = str(int((time.time() + session_seconds) * 1000))

        launch_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

        try:
            self.telegram.reset_menu_button()
        except TelegramError:
            pass

        self.launcher_message_id = self.telegram.webapp_launcher(launch_url)
        deadline = time.monotonic() + session_seconds

        try:
            while not self.stopped and time.monotonic() < deadline:
                time.sleep(0.15)
        finally:
            self._stop_http_server()
            self.cleanup()


def _warm_up_renderer():
    try:
        from graphics.common import warm_up
        warm_up()
        print('INFO IMAGEGEN: browser grafiche pronto', flush=True)
    except Exception as exc:
        print(f'WARN IMAGEGEN: browser grafiche non avviato: {type(exc).__name__}: {exc}', flush=True)


def _warm_up_cutout():
    """Modello di scontorno caricato subito: la prima foto HALF/END/FULL TIME non aspetta."""
    try:
        from livescore.graphics import phase_layers
        from PIL import Image
        phase_layers.cutout(Image.new('RGB', (64, 64)))
        print('INFO IMAGEGEN: scontorno pronto', flush=True)
    except Exception as exc:
        print(f'WARN IMAGEGEN: scontorno non avviato: {type(exc).__name__}: {exc}', flush=True)


def main():
    token = os.environ.get('MANUAL_GRAPHICS_TELEGRAM_TOKEN', '')
    chat_id = os.environ.get('MANUAL_GRAPHICS_TELEGRAM_CHAT_ID', '')

    telegram = Telegram(token, chat_id)
    telegram.validate_private_chat()

    renderer = Renderer()

    service = Service(
        telegram,
        renderer,
        Catalog(),
        chat_id,
    )

    def stop(*_):
        service.request_stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    service.run()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR IMAGEGEN: {type(exc).__name__}: {exc}', flush=True)
        raise SystemExit(1)
