"""Letture da Diretta.it più veloci.

- `shared`: richieste uguali nello stesso momento (post 3:4 e storia IG) leggono la pagina
  una volta sola: la seconda aspetta la prima e ne riusa il risultato per pochi secondi.
- `disk_get` / `disk_put`: cose che cambiano di rado (stemmi grandi, font, Coppa Italia finita
  o no) restano su disco anche dopo un riavvio del servizio.
"""
import copy
import hashlib
import json
import tempfile
import threading
import time
from pathlib import Path

CACHE_DIR = Path(tempfile.gettempdir()) / 'imagegen_cache'

_locks: dict = {}
_locks_guard = threading.Lock()
_results: dict = {}


def shared(key, ttl, func):
    """func() una volta per chiave: chi arriva mentre è in corso aspetta e riusa il risultato
    (copia), anche per i ttl secondi dopo. Gli errori non si tengono: il prossimo riprova."""
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        hit = _results.get(key)
        if hit and time.time() - hit[0] <= ttl:
            return copy.deepcopy(hit[1])
        value = func()
        _results[key] = (time.time(), value)
        return copy.deepcopy(value)


def forget():
    """Solo per i test: nessun risultato condiviso."""
    _results.clear()


def _path(name, suffix):
    safe = hashlib.sha256(name.encode('utf-8')).hexdigest()[:32]
    return CACHE_DIR / f'{safe}{suffix}'


def disk_get(name, max_age, binary=False):
    """Contenuto salvato con disk_put se più giovane di max_age secondi, altrimenti None."""
    path = _path(name, '.bin' if binary else '.json')
    try:
        if time.time() - path.stat().st_mtime > max_age:
            return None
        return path.read_bytes() if binary else json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def disk_put(name, value, binary=False):
    path = _path(name, '.bin' if binary else '.json')
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f'.{threading.get_ident()}.tmp')
        if binary:
            tmp.write_bytes(value)
        else:
            tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        tmp.replace(path)
    except OSError:
        pass            # senza disco si va avanti come prima, solo più lenti
