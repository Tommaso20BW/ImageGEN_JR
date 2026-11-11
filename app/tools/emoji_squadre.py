"""Controllo dei pack (a ogni nuova stagione FCLogo) di emoji delle squadre (workflow "Emoji squadre").

Lavora sulla cartella degli asset (repo LiveScore_Assets_JR):
  team_emoji/auto.json       squadra -> emoji scelta in automatico (+ id di ogni pack all'ultima lettura)
  team_emoji/packs.json      emoji di ogni pack (ordine, simbolo di riserva) per Impostazioni
  team_emoji/packs/<pack>.webp  miniature del pack in griglia (CELL px, COLS per riga)
  team_overrides/emoji.json  scelte fatte a mano in Impostazioni › Emoji squadre (vincono sempre)

Regole:
- Emoji tolta da un pack: si cerca la sostituta fra le emoji nuove (o, se non ce ne sono, fra
  tutte). Vale solo con compatibilità >= 90%, confrontando la nuova emoji con quella vecchia
  (miniatura salvata) e con il logo FCLogo della squadra. Sotto il 90% la squadra resta senza
  emoji (nel Matchday 🆚) e il riepilogo lo dice.
- Squadra nuova nel catalogo: cerca fra tutte le emoji (compatibilità >= 90% e reciproca:
  l'emoji somiglia più a quella squadra che a ogni altra).
- Emoji nuova nel tuo pack (JR Pack) che somiglia >= 90% a una squadra: diventa la sua.
- Le scelte "manual" non cambiano, finché la loro emoji resta nel pack.
Il riepilogo lo manda il bot di ImageGEN su Telegram (solo se c'è qualcosa di nuovo).

Uso: python emoji_squadre.py <cartella asset> <fclogo_manifest.json> [pack in più ...]
Variabili: TOKEN (bot), CHAT_ID (riepilogo; se manca lo stampa e basta).
"""
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

OWN_PACK = 'AroundJuventus'
GENERIC_PACKS = ('UEFA', 'European')     # pack con squadre di tutti i paesi: ultima scelta
MIN_MATCH = 0.90                         # compatibilità minima per un abbinamento automatico
SIZE = 32
CELL, COLS = 64, 12

# Nomi dei pack in Impostazioni (in ordine).
PACK_NAMES = {
    'AroundJuventus': 'JR Pack', 'ItalianFootballEmoji': 'Italia', 'EnglishFootball_Emoji': 'Inghilterra',
    'EnglishFootball2Emoji': 'Inghilterra 2', 'SpanishFootballEmoji': 'Spagna', 'GermanFootballEmoji': 'Germania',
    'FrenchFootballEmoji': 'Francia', 'DutchFootballEmoji': 'Olanda', 'PortugueseFootballEmoji': 'Portogallo',
    'BelgianFootballEmoji': 'Belgio', 'TurkishFootballEmoji': 'Turchia', 'ScottishFootballEmoji': 'Scozia',
    'GreekFootballEmoji': 'Grecia', 'AustrianFootballEmoji': 'Austria', 'SwissFootballEmoji': 'Svizzera',
    'CzechFootballEmoji': 'Rep. Ceca', 'NorwegianFootballEmoji': 'Norvegia', 'DanishFootballEmoji': 'Danimarca',
    'PolishFootballEmoji': 'Polonia', 'SwedishFootballEmoji': 'Svezia', 'CroatianFootballEmoji': 'Croazia',
    'SerbianFootballEmoji': 'Serbia', 'UkrainianFootballEmoji': 'Ucraina', 'HungarianFootballEmoji': 'Ungheria',
    'RomanianFootballEmoji': 'Romania', 'SlovakFootballEmoji': 'Slovacchia', 'SlovenianFootballEmoji': 'Slovenia',
    'BulgarianFootballEmoji': 'Bulgaria', 'CyprusLogos': 'Cipro', 'IsraeliFootballEmoji': 'Israele',
    'AzerbaijaniFootballEmoji': 'Azerbaigian', 'KazakhstaniFootballEmoji': 'Kazakistan',
    'EuropeanFootballEmoji': 'Europa', 'UEFAChampionsLeagueEmoji': 'Champions League',
    'UEFAEuropeLeagueEmoji': 'Europa League', 'UEFAConferenceLeagueEmoji': 'Conference League',
}


