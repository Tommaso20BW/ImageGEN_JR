"""Dedicated manually-started 10-minute Telegram Mini App service.

ImageGEN receives Mini App payloads through a temporary HTTPS tunnel instead of
Telegram getUpdates. This lets it coexist with LiveScore on the same bot token.
"""
import caption
import log
import sent_store
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
from telegram import DeliveryUncertain, NotSent, Telegram, TelegramError
from webapp_payload import parse_webapp_request
from graphics.common import overlay_preview
from graphics.starting_xi import MAX_PHOTO_BYTES, check_photo


SESSION_DURATION_SECONDS = 30 * 60
# Più tempo solo a richiesta: tocco sul cronometro nella Mini App e conferma (fino al massimo).
# Il job GitHub si ferma a 65 minuti (timeout-minutes in imagegen.yml): margine per
# avvio e pulizia, la sessione non va oltre 60 minuti in tutto.
SESSION_MAX_SECONDS = 60 * 60
MAX_PHOTOS = 24               # il collage ne usa fino a 9, più quelle dell'altra grafica
# Campi che spostano o cambiano solo le foto: non cambiano la sagoma dell'editor.
PHOTO_FIELDS = ('frame', 'photo_id', 'person_id', 'person_frame', 'trail')
GHOST_CACHE_SIZE = 12


def _ghost_webp(png):
    """PNG della sagoma -> WebP con trasparenza (molto più leggero da mandare al telefono)."""
    from PIL import Image
    with Image.open(io.BytesIO(png)) as image:
        out = io.BytesIO()
        image.convert('RGBA').save(out, 'WEBP', quality=82, method=1)
        return out.getvalue()
LOCK_WAIT_SECONDS = 75        # un nuovo tentativo aspetta la richiesta ancora in corso
RESEND_GUARD_SECONDS = 180    # stessa grafica reinviata entro 3 min = doppione (la Mini App riprova da sola)
# Classifica: può cambiare live. L'anteprima si riscarica sempre (tranne un nuovo tentativo
# subito dopo) e l'invio riscarica se l'anteprima è più vecchia di un minuto.
TABLE_PREVIEW_REUSE_SECONDS = 20
TABLE_SEND_REUSE_SECONDS = 60
DIRECT_PORT = 8765
# Il pulsante su Telegram parte solo quando il tunnel risponde davvero da internet.
TUNNEL_READY_SECONDS = 90     # poi il workflow riprova con un tunnel nuovo
SEND_TRIES = 3                # invio a Telegram: tentativi quando la foto sicuramente non è partita
HISTORY_SIZE = 20             # ultimi invii mostrati nella Mini App (anche delle sessioni passate)
TUNNEL_READY_STREAK = 2       # risposte buone di fila
TUNNEL_NOT_READY_EXIT = 75    # codice d'uscita: "tunnel non pronto, riprova"


class TunnelNotReady(RuntimeError):
    """Il tunnel non risponde da internet: il workflow ne apre uno nuovo."""


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
            'Content-Type, X-ImageGEN-Session, X-ImageGEN-Crop',
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
            log.warn('RICHIESTA', f'{self.path} respinta: sessione non valida')
            self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
            return None

        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0

        if length <= 0 or length > 16384:
            log.warn('RICHIESTA', f'{self.path} respinta: lunghezza {length}')
            self._json(413, {'ok': False, 'error': 'Richiesta non valida.'})
            return None

        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            log.warn('RICHIESTA', f'{self.path} respinta: JSON non valido')
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
        if parts.path.rstrip('/') == '/espnteams':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            self._json(200, {'ok': True, 'teams': self.service.espn_teams()})
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
                self._png(self.service.overlay(query.get('name', ''), query.get('kit', ''), query.get('hires') == '1'))
            except (KeyError, ValueError, OSError):
                self._json(404, {'ok': False, 'error': 'Modello non trovato.'})
            return
        if parts.path.rstrip('/') == '/cutout_state':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            self._json(200, {'ok': True, **self.service.cutout_state(
                query.get('id', ''), start=query.get('start', '') == '1')})
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
        if parts.path.rstrip('/') == '/clean':
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            try:
                self._png(self.service.renderer.clean_background(query.get('id', '')), 'image/jpeg')
            except ValueError as exc:
                self._json(404, {'ok': False, 'error': str(exc)})
            return
        if parts.path.rstrip('/') == '/pagebg':
            # Sfondo di pagina (maglia o competizione) per l'editor foto, ridotto.
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            try:
                self._png(self.service.page_background(query.get('kit', ''), query.get('name', '')), 'image/jpeg')
            except (KeyError, ValueError, OSError):
                self._json(404, {'ok': False, 'error': 'Sfondo non trovato.'})
            return
        if parts.path.rstrip('/') in ('/layouts', '/pxibg'):
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            if parts.path.rstrip('/') == '/layouts':
                self._json(200, {'ok': True, **self.service.layouts()})
                return
            try:
                self._png(self.service.pxi_background(query.get('kit', '')), 'image/jpeg')
            except (KeyError, ValueError, OSError):
                self._json(404, {'ok': False, 'error': 'Sfondo non trovato.'})
            return
        if parts.path.rstrip('/') == '/convocati':
            # SQUAD LIST: convocati della prima squadra letti da juventus.com (dal più recente).
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            import juventus_convocati
            try:
                items = juventus_convocati.fetch(query.get('url', ''))
                log.info('DATI', f'Convocati dal sito: {len(items)}')
                self._json(200, {'ok': True, 'items': items})
            except ValueError as exc:
                log.warn('DATI', f'Convocati non letti: {exc}')
                self._json(400, {'ok': False, 'error': str(exc)})
            return
        if parts.path.rstrip('/') == '/probabili_info':
            # Giorno e ora dell'ultimo aggiornamento di ogni sito, per i pulsanti.
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            import probabili_web
            self._json(200, {'ok': True, **probabili_web.info()})
            return
        if parts.path.rstrip('/') == '/probabili':
            # PROBABILE XI: formazione della Juventus da Gazzetta o Sky Sport.
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            import probabili_web
            try:
                lineup = probabili_web.fetch(query.get('source', ''))
                log.info('DATI', f"Probabili lette da {lineup['source']} · modulo {lineup['module']}")
                self._json(200, {'ok': True, 'lineup': lineup})
            except ValueError as exc:
                log.warn('DATI', f'Probabili non lette: {exc}')
                self._json(400, {'ok': False, 'error': str(exc)})
            return
        if parts.path.rstrip('/') == '/session':
            # Scadenza vera (può essere stata allungata): la Mini App la legge all'apertura.
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            self._json(200, {'ok': True, **self.service.session_info()})
            return
        if parts.path.rstrip('/') in ('/history', '/history/thumb', '/history/image'):
            # Ultimi invii della sessione (elenco e miniature) per la Mini App.
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            if parts.path.rstrip('/') == '/history':
                self._json(200, {'ok': True, 'items': self.service.history_list()})
                return
            try:
                if parts.path.rstrip('/') == '/history/image':
                    self._png(self.service.history_image(query.get('id', '')), 'image/jpeg')
                    return
                self._png(self.service.history_thumb(query.get('id', '')), 'image/jpeg')
            except ValueError as exc:
                self._json(404, {'ok': False, 'error': str(exc)})
            return
        if parts.path.rstrip('/') == '/photothumb':
            # Miniatura di una foto caricata (scelta della foto del post nella CITAZIONE IG).
            query = dict(parse_qsl(parts.query))
            if query.get('session', '') != self.service.session:
                self._json(403, {'ok': False, 'error': 'Sessione non valida.'})
                return
            try:
                self._png(self.service.photo_thumb(query.get('id', ''), query.get('big') == '1'), 'image/jpeg')
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
            raw = self.rfile.read(length)
            if self.headers.get('X-ImageGEN-Crop', '') == 'story':
                self._json(200, {'ok': True, **self.service.store_story_shot(raw)})
                return
            self._json(200, {'ok': True, **self.service.store_photo(raw)})
        except ValueError as exc:
            self._json(400, {'ok': False, 'error': str(exc)})

    def do_POST(self):
        path = self.path.rstrip('/')
        if path == '/upload':
            self._upload()
            return
        if path not in ('/preview', '/submit', '/close', '/ghost', '/layout', '/extend', '/settings', '/resend',
                        '/usesent', '/phrases', '/igpost', '/colors', '/playerphoto'):
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

            if path == '/extend':
                self._json(200, {'ok': True, **self.service.extend(envelope)})
                return

            if path == '/resend':
                self._json(200, {'ok': True, 'message_id': self.service.resend(envelope)})
                return

            if path == '/usesent':
                self._json(200, {'ok': True, **self.service.use_sent(envelope)})
                return

            if path == '/phrases':
                self._json(200, {'ok': True, **self.service.phrases(envelope)})
                return

            if path == '/colors':
                self._json(200, {'ok': True, **self.service.colors(envelope)})
                return

            if path == '/playerphoto':
                self._json(200, {'ok': True, **self.service.player_photo(envelope)})
                return

            if path == '/igpost':
                self._json(200, {'ok': True, **self.service.ig_post(envelope)})
                return

            if path == '/layout':
                self._json(200, {'ok': True, 'layout': self.service.save_layout(envelope)})
                return

            if path == '/settings':
                self._json(200, {'ok': True, **self.service.settings(envelope)})
                return

            if path == '/ghost':
                self._png(self.service.ghost(envelope), 'image/webp')
                return

            if path == '/preview':
                png = self.service.preview(envelope)
                # Al telefono va un JPEG leggero; a Telegram resta il PNG.
                self._png(self.service.preview_jpeg(png), 'image/jpeg')
                return

            message_id = self.service.submit(envelope)
            self._json(200, {'ok': True, 'message_id': message_id})

        except BusyError as exc:
            self._json(409, {'ok': False, 'error': str(exc)})
        except ValueError as exc:
            log.warn('RICHIESTA', f'{path} respinta: {exc}')
            self._json(400, {'ok': False, 'error': str(exc)})
        # Niente 502/503: la Mini App li prenderebbe per un problema del tunnel e rimanderebbe da sola.
        except DeliveryUncertain:
            self._json(424, {'ok': False, 'error': 'Telegram non ha risposto: controlla nella chat se la foto è arrivata. '
                                                   'Se manca, rimandala da “Ultimi invii”.'})
        except NotSent:
            self._json(424, {'ok': False, 'error': 'Telegram non ha ricevuto la foto dopo 3 tentativi. Riprova tra poco.'})
        except TelegramError:
            self._json(424, {'ok': False, 'error': 'Telegram ha rifiutato la foto. Riapri ImageGEN e riprova.'})
        except Exception as exc:  # pragma: no cover - defensive fallback
            log.error('RICHIESTA', f'{path} non riuscita: {log.exc_text(exc)}')
            self._json(500, {'ok': False, 'error': 'Errore interno ImageGEN.'})


