"""Log di ImageGen, ordinati come quelli di LiveScore:

    [21:08:45] INFO   AVVIO      | Loghi incorporati: 148/148

Una riga per evento: ora italiana, livello, area (colonne fisse) e un messaggio in
italiano. Alla fine della sessione un riepilogo (grafiche inviate, avvisi) va nel
"Summary" del run su GitHub.
"""
import os
import re
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

ITALY_TZ = ZoneInfo('Europe/Rome')
_SECRET_ENV = ('MANUAL_GRAPHICS_TELEGRAM_TOKEN', 'IMAGEGEN_GH_PAT', 'IMAGEGEN_ASSETS_PAT', 'GH_TOKEN')
_BOT_TOKEN_RE = re.compile(r'(?<!\d)\d{6,}:[A-Za-z0-9_-]{30,}')

# Nome di ogni grafica come nella Mini App.
KIND_NAMES = {
    'goal': 'Gol', 'saved': 'Parata', 'stats': 'Statistiche',
    'kick': 'Kick Off', 'half': 'Half Time', 'second': '2nd Half', 'end_of_90': 'End Of 90’', 'full': 'Full Time',
    'md': 'Matchday', 'pxi': 'Probabile XI', 'squad': 'Squad List', 'xi': 'Starting XI',
    'cal': 'Calendario', 'table': 'Classifica', 'jr': 'Post', 'igbn': 'Storia IG',
}

_lock = threading.Lock()
_sent = []        # (ora, grafica, dettagli) inviate in questa sessione
_warnings = 0


def now():
    return datetime.now(ITALY_TZ).strftime('%H:%M:%S')


def kind_name(kind):
    return KIND_NAMES.get(str(kind), str(kind))


def graphic_name(data):
    """Nome della grafica per il log: "Half Time", "Italia · Half Time"..."""
    name = kind_name(data.get('kind'))
    return f'Italia · {name}' if data.get('team') == 'italy' else name


def redact(message):
    """Niente token o segreti nel log (i log di Actions si possono leggere)."""
    for name in _SECRET_ENV:
        secret = os.getenv(name)
        if secret and len(secret) >= 8:
            message = message.replace(secret, '***')
    return _BOT_TOKEN_RE.sub('***', message)


def line(level, area, message):
    global _warnings
    level = level.upper()
    if level in ('WARN', 'ERROR'):
        _warnings += 1
    text = redact(str(message)).replace('\n', ' · ')
    with _lock:
        print(f'[{now()}] {level:<6} {area.upper():<10} | {text}', flush=True)


def info(area, message):
    line('INFO', area, message)


def warn(area, message):
    line('WARN', area, message)


def error(area, message):
    line('ERROR', area, message)


def exc_text(exc):
    """Errore breve: tipo e messaggio."""
    return f'{type(exc).__name__}: {exc}'


def kb(size):
    return f'{size / 1024 / 1024:.1f} MB' if size >= 1024 * 1024 else f'{size // 1024} KB'


def sent(name, details=''):
    """Grafica inviata su Telegram: finisce anche nel riepilogo del run."""
    with _lock:
        _sent.append((now(), name, details))


def write_summary(started, ended, extra=None):
    """Riepilogo della sessione nel "Summary" del run GitHub (se disponibile)."""
    path = os.getenv('GITHUB_STEP_SUMMARY')
    if not path:
        return
    rows = [f'### ImageGen · sessione {started}–{ended}', '']
    if _sent:
        rows += ['| Ora | Grafica | Dettagli |', '| --- | --- | --- |']
        rows += [f'| {t} | {name} | {details} |' for t, name, details in _sent]
    else:
        rows.append('Nessuna grafica inviata.')
    rows.append('')
    rows.append(f'Avvisi nel log: **{_warnings}**' if _warnings else 'Nessun avviso nel log.')
    for item in extra or ():
        rows.append(f'- {item}')
    try:
        with open(path, 'a', encoding='utf-8') as out:
            out.write('\n'.join(rows) + '\n')
    except OSError:
        pass
