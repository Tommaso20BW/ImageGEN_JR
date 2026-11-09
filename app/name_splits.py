"""Nome e cognome dei convocati ricordati nel repository (data/name_splits.json).

Per ogni nome scritto (chiave: name_key, es. "pape matar sarr") quante parole sono il
nome, in bianco sulla grafica; le altre sono il cognome, in oro (es. 1 -> PAPE | MATAR SARR).
La Mini App lo chiede quando il nome ha più di due parole e non è ancora salvato; quando la
grafica viene inviata le scelte nuove o cambiate si salvano con un commit, come i numeri
di maglia (shirt_numbers.save_json).
"""
import json
import re
import unicodedata
from pathlib import Path

PATH = 'app/data/name_splits.json'                        # percorso nella repository
LOCAL = Path(__file__).parent / 'data' / 'name_splits.json'


def name_key(name):
    """"Pape Matar Sarr" -> "pape matar sarr" (minuscolo, senza accenti né segni)."""
    text = str(name or '').lower()
    for a, b in (('ı', 'i'), ('ł', 'l'), ('đ', 'd'), ('ð', 'd'), ('ø', 'o'), ('ß', 'ss')):
        text = text.replace(a, b)
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def load():
    try:
        data = json.loads(LOCAL.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {k: int(v) for k, v in data.items() if not k.startswith('_') and str(v).isdigit()}


def first_words(name, chosen=None, known=None):
    """Quante parole di `name` sono il nome: la scelta fatta (`chosen`), quella salvata,
    altrimenti 1 (la prima parola). Sempre almeno una parola di cognome."""
    words = len(str(name or '').split())
    if words < 2:
        return 0
    for value in (chosen, (load() if known is None else known).get(name_key(name))):
        if isinstance(value, int) and 1 <= value <= words - 1:
            return value
    return 1


def changes(players, known):
    """{chiave: parole del nome} delle scelte nuove o diverse da quelle salvate.
    players: [(nome scritto, parole del nome scelte o None)]."""
    out = {}
    for name, first in players:
        if isinstance(first, int) and len(str(name).split()) > 1 and known.get(name_key(name)) != first:
            out[name_key(name)] = first
    return out


def save(updates, env=None, session=None):
    from shirt_numbers import save_json
    return save_json(PATH, LOCAL, updates, 'Nome e cognome convocati', env=env, session=session)