class Service:
    def __init__(self, telegram, renderer, catalog, chat_id):
        self.telegram = telegram
        self.renderer = renderer
        self.catalog = catalog
        self.chat_id = str(chat_id)

        self.session = secrets.token_urlsafe(18)
        self.stopped = False
        # Fine sessione (time.monotonic) e inizio, per le estensioni dell'ultimo minuto.
        self.started_at = time.monotonic()
        self.deadline = self.started_at + SESSION_DURATION_SECONDS
        self.deadline_lock = threading.Lock()
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
        # Scontorni in corso/finiti (id foto -> stato), per chiedere lo stato con richieste brevi.
        self.cutout_jobs = {}
        self.cutout_jobs_lock = threading.Lock()
        self.preview_jpeg_cache = {}
        self.ghost_cache = {}
        self.recent_sends = {}
        self.renderer.photos = self.photos
        # Ultimi invii (dal più recente): rimandabili dalla Mini App senza rifare la grafica.
        self.history = []
        self.history_lock = threading.Lock()
        self.last_resend = None
        self.ig_phrases = []
        self.saved_colors = {'title': [], 'jr': []}

    def store_photo(self, raw):
        width, height = check_photo(raw)
        photo_id = hashlib.sha256(raw).hexdigest()[:16]
        self.photos[photo_id] = raw
        while len(self.photos) > MAX_PHOTOS:
            self.photos.pop(next(iter(self.photos)))
        log.info('FOTO', f'Foto caricata · {width}×{height}')
        return {'photo_id': photo_id, 'width': width, 'height': height}

    def player_photo(self, envelope):
        """Matchday / Starting XI: posa 3:4 del giocatore dagli asset al posto della foto caricata.
        Entra tra le foto della sessione come un caricamento (stesso editor, stessa scia)."""
        import base64
        from PIL import Image
        from graphics.common import matchday_pose
        from livescore.graphics import goal as g
        envelope = envelope or {}
        name = str(envelope.get('player') or '')
        player = next((p for p in g.load_players() if p.name == name), None)
        if player is None:
            raise ValueError('Giocatore non trovato.')
        path = matchday_pose(player, str(envelope.get('kit') or 'home'), str(envelope.get('pose') or ''))
        out = self.store_photo(path.read_bytes())
        # Anteprima leggera per l'editor del telefono (la grafica usa il PNG intero).
        with Image.open(path) as image:
            image.thumbnail((720, 960))
            buf = io.BytesIO()
            image.save(buf, 'WEBP', quality=82)
        out['preview'] = 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
        log.info('FOTO', f'Posa di {player.name} ({path.name})')
        return out

    def store_story_shot(self, raw):
        """Screenshot di una storia (Citazione IG): tiene la storia senza l'interfaccia di Instagram e,
        a parte, la foto profilo (serve se il link non l'ha data)."""
        import story_shot
        photo, avatar, bars = story_shot.read(raw)
        out = self.store_photo(photo)
        out['cropped'] = avatar is not None
        if bars:
            out['bars'] = bars
        if avatar:
            try:
                out['avatar_id'] = self.store_photo(avatar)['photo_id']
            except ValueError:
                pass
        return out

    def _expires_ms(self):
        return int((time.time() + (self.deadline - time.monotonic())) * 1000)

    def session_info(self):
        return {'expires': self._expires_ms(),
                'max': int((time.time() + (self.started_at + SESSION_MAX_SECONDS - time.monotonic())) * 1000)}

    def extend(self, envelope=None):
        """Con "to_max" (tocco sul cronometro e conferma): subito al massimo, 60 minuti
        dall'avvio. Senza, nessun allungamento: risponde solo con la scadenza attuale."""
        to_max = isinstance(envelope, dict) and envelope.get('to_max') is True
        with self.deadline_lock:
            now = time.monotonic()
            left = self.deadline - now
            limit = self.started_at + SESSION_MAX_SECONDS
            extended = False
            if to_max and left > 0 and self.deadline < limit and not self.stopped:
                self.deadline = limit
                extended = True
                log.info('SESSIONE', f'Sessione portata al massimo · restano {(self.deadline - now) / 60:.0f} min')
        return {**self.session_info(), 'extended': extended}

    def layouts(self):
        """PROBABILE XI: disposizioni in uso per modulo + griglia di Modifica."""
        import layouts
        from graphics.probabili import GRID_X, GRID_Y
        everything = layouts.all_layouts()
        return {'layouts': everything, 'defaults': everything,
                'grid': {'x': GRID_X, 'y': GRID_Y},
                'scale': {'min': layouts.SCALE_MIN, 'max': layouts.SCALE_MAX}}

    def save_layout(self, envelope):
        """Salva subito in locale; il commit nel repository va in un thread."""
        import layouts
        action = envelope.get('action')
        if str(envelope.get('session') or '') != self.session or action not in ('layout', 'module_add', 'module_delete'):
            raise ValueError('Richiesta non valida.')
        if action == 'module_add':           # "+": nuovo modulo con disposizione automatica
            module, layout = layouts.create(envelope.get('module'))
            return {'module': module, 'layout': layout}
        module = str(envelope.get('module') or '')
        if action == 'module_delete':
            layouts.delete(module)
            return {'module': module}
        layout = layouts.clean(module, envelope.get('layout'))
        log.info('SALVATAGGIO', f"Posizioni {module} ricevute dalla Mini App · scala {round(layout['scale'] * 100)}%")
        threading.Thread(target=self._save_layout, args=(module, layout), daemon=True).start()
        return layout

    def _remember_layout(self, data):
        """PROBABILE XI: posizioni dell'anteprima diverse da quelle salvate -> si salvano.

        Non dipende solo da "Fatto" (richiesta separata che si può perdere): ogni
        anteprima porta già le posizioni con cui è disegnata la grafica.
        """
        if data.get('kind') != 'pxi' or not data.get('layout'):
            return
        try:
            import layouts
            if data['layout'] != layouts.get(data['module']):
                log.info('SALVATAGGIO', f"Posizioni {data['module']} nuove dall'anteprima: le salvo")
                threading.Thread(target=self._save_layout, args=(data['module'], data['layout']), daemon=True).start()
        except Exception as exc:
            log.warn('SALVATAGGIO', f'Posizioni non controllate: {type(exc).__name__}: {exc}')

    def _save_layout(self, module, layout):
        try:
            import layouts
            layouts.save(module, layout)
        except Exception as exc:
            log.warn('SALVATAGGIO', f'Posizioni non salvate: {type(exc).__name__}: {exc}')

    def page_background(self, kit, graphic=''):
        """Sfondo di pagina della maglia/competizione, ridotto (540x720), per l'editor foto."""
        from PIL import Image
        from graphics.uefa import ALL, background
        if kit not in ALL:
            raise ValueError('Maglia non valida.')
        graphic = graphic if graphic in ('matchday', 'starting_xi') else None
        key = ('pagebg', kit, graphic)
        if key not in self.overlays:
            with Image.open(background(kit, graphic)) as image:
                small = image.convert('RGB').resize((540, 720), Image.LANCZOS)
                out = io.BytesIO()
                small.save(out, format='JPEG', quality=85)
            self.overlays[key] = out.getvalue()
        return self.overlays[key]

    def pxi_background(self, kit):
        """Sfondo del campo di PROBABILE XI, ridotto, per l'editor delle posizioni."""
        from PIL import Image
        from graphics.common import asset_dir
        from graphics.probabili import KITS, _meta
        from graphics.uefa import is_theme, probabili_bg
        if kit not in KITS:
            raise ValueError('Maglia non valida.')
        key = ('pxibg', kit)
        if key not in self.overlays:
            path = probabili_bg(kit) if is_theme(kit) else asset_dir() / 'canva' / _meta()[kit]['bg']
            with Image.open(path) as image:
                small = image.convert('RGB').resize((540, 720), Image.LANCZOS)
                out = io.BytesIO()
                small.save(out, format='JPEG', quality=85)
            self.overlays[key] = out.getvalue()
        return self.overlays[key]

    def cutout_state(self, photo_id, start=False):
        """Stato dello scontorno: 'running', 'ready' o 'error'.

        Lo scontorno è un lavoro in background: la Mini App chiede lo stato con richieste
        brevi e scarica il PNG solo a lavoro finito. Una sola richiesta lunga attraverso il
        tunnel cade spesso mentre il processore è occupato dal modello.
        """
        with self.cutout_jobs_lock:
            job = self.cutout_jobs.get(photo_id)
            if job is None and photo_id in self.preview_cutouts:
                return {'state': 'ready', 'error': ''}
            if (job is None or job['state'] == 'error') and start:
                job = {'state': 'running', 'error': ''}
                self.cutout_jobs[photo_id] = job
                while len(self.cutout_jobs) > MAX_PHOTOS:
                    self.cutout_jobs.pop(next(iter(self.cutout_jobs)))
                threading.Thread(target=self._cutout_job, args=(photo_id, job), daemon=True).start()
            if job is None:
                return {'state': 'error', 'error': 'Scontorno non avviato.'}
            return {'state': job['state'], 'error': job['error']}

    def _cutout_job(self, photo_id, job):
        _lower_priority()
        try:
            self.cutout_preview(photo_id)
            job['state'] = 'ready'
            # Editor pronto con lo scontorno veloce: ora quello fine per la grafica vera.
            self.renderer.start_fine(photo_id)
        except Exception as exc:  # noqa: BLE001 - l'errore va alla Mini App, non al server
            job['error'] = str(exc) if isinstance(exc, ValueError) else 'Scontorno non riuscito.'
            job['state'] = 'error'
            log.warn('FOTO', f'Scontorno non riuscito: {type(exc).__name__}: {exc}')

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

    def overlay(self, name, kit, full=False):
        key = (name, kit, full)
        if key not in self.overlays:
            self.overlays[key] = overlay_preview(name, kit, full=full)
        return self.overlays[key]

    def _set_stage(self, stage):
        self.progress_stage = str(stage)

    def request_stop(self):
        """End the active session immediately and let run() perform normal cleanup."""
        if not self.stopped:
            log.info('SESSIONE', 'Chiusura richiesta dalla Mini App')
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

    @staticmethod
    def _table_version(data):
        """Classifica: impronta delle righe lette da Diretta.it per l'ultima grafica ('' per le altre)."""
        if data.get('kind') != 'table':
            return ''
        comp = str(data.get('competition') or '').upper()
        if data.get('view') == 'bracket':
            from graphics import tabellone
            raw = json.dumps((tabellone._last.get(comp) or {}).get('rounds'), sort_keys=True, ensure_ascii=False, default=str)
            return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]
        from graphics import classifica
        snap = classifica._last.get(comp) or {}
        raw = json.dumps(snap.get('classifica'), sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def _cache_fresh(cached, data, max_age):
        """La classifica scade presto (cambia live); le altre grafiche no."""
        return data.get('kind') != 'table' or time.time() - cached.get('updated', 0) <= max_age

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
                and self._cache_fresh(cached, data, TABLE_PREVIEW_REUSE_SECONDS)
            ):
                return cached['png'], cached.get('request_id') or request_state['id']

        log.info('ANTEPRIMA', f"{log.graphic_name(data)}: preparo l'anteprima")
        self._set_stage('render')
        self.renderer.used_fast_cutout = False
        png = self.renderer.render(data, progress=self._set_stage)

        with self.preview_cache_lock:
            self.preview_cache = {
                'fingerprint': fingerprint,
                'request_id': request_state['id'],
                'data': data,
                'png': png,
                'updated': time.time(),
                'fast_cutout': self.renderer.used_fast_cutout,
            }

        return png, request_state['id']

    def preview(self, envelope):
        # Un nuovo tentativo aspetta quello in corso e poi riusa l'anteprima già pronta.
        if not self.operation_lock.acquire(timeout=LOCK_WAIT_SECONDS):
            raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
        started = time.time()
        try:
            request_state = self._parse_request(envelope)
            self._remember_layout(request_state['data'])
            png, _ = self._render_and_cache(request_state)
            log.info('ANTEPRIMA', f"{log.graphic_name(request_state['data'])}: anteprima pronta in {time.time() - started:.1f} s")
            return png
        finally:
            self._set_stage('idle')
            self.operation_lock.release()

    def ghost(self, envelope):
        """Grafica senza foto, trasparente e leggera: l'editor la mostra sopra la foto.
        WebP con trasparenza (circa 10 volte più leggero del PNG: arriva prima al telefono);
        le ultime sagome restano in memoria, così tornando indietro compaiono subito."""
        data = self._parse_request(envelope)['data']
        key = self._fingerprint({k: v for k, v in data.items() if k not in PHOTO_FIELDS})
        if key not in self.ghost_cache:
            if not self.operation_lock.acquire(timeout=LOCK_WAIT_SECONDS):
                raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
            try:
                if key not in self.ghost_cache:
                    self.ghost_cache[key] = _ghost_webp(self.renderer.render(data, ghost=True))
                    while len(self.ghost_cache) > GHOST_CACHE_SIZE:
                        self.ghost_cache.pop(next(iter(self.ghost_cache)))
            finally:
                self.operation_lock.release()
        return self.ghost_cache[key]

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
            log.warn('SALVATAGGIO', f'Numeri di maglia non salvati: {type(exc).__name__}: {exc}')

    def _remember_names(self, players):
        """Nome/cognome scelti per i convocati inviati -> repository (data/name_splits.json)."""
        try:
            import logo_bundle
            import name_splits
            chosen = [(row[3], row[4]) for row in players if len(row) > 4]
            updates = name_splits.changes(chosen, name_splits.load())
            if updates:
                logo_bundle.NAME_SPLITS.update(updates)
                name_splits.save(updates)
        except Exception as exc:
            log.warn('SALVATAGGIO', f'Nome e cognome non salvati: {type(exc).__name__}: {exc}')

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
            log.warn('DATI', f'Calendario ESPN non disponibile: {type(exc).__name__}: {exc}')
            return []

    def settings(self, envelope):
        """Impostazioni › Loghi (anteprima e salvataggio) e › Nomi (nome italiano e hashtag)."""
        import logo_bundle
        import team_settings
        from graphics.common import _logo_rows, _manifest_rows, asset_dir

        if str(envelope.get('session') or '') != self.session:
            raise ValueError('Richiesta non valida.')
        action = envelope.get('action')
        if action == 'logo_current':
            # Logo nitido per il riquadro del pannello (il pacchetto dell'app ha solo miniature da 96 px):
            # quello in uso (anche caricato a mano) e quello FCLogo originale.
            from graphics.common import team_logo
            name, out = str(envelope.get('name') or ''), {}
            try:
                out['current'] = team_settings.preview_uri(team_logo(name).read_bytes(), 480)
            except (FileNotFoundError, OSError):
                pass
            row = next((r for r in _logo_rows(str(asset_dir())) if r.get('name') == name), None)
            fc = asset_dir() / 'team_logos' / str((row or {}).get('file') or '')
            if row and row.get('file') and fc.is_file():
                out['fclogo'] = team_settings.preview_uri(fc.read_bytes(), 480)
            return out
        if action == 'logo_preview':
            # Per l'editor: stemma senza margini (+ proporzioni) e posizione di partenza.
            # photo_id = logo appena caricato (parte come FCLogo); key = logo già salvato (parte da dov'è).
            from PIL import Image
            key = str(envelope.get('key') or '')
            if key:
                entry = team_settings._read(asset_dir()).get(key) or {}
                stored = asset_dir() / 'team_overrides' / str(entry.get('logo') or '')
                if not entry.get('logo') or not stored.is_file():
                    raise ValueError('Logo non trovato.')
                square = Image.open(stored)
                box = square.getchannel('A').getbbox() or (0, 0, *square.size)
                side = square.width
                frame = {'x': (box[0] + box[2]) / 2 / side - .5, 'y': (box[1] + box[3]) / 2 / side - .5,
                         's': max(box[2] - box[0], box[3] - box[1]) / side}
                mono = team_settings.trim(stored.read_bytes())
            else:
                photo_id = str(envelope.get('photo_id') or '')
                if envelope.get('fclogo'):
                    # Link di fclogo.top incollato: il PNG si scarica qui e diventa come un logo caricato.
                    photo_id = self.store_photo(team_settings.fclogo_logo(envelope['fclogo']))['photo_id']
                raw = self.photos.get(photo_id)
                if raw is None:
                    raise ValueError('Logo caricato scaduto: caricalo di nuovo.')
                mono, frame = team_settings.make_mono(raw), dict(team_settings.FRAME_DEFAULT)
                w, h = Image.open(io.BytesIO(mono)).size
                return {'preview': team_settings.preview_uri(mono, 480), 'aspect': w / h, 'frame': frame, 'photo_id': photo_id}
            w, h = Image.open(io.BytesIO(mono)).size
            return {'preview': team_settings.preview_uri(mono, 480), 'aspect': w / h, 'frame': frame}
        if action == 'names_list':       # Impostazioni › Nomi: nome ESPN -> nome italiano e hashtag
            return {'teams': team_settings.names_list(asset_dir())}
        if action == 'name_save':
            return team_settings.save_name(envelope.get('team') or {}, asset_dir())
        if action in ('emoji_team', 'emoji_pack', 'emoji_save'):   # Impostazioni › squadra › Emoji
            import team_emoji
            if action == 'emoji_team':
                return team_emoji.team_detail(envelope.get('team') or {}, asset_dir())
            if action == 'emoji_pack':
                return team_emoji.pack_sheet(str(envelope.get('pack') or ''), asset_dir())
            return team_emoji.save(envelope.get('emoji') or {}, asset_dir())
        if action != 'team_save':
            raise ValueError('Richiesta non valida.')
        assets = str(asset_dir())
        result = team_settings.save(envelope.get('team') or {}, assets, _manifest_rows(assets), self.photos)
        row = next((r for r in _logo_rows(assets) if r.get('override_key') == result['key']), None)
        if row is None and not result['key'].startswith('new:'):
            from livescore.core.team_matching import normalize_team_name
            row = next((r for r in _logo_rows(assets) if normalize_team_name(r.get('name', '')) == result['key']), None)
        team = logo_bundle._prepare(asset_dir(), row) if row else None
        # Pacchetto della mini app rifatto con la correzione: chi la riapre in questa sessione la vede.
        threading.Thread(target=self._rebuild_catalog, daemon=True).start()
        return {'team': team, 'key': result['key'], 'remote': result['remote'], 'warning': result['warning']}

    def _rebuild_catalog(self):
        try:
            self.catalog_bundle = build_team_bundle()
        except Exception as exc:
            log.warn('AVVIO', f'Pacchetto loghi non rifatto: {type(exc).__name__}: {exc}')

    def espn_teams(self):
        """Squadre del calendario Juventus su ESPN (stagione in corso e precedente, prossime partite)."""
        import requests

        import fixtures
        seen = {}
        try:
            events = list(fixtures._fetch())
            last = requests.get(fixtures.URL, params={'season': time.localtime().tm_year - 1}, timeout=15)
            if last.ok:
                events += last.json().get('events', [])
        except Exception as exc:
            log.warn('DATI', f'Squadre ESPN non disponibili: {type(exc).__name__}: {exc}')
            return []
        for e in events:
            league = (e.get('league') or {}).get('name') or ''
            for c in ((e.get('competitions') or [{}])[0].get('competitors') or []):
                team = c.get('team') or {}
                name, tid = team.get('displayName') or '', str(team.get('id') or c.get('id') or '')
                if name and tid != fixtures.JUVENTUS_ID and name not in seen:
                    seen[name] = {'name': name, 'id': tid, 'league': league, 'date': str(e.get('date', ''))[:10]}
        return sorted(seen.values(), key=lambda x: x['date'], reverse=True)

    def kit(self, event_id, league):
        """Maglia della Juventus nella partita ESPN (partite giocate), '' se non si sa."""
        try:
            import fixtures
            return fixtures.kit(event_id, league)
        except Exception as exc:
            log.warn('DATI', f'Maglia non trovata su ESPN: {type(exc).__name__}: {exc}')
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
            log.warn('DATI', f'Partita non trovata su ESPN: {type(exc).__name__}: {exc}')
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
        asked = time.time()
        if not self.operation_lock.acquire(timeout=LOCK_WAIT_SECONDS):
            log.warn('INVIO', f'Invio rifiutato: servizio occupato da {LOCK_WAIT_SECONDS} s')
            raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
        waited = time.time() - asked
        try:
            request_state = self._parse_request(envelope)
            data = copy.deepcopy(request_state['data'])
            fingerprint = self._fingerprint(data)

            # Stessa grafica appena inviata (risposta persa per strada): niente doppione.
            # Classifica: si controlla dopo, sulle righe aggiornate (se cambiano, si reinvia).
            sent = self.recent_sends.get(fingerprint)
            if data['kind'] != 'table' and sent and time.time() - sent[1] < RESEND_GUARD_SECONDS:
                log.info('INVIO', f"{log.graphic_name(data)}: già inviata poco fa, non la rimando")
                return sent[0]

            with self.preview_cache_lock:
                cached = self.preview_cache
                if (
                    cached
                    and cached.get('fingerprint') == fingerprint
                    and cached.get('png')
                    and self._cache_fresh(cached, data, TABLE_SEND_REUSE_SECONDS)
                    and not cached.get('fast_cutout')
                ):
                    png = cached['png']
                else:
                    png = None
                    same = bool(cached and cached.get('fingerprint') == fingerprint and cached.get('png'))
                    reason = ('anteprima con lo scontorno veloce, rifaccio con quello fine'
                              if same and cached.get('fast_cutout')
                              else 'anteprima di più di un minuto fa, riscarico la classifica' if same
                              else 'preparo la grafica da inviare')

            if png is None:
                log.info('INVIO', f"{log.graphic_name(data)}: {reason}")
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
                log.info('INVIO', f"{log.graphic_name(data)}: uso l'anteprima già pronta")

            if data['kind'] == 'table':
                # Doppione solo se le righe della classifica sono identiche a quella appena inviata.
                fingerprint = f'{fingerprint}:{self._table_version(data)}'
                sent = self.recent_sends.get(fingerprint)
                if sent and time.time() - sent[1] < RESEND_GUARD_SECONDS:
                    log.info('INVIO', f"{log.graphic_name(data)}: classifica identica inviata poco fa, non la rimando")
                    return sent[0]

            sending = time.time()
            text = caption.safe_build(data)
            message_id = self._send_photo(png, f"{data['kind']}-{request_state['id']}.png",
                                          log.graphic_name(data), text)
            self.generated_message_ids.append(int(message_id))
            self.recent_sends[fingerprint] = (int(message_id), time.time())
            self._remember_send(message_id, data, png, text)
            self._remember_ig_name(data)
            if data['kind'] == 'xi':
                threading.Thread(target=self._remember_shirts, args=(data['lineup'],), daemon=True).start()
            if data['kind'] == 'conv':
                threading.Thread(target=self._remember_names, args=(data['players'],), daemon=True).start()
            took = time.time() - sending
            log.info('INVIO', f"{log.graphic_name(data)}: inviata su Telegram · {log.kb(len(png))} in {took:.1f} s"
                              + (f' (in coda {waited:.1f} s)' if waited >= 1 else ''))
            log.sent(log.graphic_name(data), f'{log.kb(len(png))} · {took:.1f} s')
            return int(message_id)
        finally:
            self.operation_lock.release()

    def _send_photo(self, png, filename, name, text=None):
        """Foto su Telegram. Se Telegram dice che non l'ha ricevuta (troppe richieste,
        connessione mai aperta) riprova da solo, fino a SEND_TRIES volte. Con esito incerto
        (risposta persa) non riprova: la foto potrebbe essere già nella chat."""
        for attempt in range(1, SEND_TRIES + 1):
            started = time.time()
            try:
                message_id = int(self.telegram.photo(png, filename, text))
                if getattr(self.telegram, 'caption_dropped', False):
                    log.warn('INVIO', f'{name}: Telegram ha rifiutato la didascalia, foto inviata senza testo')
                return message_id
            except NotSent as exc:
                if attempt >= SEND_TRIES:
                    log.warn('INVIO', f"{name}: Telegram non l'ha ricevuta dopo {SEND_TRIES} tentativi ({exc})")
                    raise
                wait = min(10, exc.retry_after or 2 * attempt)
                log.warn('INVIO', f"{name}: Telegram non l'ha ricevuta ({exc}), riprovo tra {wait} s "
                                  f'({attempt + 1}/{SEND_TRIES})')
                time.sleep(wait)
            except Exception as exc:
                log.warn('INVIO', f'{name}: Telegram non ha confermato '
                                  f'({type(exc).__name__}, {time.time() - started:.1f} s, {log.kb(len(png))})')
                raise

    def _remember_send(self, message_id, data, png, text=None):
        """Aggiunge l'invio a "Ultimi invii", con una miniatura per la Mini App, e lo salva nel
        repo degli asset (con il file_id Telegram: resta anche per le sessioni dopo)."""
        entry = {'id': int(message_id), 'name': log.graphic_name(data), **_send_detail(data),
                 'kind': data.get('kind', ''), 'at': int(time.time() * 1000), 'png': png, 'caption': text or '',
                 'thumb': _jpeg(png, (240, 320), 80),
                 **(getattr(self.telegram, 'last_photo', None) or {})}
        with self.history_lock:
            self.history.insert(0, entry)
            del self.history[HISTORY_SIZE:]
            rows = list(self.history)
        sent_store.save_history(rows)

    def _history_entry(self, message_id):
        with self.history_lock:
            entry = next((e for e in self.history if str(e['id']) == str(message_id)), None)
        if entry is None:
            raise ValueError('Grafica non più disponibile.')
        return entry

    def _history_bytes(self, entry, key, file_key):
        """Immagine dell'invio: in memoria (questa sessione) o scaricata da Telegram (sessioni passate)."""
        if entry.get(key):
            return entry[key]
        if not entry.get(file_key):
            raise ValueError('Immagine non disponibile.')
        try:
            entry[key] = self.telegram.download(entry[file_key])
        except TelegramError as exc:
            log.warn('INVII', f"{entry.get('name')}: immagine non scaricata da Telegram ({exc})")
            raise ValueError('Immagine non disponibile su Telegram.') from None
        return entry[key]

    def history_list(self):
        with self.history_lock:
            return [{k: v for k, v in e.items() if k in ('id', 'name', 'player', 'minute', 'score',
                                                         'opponent', 'note', 'kind', 'at')} for e in self.history]

    def history_thumb(self, message_id):
        entry = self._history_entry(message_id)
        if entry.get('thumb'):
            return entry['thumb']
        return self._history_bytes(entry, 'thumb', 'thumb_id')

    def use_sent(self, envelope):
        """Storia IG: una grafica già inviata diventa la foto della storia (come una foto caricata)."""
        entry = self._history_entry((envelope or {}).get('id'))
        raw = entry.get('png') or self._history_bytes(entry, 'full', 'file_id')
        return self.store_photo(raw)

    def ig_post(self, envelope):
        """CITAZIONE IG / X / THREADS: legge il post dal link (instagram.py, xpost.py o threadspost.py) e
        tiene le sue foto come foto caricate. Per X e Threads in fondo c'è sempre anche lo sfondo di
        riserva (molti post non hanno foto)."""
        import instagram
        import threadspost
        import xpost
        from graphics import ig_quote
        url = (envelope or {}).get('url')
        th = threadspost.is_threads_url(url)
        x = th or xpost.is_x_url(url)          # X e Threads: nome e @account arrivano entrambi dal post
        story = not x and instagram.story_user(url) is not None     # storia: niente foto, la carichi tu
        if story:
            try:
                post = instagram.fetch_story(url)
            except Exception:       # storia scaduta o Instagram che non risponde: l'account c'è nel link
                handle = instagram.story_user(url)
                post = {'code': '', 'user': handle, 'name': handle, 'verified': False, 'text': '',
                        'avatar': None, 'photos': [], 'story': True}
        else:
            post = threadspost.fetch(url) if th else xpost.fetch(url) if x else instagram.fetch(url)
        photos = []
        for raw in post['photos']:
            try:
                photos.append(self.store_photo(raw))
            except ValueError:
                continue
        if x:
            photos.append({**self.store_photo(ig_quote.x_background()), 'bg': True})
        if not photos and not story:
            raise ValueError('Foto del post non valide. Carica la foto a mano.')
        avatar = None
        if post['avatar']:
            try:
                avatar = self.store_photo(post['avatar'])['photo_id']
            except ValueError:
                avatar = None
        # Instagram dà solo l'username: il nome è quello scritto l'ultima volta per l'account (se c'è).
        handle = post.get('handle') or ('' if x else post['user'])
        user = post['user'] if x else sent_store.load_names().get(handle.lower(), post.get('name') or handle)
        # Testo già senza emoji (come uscirà nella grafica): nella Mini App si vede quello vero.
        return {'platform': 'threads' if th else 'x' if x else 'ig', 'user': ig_quote.clean_name(user), 'handle': handle,
                'verified': bool(post.get('verified')), 'text': ig_quote.clean_text(post['text']),
                'photos': photos, 'avatar_id': avatar, 'story': story}

    def _remember_ig_name(self, data):
        """Citazione IG inviata con un nome diverso dall'username: la prossima volta arriva già."""
        handle, name = str(data.get('handle') or '').lower(), str(data.get('name') or '')
        if data.get('kind') != 'igq' or not handle or not name or name.lower() == handle:
            return
        names = sent_store.load_names()
        if names.get(handle) != name:
            names[handle] = name
            sent_store.save_names(names)
            log.info('SALVATAGGIO', f'Nome per @{handle}: {name}')

    def photo_thumb(self, photo_id, big=False):
        """Foto caricata ridotta: miniatura (scelta della foto) o grande (editor della foto)."""
        raw = self.photos.get(str(photo_id or ''))
        if not raw:
            raise ValueError('Foto non trovata.')
        key = ('thumb', photo_id, big)
        if key not in self.overlays:
            self.overlays[key] = _jpeg(raw, (1080, 1920) if big else (360, 480), 85 if big else 82)
        return self.overlays[key]

    def phrases(self, envelope):
        """Storia IG: frasi pronte (elenco, aggiungi, togli). Salvate nel repo degli asset."""
        from graphics import ig_story
        action = (envelope or {}).get('action')
        text = sent_store.clean_phrase((envelope or {}).get('text'))
        color = ig_story.text_color((envelope or {}).get('color'))
        with self.history_lock:
            phrases = list(self.ig_phrases)
            if action == 'add':
                if not text:
                    raise ValueError('Scrivi prima la frase.')
                # Stessa frase già salvata: si aggiorna il colore e torna in cima.
                phrases = [{'text': text, 'color': color}] + [p for p in phrases if p['text'] != text]
            elif action == 'delete':
                phrases = [p for p in phrases if p['text'] != text]
            elif action != 'list':
                raise ValueError('Richiesta non valida.')
            changed = phrases != self.ig_phrases
            self.ig_phrases = phrases[:sent_store.PHRASES_KEEP]
        if changed:
            sent_store.save_phrases(self.ig_phrases)
            log.info('SALVATAGGIO', f"Frasi pronte: {'aggiunta' if action == 'add' else 'tolta'} una frase "
                                    f'({len(self.ig_phrases)} in tutto)')
        return {'phrases': self.ig_phrases}

    def colors(self, envelope):
        """Post: colori aggiunti con il + (titolo e logo JR). Elenco, aggiungi, togli; nel repo degli asset."""
        from graphics import photo_jr
        envelope = envelope or {}
        action, target = envelope.get('action'), envelope.get('target')
        if action != 'list':
            if target not in ('title', 'jr'):
                raise ValueError('Richiesta non valida.')
            if target == 'title':
                color = photo_jr.clean_title_color(envelope.get('color'))
            else:
                color = photo_jr.clean_color(envelope.get('color'))
                if not isinstance(color, dict):
                    raise ValueError('Nero, bianco e oro sono già tra i classici.')
        with self.history_lock:
            saved = {k: list(v) for k, v in self.saved_colors.items()}
            if action == 'add':
                saved[target] = [color] + [c for c in saved[target] if c != color]
            elif action == 'delete':
                saved[target] = [c for c in saved[target] if c != color]
            elif action != 'list':
                raise ValueError('Richiesta non valida.')
            saved = {k: v[:sent_store.COLORS_KEEP] for k, v in saved.items()}
            changed = saved != self.saved_colors
            self.saved_colors = saved
        if changed:
            sent_store.save_colors(saved)
            log.info('SALVATAGGIO', f"Colori del Post: {'aggiunto' if action == 'add' else 'tolto'} un colore "
                                    f"({len(saved['title'])} titolo · {len(saved['jr'])} JR)")
        return {'colors': self.saved_colors}

    def history_image(self, message_id):
        """Grafica inviata, come JPEG leggero per la pagina "Ultimi invii"."""
        entry = self._history_entry(message_id)
        if entry.get('png'):
            return self.preview_jpeg(entry['png'])
        return self._history_bytes(entry, 'full', 'file_id')      # da Telegram è già un JPEG

    def resend(self, envelope):
        """Rimanda su Telegram una grafica già inviata in questa sessione (stesso PNG)."""
        try:
            wanted = int((envelope or {}).get('id'))
        except (TypeError, ValueError):
            raise ValueError('Invio non valido.') from None
        with self.history_lock:
            entry = next((e for e in self.history if e['id'] == wanted), None)
        if entry is None or not (entry.get('png') or entry.get('file_id')):
            raise ValueError('Grafica non più disponibile: rifalla da capo.')
        if not self.operation_lock.acquire(timeout=LOCK_WAIT_SECONDS):
            raise BusyError('Sto già elaborando una richiesta. Attendi qualche secondo.')
        try:
            # Doppio tocco o risposta persa: la stessa grafica rimandata da pochi secondi non riparte.
            last = self.last_resend
            if last and last[0] == wanted and time.time() - last[2] < 20:
                log.info('INVIO', f"{entry['name']}: già rimandata poco fa, non la rimando")
                return last[1]
            started = time.time()
            # Di questa sessione: lo stesso PNG. Delle sessioni passate: la foto già su Telegram.
            message_id = self._send_photo(entry.get('png') or entry['file_id'],
                                          f"{entry['kind']}-rimandata.png", entry['name'], entry.get('caption'))
            self.generated_message_ids.append(message_id)
            self.last_resend = (wanted, message_id, time.time())
            took = time.time() - started
            log.info('INVIO', f"{entry['name']}: rimandata su Telegram in {took:.1f} s")
            size = f"{log.kb(len(entry['png']))} · " if entry.get('png') else ''
            log.sent(f"{entry['name']} (rimandata)", f'{size}{took:.1f} s')
            return message_id
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
        log.info('AVVIO', f'Servizio locale pronto · porta {port}')

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
            log.info('SESSIONE', f'Messaggi della sessione cancellati: {len(ids)}')
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
        (log.warn if failed else log.info)('SESSIONE', f'Messaggi della sessione cancellati: {len(ids) - failed}'
            + (f' · non cancellati: {failed}' if failed else ''))

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

        # Nessun messaggio, né all'avvio né in chiusura: il tasto "ImageGEN" in basso
        # nella chat torna quello normale qui sotto e sparisce.
        try:
            self.telegram.reset_menu_button()
        except TelegramError:
            pass

    def _wait_tunnel(self, direct_url, timeout=TUNNEL_READY_SECONDS):
        """True quando l'indirizzo pubblico risponde (da internet, come dal telefono) con
        questa sessione, TUNNEL_READY_STREAK volte di fila. Il tunnel appena creato spesso
        non funziona ancora per qualche secondo: il pulsante deve partire dopo."""
        import urllib.request

        url = f"{direct_url.rstrip('/')}/session?{urlencode({'session': self.session})}"
        start = time.monotonic()
        streak = attempts = 0
        last = ''
        time.sleep(1.5)
        while time.monotonic() - start < timeout and not self.stopped:
            attempts += 1
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'ImageGEN-JR tunnel check'})
                with urllib.request.urlopen(request, timeout=6) as response:
                    ok = response.status == 200 and b'"ok": true' in response.read(4096)
                last = 'risposta non valida' if not ok else ''
            except Exception as exc:
                ok = False
                last = f'{type(exc).__name__}: {exc}'[:120]
            streak = streak + 1 if ok else 0
            if streak >= TUNNEL_READY_STREAK:
                log.info('TUNNEL', f'Tunnel raggiungibile da internet in {time.monotonic() - start:.1f} s ({attempts} prove)')
                return True
            time.sleep(0.7 if ok else 1.5)
        log.warn('TUNNEL', f'Tunnel non raggiungibile dopo {time.monotonic() - start:.0f} s ({attempts} prove) · {last}')
        return False

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
            log.warn('AVVIO', f'Pacchetto loghi non disponibile: {type(exc).__name__}: {exc}')

        # Ultimi invii delle sessioni passate e frasi pronte della Storia IG (repo degli asset).
        with self.history_lock:
            self.history = sent_store.load_history()
            self.ig_phrases = sent_store.load_phrases()
            self.saved_colors = sent_store.load_colors()
        if self.history or self.ig_phrases:
            log.info('AVVIO', f'Ultimi invii: {len(self.history)} · frasi pronte: {len(self.ig_phrases)}')

        self._start_http_server()
        # Browser per le grafiche acceso subito: la prima anteprima non aspetta l'avvio.
        threading.Thread(target=_warm_up_renderer, daemon=True).start()
        threading.Thread(target=_warm_up_cutout, daemon=True).start()
        if not self._wait_tunnel(direct_url):
            self._stop_http_server()
            if self.stopped:          # run annullato mentre si aspettava: si esce e basta
                return
            raise TunnelNotReady(f'tunnel senza risposta dopo {TUNNEL_READY_SECONDS} s')

        parts = urlsplit(webapp_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['session'] = self.session
        query['direct'] = direct_url.rstrip('/') + '/submit'
        # Scadenza in ms epoch, per il timer della Mini App (stessa durata del loop qui sotto).
        session_seconds = min(SESSION_DURATION_SECONDS, max(1, duration))
        self.started_at = time.monotonic()
        self.deadline = self.started_at + session_seconds
        query['expires'] = str(self._expires_ms())

        launch_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

        try:
            self.telegram.reset_menu_button()
        except TelegramError:
            pass

        self.launcher_message_id = self.telegram.webapp_launcher(launch_url)
        opened = log.now()
        log.info('SESSIONE', f'Pulsante inviato su Telegram · sessione aperta per {session_seconds / 60:.0f} min')

        try:
            # self.deadline può spostarsi in avanti (cronometro → massimo) mentre la sessione è aperta.
            while not self.stopped and time.monotonic() < self.deadline:
                time.sleep(0.15)
        finally:
            self._stop_http_server()
            self.cleanup()
            sent_store.wait()
            log.info('SESSIONE', 'Sessione chiusa')
            log.write_summary(opened, log.now())


def _jpeg(raw, size, quality):
    """Immagine ridotta in JPEG (miniature). b'' se non si riesce."""
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(raw)).convert('RGB')
        image.thumbnail(size)
        out = io.BytesIO()
        image.save(out, format='JPEG', quality=quality)
        return out.getvalue()
    except Exception:  # noqa: BLE001 - senza miniatura l'invio resta comunque in elenco
        return b''