def pack_name(pack):
    return PACK_NAMES.get(pack, pack)


# ---------- somiglianza fra immagini ----------

def feature(image):
    """Immagine (bytes o PIL) -> (colori, sagoma, proporzioni) su SIZE x SIZE, ritagliata sul disegno."""
    if isinstance(image, (bytes, bytearray)):
        image = Image.open(io.BytesIO(image))
    a = np.array(image.convert('RGBA'))
    if a[..., 3].min() == 255:      # fondo bianco pieno (anteprime FCLogo): trattalo come trasparente
        a[..., 3] = np.where((a[..., :3] > 245).all(-1), 0, 255)
    ys, xs = np.nonzero(a[..., 3] > 40)
    if not len(xs):
        return None
    im = Image.fromarray(a).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    w, h = im.size
    side = max(w, h)
    square = Image.new('RGBA', (side, side))
    square.paste(im, ((side - w) // 2, (side - h) // 2))
    px = np.array(square.resize((SIZE, SIZE), Image.LANCZOS)).astype(float) / 255
    alpha = px[..., 3:]
    return px[..., :3] * alpha + 0.5 * (1 - alpha), alpha[..., 0], w / h


def similarity(f, g):
    """Compatibilità 0..1 (1 = identiche). Colori + sagoma + proporzioni; 0,90 = stessa squadra."""
    if f is None or g is None:
        return 0.0
    colour = np.abs(f[0] - g[0]).mean()
    iou = np.minimum(f[1], g[1]).sum() / max(np.maximum(f[1], g[1]).sum(), 1e-9)
    distance = colour * 2 + (1 - iou) + abs(np.log(f[2] / g[2]))
    return float(max(0.0, 1 - distance / 2.5))


SUGGEST = 8          # emoji consigliate per squadra (Impostazioni › squadra › Emoji)


def suggestions(logo, pool):
    """Le emoji più somiglianti al logo: [{'id', 'score'}], la migliore prima."""
    if logo is None:
        return []
    scored = sorted(((similarity(logo, f), i) for i, f in pool if f is not None), reverse=True)
    return [{'id': i, 'score': round(s, 3)} for s, i in scored[:SUGGEST] if s >= 0.5]


def pick_rank(pack):
    return 0 if pack == OWN_PACK else 2 if pack.startswith(GENERIC_PACKS) else 1


# ---------- miniature dei pack ----------

def build_sprite(images):
    """Miniature (bytes, nell'ordine del pack) -> griglia WebP, CELL px a cella, COLS per riga."""
    rows = max(1, (len(images) + COLS - 1) // COLS)
    sheet = Image.new('RGBA', (COLS * CELL, rows * CELL))
    for n, raw in enumerate(images):
        if not raw:
            continue
        try:
            im = Image.open(io.BytesIO(raw)).convert('RGBA')
        except Exception:
            continue
        im.thumbnail((CELL, CELL), Image.LANCZOS)
        x, y = (n % COLS) * CELL, (n // COLS) * CELL
        sheet.paste(im, (x + (CELL - im.width) // 2, y + (CELL - im.height) // 2), im)
    out = io.BytesIO()
    sheet.save(out, 'WEBP', quality=82, method=6)
    return out.getvalue()


def sprite_cell(sprite, pos):
    """Miniatura n. pos (ordine nel pack) ritagliata dalla griglia (PIL Image)."""
    x, y = (pos % COLS) * CELL, (pos // COLS) * CELL
    return sprite.crop((x, y, x + CELL, y + CELL))


# ---------- abbinamenti ----------

def team_key(team):
    return str(team.get('slug') or team.get('key') or '')


def update(state, teams, packs, team_feature, emoji_feature, old_feature=lambda i: None, overrides=None):
    """Aggiorna state (auto.json) e overrides (scelte a mano). Torna le righe del riepilogo.

    teams: squadre ({slug|key, name, aliases}). packs: {pack: [{'id', 'emoji', 'index'}, ...]}.
    team_feature(team), emoji_feature(id), old_feature(id della emoji tolta): immagini pronte o None."""
    overrides = {} if overrides is None else overrides
    known = {i for ids in state.get('packs', {}).values() for i in ids}
    rows = {e['id']: {**e, 'pack': pack} for pack, items in packs.items() for e in items if e.get('id')}
    new_ids = [i for i in rows if i not in known]
    mapped = state.setdefault('teams', {})
    report = []
    if new_ids:
        report.append(f'🆕 {len(new_ids)} emoji nuove nei pack')

    cache, tcache = {}, {}

    def ef(i):
        if i not in cache:
            cache[i] = emoji_feature(i)
        return cache[i]

    def tf(team):
        k = team_key(team)
        if k not in tcache:
            tcache[k] = team_feature(team)
        return tcache[k]

    def best_team(i):
        best = (0.0, None)
        for t in teams:
            s = similarity(ef(i), tf(t))
            if s > best[0]:
                best = (s, team_key(t))
        return best

    def choose(team, pool, old=None):
        """Emoji migliore per la squadra: (id, compatibilità) o (None, migliore trovata)."""
        logo = tf(team)
        scored = []
        for i in pool:
            f = ef(i)
            by_old, by_logo = similarity(old, f), similarity(logo, f)
            scored.append((max(by_old, by_logo), by_old, i))
        if not scored:
            return None, 0.0
        top = max(s[0] for s in scored)
        if top < MIN_MATCH:
            return None, top
        near = sorted((s for s in scored if s[0] >= top - 0.02), key=lambda s: (pick_rank(rows[s[2]]['pack']), -s[0]))
        for score, by_old, i in near:
            if by_old >= MIN_MATCH or best_team(i)[1] == team_key(team):
                return i, score
        return None, top

    def entry(team, i, manual=False):
        e = rows[i]
        return {'name': team['name'], 'aliases': team.get('aliases') or [], 'id': i, 'emoji': e.get('emoji') or '',
                'pack': e['pack'], 'index': e.get('index'), **({'manual': True} if manual else {})}

    def where(i):
        return f"{pack_name(rows[i]['pack'])} n. {rows[i].get('index')}"

    by_key = {team_key(t): t for t in teams}

    # 1. Scelte a mano con l'emoji sparita dal pack: si cerca la sostituta (>= 90%), sennò si tolgono.
    for key, row in list(overrides.items()):
        if not row.get('id') or row['id'] in rows:
            continue
        team = by_key.get(key) or {'key': key, 'name': row.get('name') or key}
        i, score = choose(team, new_ids or list(rows), old_feature(row['id']))
        if i:
            overrides[key] = {'id': i, 'emoji': rows[i].get('emoji') or '', 'pack': rows[i]['pack'],
                              'index': rows[i].get('index')}
            report.append(f"🔁 {team['name']}: emoji tolta dal pack, scelta tua sostituita con {where(i)} ({score:.0%})")
        else:
            overrides.pop(key)
            report.append(f"⚠️ {team['name']}: la tua emoji è sparita dal pack e nessuna nuova è compatibile "
                          f"almeno al 90% (migliore {score:.0%}): torna quella automatica")

    # 2. Squadre del catalogo: emoji sparita o squadra nuova.
    for team in teams:
        key = team_key(team)
        row = mapped.get(key)
        if row and row.get('id') and row['id'] not in rows:
            i, score = choose(team, new_ids or list(rows), old_feature(row['id']))
            if i:
                mapped[key] = entry(team, i, manual=bool(row.get('manual')))
                report.append(f"🔁 {team['name']}: emoji tolta da {pack_name(row.get('pack'))}, ora {where(i)} ({score:.0%})")
            else:
                mapped[key] = {'name': team['name'], 'aliases': team.get('aliases') or [], 'id': None}
                report.append(f"⚠️ {team['name']}: emoji tolta da {pack_name(row.get('pack'))}, nessuna nuova compatibile "
                              f"almeno al 90% (migliore {score:.0%}): nel Matchday 🆚")
        elif not row:
            i, score = choose(team, list(rows))
            if i:
                mapped[key] = entry(team, i)
                report.append(f"✅ {team['name']} (nuova): {where(i)} ({score:.0%})")
            else:
                mapped[key] = {'name': team['name'], 'aliases': team.get('aliases') or [], 'id': None}
                report.append(f"⚠️ {team['name']} (nuova): nessuna emoji compatibile almeno al 90%, nel Matchday 🆚")
        elif not row.get('id') and new_ids:
            i, score = choose(team, new_ids)
            if i:
                mapped[key] = entry(team, i)
                report.append(f"✅ {team['name']}: {where(i)} ({score:.0%})")

    # 3. Emoji nuove nel JR Pack: prendono il posto di quelle dei pack esteri.
    for i in new_ids:
        if rows[i]['pack'] != OWN_PACK:
            continue
        score, key = best_team(i)
        row = mapped.get(key) or {}
        if key is None or score < MIN_MATCH or row.get('manual') or row.get('pack') == OWN_PACK:
            continue
        if choose(by_key[key], [i, *([row['id']] if row.get('id') else [])])[0] == i:
            mapped[key] = entry(by_key[key], i)
            report.append(f"✅ {by_key[key]['name']}: ora usa la tua emoji ({where(i)}, {score:.0%})")

    # 4. Consigliate: rifatte se i pack sono cambiati o se mancano.
    changed = bool(new_ids) or set(known) != set(rows)
    for team in teams:
        row = mapped.get(team_key(team))
        if row is None or (not changed and 'suggest' in row):
            continue
        logo = tf(team)
        row['suggest'] = suggestions(logo, [(i, ef(i)) for i in rows]) if logo is not None else []

    state['packs'] = {pack: [e['id'] for e in items if e.get('id')] for pack, items in packs.items()}
    return report


# ---------- file nella cartella degli asset ----------

def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def pack_index(packs):
    """packs.json: per ogni pack nome italiano, griglia e emoji in ordine."""
    return {pack: {'name': pack_name(pack), 'cell': CELL, 'cols': COLS, 'file': f'packs/{pack}.webp',
                   'items': [{'id': e['id'], 'emoji': e.get('emoji') or '', 'index': e.get('index')} for e in items]}
            for pack, items in packs.items()}


def catalog_teams(manifest_path, assets):
    """Squadre del catalogo FCLogo + quelle aggiunte da te (team_overrides, chiave new:...)."""
    teams = [{'slug': t['slug'], 'name': t['name'], 'aliases': t.get('aliases') or [], 'preview_url': t.get('preview_url')}
             for t in read_json(manifest_path, {}).get('teams', [])]
    custom = read_json(Path(assets) / 'team_overrides' / 'overrides.json', {}).get('teams', {})
    teams += [{'key': k, 'name': v.get('name') or k, 'aliases': v.get('aliases') or []}
              for k, v in custom.items() if k.startswith('new:')]
    return teams


# ---------- Telegram ----------

class Bot:
    def __init__(self, token):
        import requests
        self.http = requests.Session()
        self.api = f'https://api.telegram.org/bot{token}/'
        self.files = f'https://api.telegram.org/file/bot{token}/'

    def call(self, method, **params):
        for _ in range(6):
            r = self.http.post(self.api + method, data=params, timeout=30)
            if r.status_code == 429:
                time.sleep(int(r.json().get('parameters', {}).get('retry_after', 3)) + 1)
                continue
            body = r.json()
            if not body.get('ok'):
                raise RuntimeError(f"{method}: {body.get('description')}")
            return body['result']
        raise RuntimeError(f'{method}: troppe richieste')

    def download(self, file_id):
        path = self.call('getFile', file_id=file_id)['file_path']
        return self.http.get(self.files + path, timeout=30).content


def season_of(manifest_path):
    return str(read_json(Path(manifest_path), {}).get('season') or '')


def main(assets, manifest_path, extra_packs=(), force=True):
    """force=False: controlla solo se il catalogo FCLogo è passato a una stagione nuova."""
    import requests
    assets = Path(assets)
    base = assets / 'team_emoji'
    state = read_json(base / 'auto.json', {'packs': {}, 'teams': {}})
    season = season_of(manifest_path)
    if not force and not extra_packs and season and state.get('season') == season:
        print(f'Stagione {season} già controllata: niente da fare.')
        return
    index = read_json(base / 'packs.json', {})
    overrides_path = assets / 'team_overrides' / 'emoji.json'
    overrides = read_json(overrides_path, {}).get('teams', {})
    teams = catalog_teams(manifest_path, assets)
    bot = Bot(os.environ['TOKEN'])

    packs, thumbs, errors = {}, {}, []
    names = [*state.get('packs', {}), *(p for p in extra_packs if p not in state.get('packs', {}))]
    for name in names:
        try:
            info = bot.call('getStickerSet', name=name)
        except Exception as exc:
            errors.append(f'❌ Pack {pack_name(name)} non letto: {exc}')
            if name in index:            # pack non letto: resta com'era
                packs[name] = index[name]['items']
            continue
        packs[name] = []
        for n, st in enumerate(info['stickers']):
            i = st.get('custom_emoji_id')
            if i:
                packs[name].append({'id': i, 'emoji': st.get('emoji') or '', 'index': n})
                thumbs[i] = (st.get('thumbnail') or {}).get('file_id') or st['file_id']
        print(name, len(packs[name]), 'emoji', flush=True)

    downloaded = {}

    def raw(i):
        if i not in downloaded:
            try:
                downloaded[i] = bot.download(thumbs[i]) if i in thumbs else None
            except Exception:
                downloaded[i] = None
        return downloaded[i]

    def emoji_feature(i):
        data = raw(i)
        return feature(data) if data else None

    old_where = {e['id']: (pack, pos) for pack, info in index.items() for pos, e in enumerate(info.get('items', []))}
    sprites = {}

    def old_feature(i):
        if i not in old_where:
            return None
        pack, pos = old_where[i]
        if pack not in sprites:
            try:
                sprites[pack] = Image.open(base / index[pack]['file']).convert('RGBA')
            except Exception:
                sprites[pack] = None
        return feature(sprite_cell(sprites[pack], pos)) if sprites[pack] else None

    def team_feature(team):
        try:
            url = team.get('preview_url')
            return feature(requests.get(url, timeout=20).content) if url else None
        except Exception:
            return None

    report = errors + update(state, teams, packs, team_feature, emoji_feature, old_feature, overrides)

    # Miniature: rifatte solo per i pack cambiati (o senza griglia).
    for pack, items in packs.items():
        old_ids = [e['id'] for e in index.get(pack, {}).get('items', [])]
        if old_ids == [e['id'] for e in items] and (base / f'packs/{pack}.webp').is_file():
            continue
        if not all(e['id'] in thumbs for e in items):
            continue
        (base / 'packs').mkdir(parents=True, exist_ok=True)
        (base / f'packs/{pack}.webp').write_bytes(build_sprite([raw(e['id']) for e in items]))
    for pack in set(index) - set(packs):
        (base / f'packs/{pack}.webp').unlink(missing_ok=True)

    if season:
        state['season'] = season
    write_json(base / 'auto.json', state)
    write_json(base / 'packs.json', pack_index(packs))
    if overrides_path.is_file() or overrides:
        write_json(overrides_path, {'version': 1, 'teams': overrides})

    text = '\n'.join([f'Emoji squadre: controllo dei pack (stagione {season})' if season else 'Emoji squadre: controllo dei pack', '', *report]) if report else ''
    print(text or 'Nessuna novità nei pack.')
    if text and os.environ.get('CHAT_ID'):
        bot.call('sendMessage', chat_id=os.environ['CHAT_ID'], text=text, disable_web_page_preview='true')


if __name__ == '__main__':
    args = sys.argv[1:]
    new_season_only = '--nuova-stagione' in args
    args = [a for a in args if a != '--nuova-stagione']
    main(args[0], args[1], args[2:], force=not new_season_only)
