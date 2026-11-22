"""Dati della Mini App che restano tra una sessione e l'altra, nel repo degli asset:

- imagegen/history.json   "Ultimi invii": nome, dettagli e riferimento Telegram (file_id)
                          di ogni grafica inviata. Le immagini restano su Telegram: con il
                          file_id si rimandano e si riscaricano anche dopo la sessione.
- imagegen/ig_phrases.json Storia IG: frasi pronte.
- imagegen/colors.json     Post: colori aggiunti con il + ({'title': ['#rrggbb'], 'jr': [colore JR]}).
- imagegen/editor_templates.json  Editor libero: modelli salvati ([{'id', 'name', 'doc'}], senza foto).
- imagegen/captions.json  Impostazioni › Messaggi: modelli dei testi cambiati ({tipo: testo}).
- imagegen/md_tv.json     Impostazioni › Matchday: canale TV cambiato ({competizione: canale}).

Il workflow copia la cartella imagegen/ nella cartella asset all'avvio (lettura subito, senza
rete); ogni modifica si scrive in locale e poi con un commit (team_settings._commit), in un
thread: un salvataggio alla volta, l'ultimo stato vince.
"""
import json
import os
import threading

import log

DIRNAME = 'imagegen'
HISTORY = 'history.json'
PHRASES = 'ig_phrases.json'
COLORS = 'colors.json'
COLORS_KEEP = 24
TEMPLATES = 'editor_templates.json'
TEMPLATES_KEEP = 40
TEMPLATE_MAX = 12000             # byte del modello (JSON): livelli, testi e stili, mai le foto
CAPTIONS = 'captions.json'
TV = 'md_tv.json'
NAMES = 'ig_names.json'          # Citazione IG: nome scritto a mano per ogni account ({username: nome})
HISTORY_KEEP = 20
PHRASES_KEEP = 40
PHRASE_MAX = 500

_pending = {}                 # nome file -> dati da scrivere
_pending_lock = threading.Lock()
_worker = None


def _dir():
    from graphics.common import asset_dir
    return asset_dir() / DIRNAME


def _read(name, default):
    try:
        value = json.loads((_dir() / name).read_text(encoding='utf-8'))
        return value if isinstance(value, type(default)) else default
    except (OSError, ValueError):
        return default


def load_history():
    """Ultimi invii delle sessioni passate (dal più recente), senza immagini."""
    rows = [r for r in _read(HISTORY, []) if isinstance(r, dict) and r.get('file_id') and r.get('id')]
    return rows[:HISTORY_KEEP]


def clean_phrase(value):
    """Spazi in più tolti riga per riga; gli a capo restano (nella storia contano)."""
    lines = [' '.join(line.split()) for line in str(value or '').replace('\r', '').split('\n')]
    return '\n'.join(lines).strip()[:PHRASE_MAX]


PHRASE_EXTRA = ('label', 'label_text', 'source', 'link_text')   # etichetta, titolo, fonte, link


def load_phrases():
    """Frasi pronte: [{'text', 'color'}] (le prime salvate erano solo testo: colore di base).
    Quelle salvate dopo hanno anche etichetta, titolo, fonte e link ('label' c'è sempre, anche vuota)."""
    out = []
    for item in _read(PHRASES, []):
        row = item if isinstance(item, dict) else {'text': item}
        text = clean_phrase(row.get('text'))
        if text:
            phrase = {'text': text, 'color': str(row.get('color') or 'black')}
            if 'label' in row:
                phrase.update({k: str(row.get(k) or '') for k in PHRASE_EXTRA})
            out.append(phrase)
    return out[:PHRASES_KEEP]


def load_colors():
    """Colori salvati: titolo = esadecimali, jr = colori liberi del logo (tinta unita o sfumatura)."""
    from graphics import photo_jr
    raw = _read(COLORS, {})
    out = {'title': [], 'jr': []}
    for value in raw.get('title') or []:
        try:
            out['title'].append(photo_jr.clean_title_color(value))
        except ValueError:
            pass
    for value in raw.get('jr') or []:
        try:
            color = photo_jr.clean_color(value)
        except ValueError:
            continue
        if isinstance(color, dict):
            out['jr'].append(color)
    return {k: v[:COLORS_KEEP] for k, v in out.items()}