def _send_detail(data):
    """Dati mostrati in "Ultimi invii", separati: la Mini App li mette su due righe
    (giocatore e minuto; risultato e avversario, oppure `note`). Il nome dell'avversario è
    quello del catalogo: la Mini App lo mostra col nome italiano (Impostazioni › Nomi)."""
    kind = data.get('kind')
    score = data.get('score')
    opponent = data.get('opponent')
    empty = {'player': '', 'minute': '', 'score': '', 'opponent': '', 'note': ''}
    # Storia e Citazioni: nome dell'account (con @account se c'è) e inizio del testo.
    if kind in ('igq', 'xq', 'thq', 'igbn'):
        text = ' '.join(str(data.get('text') or '').split())
        note = (text[:117] + '…') if len(text) > 120 else text
        if not note and data.get('photo_id'):
            note = 'Solo foto'
        who = ' · '.join(v for v in (str(data.get('name') or ''),
                                     f"@{data['handle']}" if data.get('handle') else '') if v)
        return {**empty, 'player': who, 'note': note}
    if kind == 'conv':
        n = len(data.get('players') or [])
        return {**empty, 'player': f'{n} giocatori',
                'note': ', '.join(p[3] for p in (data.get('players') or [])[:4]) + ('…' if n > 4 else '')}
    if kind == 'table':
        names = {'SA': 'Serie A', 'CI': 'Coppa Italia', 'UCL': 'Champions League', 'UEL': 'Europa League',
                 'UECL': 'Conference League'}
        return {**empty, 'player': names.get(str(data.get('competition') or ''), '')}
    if kind == 'jr':
        style = {'classic': 'Classica', 'blur': 'Sfocata', 'collage': 'Collage',
                 'title': 'Titolo'}.get(data.get('style'), '')
        extra = (data.get('ratio') if data.get('style') == 'classic'
                 else str(data.get('title') or '').upper() if data.get('style') == 'title'
                 else f"{len(data.get('cards') or data.get('cells') or [])} foto")
        return {**empty, 'player': ' · '.join(v for v in (style, extra) if v)}
    if kind == 'cal':
        from graphics.calendar import MONTHS
        n = len(data.get('matches') or [])
        return {**empty, 'player': f"{MONTHS[int(data['month']) - 1].capitalize()} {data.get('year', '')}".strip(),
                'note': f"{n} partit{'a' if n == 1 else 'e'}"}
    team = str(opponent.get('name') or '') if isinstance(opponent, dict) else ''
    if kind == 'squad':
        return {**empty, 'player': f"{len(data.get('players') or [])} convocati", 'opponent': team}
    if kind == 'md':
        info = data.get('info') or {}
        when = (info.get('date', '').title(), info.get('time', '').split(' ')[0])     # senza CET/CEST
        return {**empty, 'player': ' · '.join(v for v in when if v),
                'opponent': team}
    if kind == 'pxi':
        return {**empty, 'player': str(data.get('module') or ''), 'opponent': team}
    if kind == 'stats':
        moment = {'HT': 'Primo tempo', '2H_END': 'Fine 90’', 'FT': 'Finale'}.get(data.get('moment'), '')
        return {**empty, 'player': moment, 'opponent': team}
    pens = data.get('shootout')
    if isinstance(pens, (list, tuple)) and len(pens) == 2 and isinstance(score, (list, tuple)) and len(score) == 2:
        score = (f'{score[0]}', f'{score[1]} ({pens[0]}-{pens[1]} rig.)')
    return {
        'player': str(data.get('player') or ''),
        'minute': f"{data['minute']}'" if data.get('minute') else '',
        'score': f'{score[0]}-{score[1]}' if isinstance(score, (list, tuple)) and len(score) == 2 else '',
        'opponent': team,
    }


