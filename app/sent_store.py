"""Dati della Mini App che restano tra una sessione e l'altra, nel repo degli asset:

- imagegen/history.json   "Ultimi invii": nome, dettagli e riferimento Telegram (file_id)
                          di ogni grafica inviata. Le immagini restano su Telegram: con il
                          file_id si rimandano e si riscaricano anche dopo la sessione.
- imagegen/ig_phrases.json Storia IG: frasi pronte.

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


def load_phrases():
    """Frasi pronte: [{'text', 'color'}] (le prime salvate erano solo testo: colore di base)."""
    out = []
    for item in _read(PHRASES, []):
        row = item if isinstance(item, dict) else {'text': item}
        text = clean_phrase(row.get('text'))
        if text:
            out.append({'text': text, 'color': str(row.get('color') or 'black')})
    return out[:PHRASES_KEEP]


def save_history(entries):
    keep = ('id', 'name', 'player', 'minute', 'score', 'opponent', 'note', 'kind', 'at', 'file_id', 'thumb_id')
    rows = [{k: e.get(k) for k in keep} for e in entries if e.get('file_id')][:HISTORY_KEEP]
    _save(HISTORY, rows, 'ImageGen: ultimi invii')


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