def clean_template(value):
    """Modello dell'editor libero: {'id', 'name', 'doc'}; doc = pagina e livelli (le foto restano da
    inserire). ValueError se non è un modello valido."""
    import re
    if not isinstance(value, dict):
        raise ValueError('Modello non valido.')
    name = ' '.join(str(value.get('name') or '').split())[:40]
    doc = value.get('doc')
    if not name:
        raise ValueError('Scrivi il nome del modello.')
    if not isinstance(doc, dict) or not isinstance(doc.get('layers'), list):
        raise ValueError('Modello non valido.')
    for layer in doc['layers']:
        if isinstance(layer, dict):
            layer.pop('src', None)                       # niente foto nel modello
    if len(json.dumps(doc, ensure_ascii=False)) > TEMPLATE_MAX:
        raise ValueError('Modello troppo grande.')
    tid = str(value.get('id') or '')
    if not re.fullmatch(r'[a-z0-9]{6,16}', tid):
        raise ValueError('Modello non valido.')
    return {'id': tid, 'name': name, 'doc': doc}


def load_templates():
    out = []
    for item in _read(TEMPLATES, []):
        try:
            out.append(clean_template(item))
        except ValueError:
            pass
    return out[:TEMPLATES_KEEP]


def save_templates(templates):
    _save(TEMPLATES, templates[:TEMPLATES_KEEP], 'ImageGen: modelli dell\'editor libero')


def load_captions():
    """Modelli dei messaggi cambiati nella Mini App (solo i tipi che esistono ancora)."""
    import caption
    out = {}
    for kind, text in _read(CAPTIONS, {}).items():
        text = caption.clean_template(text)
        if kind in caption.TEMPLATE_KINDS and text:
            out[kind] = text
    return out


def save_captions(captions):
    _save(CAPTIONS, captions, 'ImageGen: modelli dei messaggi')


def load_tv():
    """Canali TV del Matchday cambiati nella Mini App (solo le competizioni che esistono)."""
    import caption
    out = {}
    for comp, tv in _read(TV, {}).items():
        tv = caption.clean_tv(tv)
        if comp in caption.MD_TV and tv:
            out[comp] = tv
    return out


def save_tv(tv):
    _save(TV, tv, 'ImageGen: canali TV del Matchday')


def save_colors(colors):
    _save(COLORS, colors, 'ImageGen: colori salvati del Post')


def save_history(entries):
    keep = ('id', 'name', 'player', 'minute', 'score', 'opponent', 'note', 'kind', 'at', 'file_id', 'thumb_id', 'caption')
    rows = [{k: e.get(k) for k in keep} for e in entries if e.get('file_id')][:HISTORY_KEEP]
    _save(HISTORY, rows, 'ImageGen: ultimi invii')


def load_names():
    return {str(k): str(v) for k, v in _read(NAMES, {}).items() if str(v).strip()}


def save_names(names):
    _save(NAMES, dict(sorted(names.items())), 'ImageGen: nomi degli account Instagram')


def save_phrases(phrases):
    _save(PHRASES, phrases[:PHRASES_KEEP], 'ImageGen: frasi pronte della Storia IG')


def _save(name, data, message):
    """Subito in locale, poi nel repo (in coda: un commit alla volta)."""
    global _worker
    text = json.dumps(data, ensure_ascii=False, indent=1) + '\n'
    try:
        _dir().mkdir(parents=True, exist_ok=True)
        (_dir() / name).write_text(text, encoding='utf-8')
    except OSError as exc:
        log.warn('SALVATAGGIO', f'{name} non scritto in locale: {exc}')
    with _pending_lock:
        _pending[name] = (text.encode('utf-8'), message)
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_flush, daemon=True)
            _worker.start()


def _flush():
    import team_settings
    while True:
        with _pending_lock:
            if not _pending:
                return
            name, (raw, message) = next(iter(_pending.items()))
            del _pending[name]
        try:
            ok, why = team_settings._commit({f'{DIRNAME}/{name}': raw}, message, os.environ)
        except Exception as exc:  # noqa: BLE001 - resta la copia locale per questa sessione
            ok, why = False, f'{type(exc).__name__}: {exc}'
        if not ok:
            log.warn('SALVATAGGIO', f'{message}: non salvato nel repository ({why})')


def wait(timeout=20):
    """Alla chiusura: aspetta che gli ultimi salvataggi arrivino nel repository."""
    worker = _worker
    if worker is not None and worker.is_alive():
        worker.join(timeout)
