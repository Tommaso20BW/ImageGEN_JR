"""Emoji personalizzate dei tesserati (le facce del JR Pack), per gli auguri di compleanno.

Di base quelle già usate sul canale (DEFAULTS, per cognome); se un giocatore della rosa non ce l'ha,
la mini app avvisa e la si sceglie a mano dal pack: la scelta resta per sempre in
team_overrides/player_emoji.json (repo degli asset, nome del giocatore -> emoji) e si può cambiare.
"""
import json
import os
import threading
import unicodedata
from pathlib import Path

import team_emoji

PACK = 'AroundJuventus'                      # JR Pack
MANUAL = 'team_overrides/player_emoji.json'
_lock = threading.Lock()

# Facce del JR Pack già usate sul canale (cognome senza accenti -> (riserva, id)).
DEFAULTS = {
    'spalletti': ('👨‍🦲', '5785405760431207322'), 'conceicao': ('🇵🇹', '5789811056847102509'),
    'yildiz': ('🇹🇷', '5789644098583404844'), 'gonzalez': ('🇦🇷', '5807952577798611024'),
    'alajbegovic': ('🇧🇦', '5789842410108361950'), 'bremer': ('🇧🇷', '5789828275370992311'),
    'boga': ('🇨🇮', '5789597223310335831'), 'woltemade': ('🇩🇪', '5816639114795033093'),
    'kalulu': ('🇫🇷', '5789930585786949166'), 'kolo muani': ('🇫🇷', '5789850871193935307'),
    'vicario': ('🇮🇹', '5789445537950344432'), 'cambiaso': ('🇮🇹', '5791922170712039419'),
    'ekhator': ('🇮🇹', '5789870589388791439'), 'gatti': ('🇮🇹', '5789729856195402778'),
    'koopmeiners': ('🇳🇱', '5789588886778814092'), 'sarr': ('🇸🇳', '5816763346724069174'),
    'mckennie': ('🇺🇸', '5789765362690039962'), 'zhegrova': ('🇽🇰', '5789535831047806543'),
    'celik': ('🇹🇷', '5789433847049363036'), 'cabal': ('🇨🇴', '5789717237581491671'),
    'pinsoglio': ('🇮🇹', '5789708535977746989'), 'milik': ('🇵🇱', '5789440070456974878'),
    'thuram': ('🇫🇷', '5789690608784253534'), 'douglas luiz': ('🇧🇷', '5789538682906091775'),
    'kelly': ('\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F', '5789901070771691820'),
}


def _plain(text):
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def manual_rows(assets=None):
    return team_emoji._read(Path(assets or team_emoji._assets()) / MANUAL, {}).get('players') or {}


def _default(name):
    padded = f' {_plain(name)} '
    return next(((eid, fb) for key, (fb, eid) in DEFAULTS.items() if f' {key} ' in padded), None)


def find(name, assets=None):
    """(id, simbolo di riserva) della faccia del giocatore, oppure None."""
    try:
        row = manual_rows(assets).get(_plain(name))
    except Exception:  # noqa: BLE001
        row = None
    if row and row.get('id'):
        return str(row['id']), row.get('emoji') or '⚽'
    return _default(name)


def detail(name, assets=None):
    """Emoji in uso per il giocatore (miniatura dal pack), se è scelta a mano, e il pack da cui sceglierla."""
    assets = Path(assets or team_emoji._assets())
    info = team_emoji.packs_info(assets)
    hit = find(name, assets)
    current = None
    if hit:
        item = next((e for e in (info.get(PACK) or {}).get('items', []) if e.get('id') == hit[0]), None)
        if item:
            current = {'pack': PACK, 'index': item.get('index'),
                       'thumb': team_emoji._thumb(assets, info, PACK, item.get('index'))}
        else:
            current = {'pack': '', 'index': None, 'thumb': '', 'emoji': hit[1]}
    return {'name': str(name or ''), 'current': current, 'manual': _plain(name) in manual_rows(assets), 'pack': PACK}


def save(request, assets=None, env=None):
    """{name, pack, index} = faccia scelta; {name, reset: true} = torna a quella di base.
    Salva in team_overrides/player_emoji.json (copia locale subito, poi un commit nel repo degli asset)."""
    import team_settings
    env = os.environ if env is None else env
    assets = Path(assets or team_emoji._assets())
    name = ' '.join(str(request.get('name') or '').split())
    if not name:
        raise ValueError('Giocatore mancante.')
    with _lock:
        rows = dict(manual_rows(assets))
        if request.get('reset'):
            rows.pop(_plain(name), None)
        else:
            pack, index = str(request.get('pack') or ''), request.get('index')
            item = next((e for e in (team_emoji.packs_info(assets).get(pack) or {}).get('items', [])
                         if e.get('index') == index), None)
            if not item:
                raise ValueError('Emoji non trovata nel pack.')
            rows[_plain(name)] = {'name': name, 'id': item['id'], 'emoji': item.get('emoji') or '',
                                  'pack': pack, 'index': index}
        text = json.dumps({'version': 1, 'players': dict(sorted(rows.items()))}, ensure_ascii=False, indent=1) + '\n'
        path = assets / MANUAL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        ok, why = team_settings._commit({MANUAL: text.encode('utf-8')}, f'Emoji giocatori: {name} (mini app ImageGen)', env)
    return {'remote': ok, 'warning': '' if ok else why, **detail(name, assets)}