def _warm_up_renderer():
    try:
        from graphics.common import warm_up
        warm_up()
        log.info('AVVIO', 'Browser grafiche pronto')
    except Exception as exc:
        log.warn('AVVIO', f'Browser grafiche non avviato: {type(exc).__name__}: {exc}')
    try:
        from graphics.classifica import warm_up_fonts
        warm_up_fonts()
    except Exception as exc:  # noqa: BLE001 - si riprova alla prima classifica
        log.warn('AVVIO', f'Font della classifica non preparati: {type(exc).__name__}: {exc}')
    try:
        from graphics.squad_list import warm_up as squad_warm_up
        squad_warm_up()          # geometria della foto della rivista (circa 30 s, una volta sola)
        log.info('AVVIO', 'Squad List pronta')
    except Exception as exc:  # noqa: BLE001 - si calcola alla prima Squad List
        log.warn('AVVIO', f'Squad List non preparata: {type(exc).__name__}: {exc}')


def _lower_priority():
    """Il modello di scontorno occupa tutto il processore e il tunnel Cloudflare, che gira nello
    stesso computer, resta indietro: la Mini App vede \"connessione instabile\". Con priorità più
    bassa per i thread del modello il tunnel passa sempre per primo."""
    try:
        os.setpriority(os.PRIO_PROCESS, 0, 5)
    except (AttributeError, OSError):
        pass


def _warm_up_cutout():
    """Modello di scontorno caricato subito: la prima foto HALF/END/FULL TIME non aspetta."""
    _lower_priority()
    try:
        from livescore.graphics import phase_layers
        from PIL import Image
        phase_layers.cutout(Image.new('RGB', (64, 64)))
        log.info('AVVIO', 'Scontorno veloce pronto (ISNet, editor)')
    except Exception as exc:
        log.warn('AVVIO', f'Scontorno non avviato: {type(exc).__name__}: {exc}')
        return
    try:
        if phase_layers.FINE_MODEL:
            phase_layers.warm_up_fine()
            log.info('AVVIO', f'Scontorno fine pronto ({phase_layers.FINE_MODEL}, grafica finale)')
    except Exception as exc:
        log.warn('AVVIO', f'Scontorno fine non avviato, uso solo quello veloce: {type(exc).__name__}: {exc}')


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
    except TunnelNotReady as exc:
        log.warn('TUNNEL', 'Tunnel non raggiungibile: il workflow ne apre uno nuovo')
        raise SystemExit(TUNNEL_NOT_READY_EXIT)
    except Exception as exc:
        log.error('AVVIO', f'Servizio fermato: {log.exc_text(exc)}')
        raise SystemExit(1)
