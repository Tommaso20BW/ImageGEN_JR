"""CONVOCATI IN NAZIONALE: riepilogo dei bianconeri chiamati dalle nazionali (3:4, nero e oro).

Per ogni giocatore la bandiera della nazionale dietro la sua foto scontornata (stessa foto delle
grafiche, posa a braccia conserte), il nome e la nazione sotto. Font degli asset (Poppins); bandiere flag-icons (MIT) nel repo degli asset, cartella flags/; logo JR in alto a
destra come classifica e tabellone.
"""
import functools
import json
import re
import unicodedata
from pathlib import Path

from graphics.common import asset_dir, data_uri, render_html

NATIONS_FILE = Path(__file__).resolve().parent.parent / 'data' / 'convocati' / 'nazioni.json'
MAX_PLAYERS = 20
TITLE_DEFAULT = 'Convocati in nazionale'
KICKER_DEFAULT = 'I bianconeri'

_nations = None


def _key(text):
    raw = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', raw.lower())


def nations():
    """{nome normalizzato: (codice bandiera, nome da scrivere)}; il nome da scrivere è il primo dell'elenco."""
    global _nations
    if _nations is None:
        data = json.loads(NATIONS_FILE.read_text(encoding='utf-8'))
        _nations = {}
        for code, names in data.items():
            if code.startswith('_'):
                continue
            for name in names:
                _nations[_key(name)] = (code, names[0])
    return _nations


def nation(name):
    """('it', 'Italia') per un nome di nazione scritto in qualunque variante; ValueError se sconosciuta."""
    hit = nations().get(_key(name))
    if not hit:
        raise ValueError(f'Nazione non riconosciuta: «{name}». Scrivila in italiano (es. Olanda, Brasile).')
    return hit


def nation_list():
    """Per la Mini App: [{code, name}] in ordine alfabetico (un nome per nazione)."""
    seen = {}
    for code, name in nations().values():
        seen.setdefault(code, name)
    return sorted(({'code': c, 'name': n} for c, n in seen.items()), key=lambda r: _key(r['name']))


KIT_ORDER = ('', 'keeper_blue', 'keeper_green', 'keeper_orange')   # sempre la maglia home (portieri: la loro)


PHOTO_W = 1.6       # larghezza della foto in pannelli: stessa scala per tutti (le foto ufficiali
                    # sono scattate tutte uguali, quindi i giocatori restano in proporzione)
HEAD_TOP = -.14     # dove comincia la testa (capelli): sopra il pannello, così la testa esce
SLANT = .14         # inclinazione del pannello (rientro dei lati, in pannelli)
PANEL_H = .98       # altezza del pannello in larghezze


@functools.lru_cache(maxsize=256)
def head_box(path):
    """(top, centro x, larghezza) della testa in frazioni della foto quadrata scontornata:
    prima riga piena (capelli) e righe della testa fino a ~1/8 della foto più sotto."""
    from PIL import Image
    alpha = Image.open(path).getchannel('A')
    w, h = alpha.size
    solid = alpha.point(lambda v: 255 if v > 140 else 0)
    box = solid.getbbox()
    if not box:
        return 0.0, .5, .3
    top = box[1]
    head = solid.crop((0, top, w, min(h, top + int(h * .13)))).getbbox()
    x0, x1 = (head[0], head[2]) if head else (box[0], box[2])
    return top / h, (x0 + x1) / 2 / w, max(.05, (x1 - x0) / w)


def _photo(player):
    """Percorso della foto: prima quella ufficiale della Lega Serie A (players_lega/),
    altrimenti la nostra foto a braccia conserte."""
    from foto_lega import photo_path
    official = photo_path(asset_dir(), player.slug)
    if official:
        return official
    folder = asset_dir() / 'players' / player.slug
    path = None
    for kit in KIT_ORDER:
        tag = f'_{kit}' if kit else ''
        candidate = folder / f'{player.slug}{tag}_pose_01_arms_crossed.png'
        if candidate.is_file():
            path = candidate
            break
    if path is None:
        found = sorted(folder.glob('*pose_01_arms_crossed.png'))
        if not found:
            raise ValueError(f'Manca la foto di {player.name}.')
        path = found[0]
    return path


def _esc(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


def _plain(text):
    return unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()


def _grid(n):
    """Colonne per n giocatori: righe piene il più possibile, ultima riga centrata."""
    if n <= 4:
        return n
    if n <= 6 or n == 9:
        return 3
    if n <= 12 or n == 16:
        return 4
    return 5


def _split(text):
    """('NICO', 'GONZALEZ'): nome in bianco, il resto (cognome) in oro."""
    words = _plain(text).upper().split()
    return (words[0], ' '.join(words[1:])) if len(words) > 1 else ('', words[0] if words else '')


def _logo():
    """Logo JR ritagliato (data uri) e sua posizione nella pagina 1080x1440: si colora con la
    stessa texture oro delle scritte, così logo e testi hanno lo stesso oro."""
    import base64
    import io
    from PIL import Image
    mark = Image.open(asset_dir() / 'canva' / 'jr_white_overlay.png').convert('RGBA')
    box = mark.getchannel('A').getbbox()
    out = io.BytesIO()
    mark.crop(box).save(out, 'PNG')
    k = 1080 / mark.width
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode(), [v * k for v in box]


MONTHS = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto',
          'settembre', 'ottobre', 'novembre', 'dicembre')


def footer_default():
    from datetime import date
    today = date.today()
    return f'Pausa nazionali · {MONTHS[today.month - 1]} {today.year}'


def build_html(players, title=TITLE_DEFAULT, kicker=KICKER_DEFAULT, footer=None):
    """players: [(Player del catalogo, codice bandiera, nome nazione[, nome da scrivere])].

    Pannelli inclinati con la bandiera, il giocatore davanti con la testa che esce sopra, filo oro
    sotto; nome (bianco) e cognome (oro) in Dharma Gothic, nazione piccola."""
    assets = asset_dir()
    fonts = (f"@font-face{{font-family:'Poppins';font-weight:500;src:url({data_uri(assets / 'fonts' / 'Poppins-Medium.ttf')})}}"
             f"@font-face{{font-family:'Dharma';src:url({data_uri(assets / 'fonts' / 'DharmaGothicEBold.otf')})}}")
    canva = assets / 'canva'
    bg, ink = data_uri(canva / 'bg_convocati.jpg'), data_uri(canva / 'probabili_third_ink.png')   # sfondo nero con fascio di luce; oro come la grafica third
    logo, (lx0, ly0, lx1, ly1) = _logo()
    flags, cards = {}, []
    for player, code, country, *shown in players:
        if code not in flags:
            path = assets / 'flags' / f'{code}.svg'
            if not path.is_file():
                raise ValueError(f'Manca la bandiera di {country}.')
            flags[code] = data_uri(path)
        path = _photo(player)
        top, cx, _hw = head_box(str(path))
        pos = f'--pl:{.5 - cx * PHOTO_W:.4f};--pt:{HEAD_TOP - top * PHOTO_W:.4f}'
        first, last = _split((shown and shown[0]) or player.name)
        cards.append(
            f'<div class="p"><div class="card"><div class="pan"><img src="{flags[code]}" alt=""></div>'
            f'<div class="pw"><img class="ph" style="{pos}" src="{data_uri(path)}" alt=""></div><div class="bar"></div></div>'
            f'<div class="tx"><div class="nm">{_esc(first)} <span class="gold">{_esc(last)}</span></div>'
            f'<div class="ct">{_esc(country.upper())}</div></div></div>'
        )
    words = str(title or TITLE_DEFAULT).strip().upper().split(None, 1)
    # Prima parola bianca, il resto oro.
    head = _esc(words[0]) + (f' <span class="gold">{_esc(words[1])}</span>' if len(words) > 1 else '')
    n, cols = len(cards), _grid(len(cards))
    foot = footer if footer is not None else footer_default()
    cut = 100 - SLANT * 100     # il lato basso del pannello va da 0 a cut%: nomi e filo oro centrati lì
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{fonts}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1440px;overflow:hidden}}
body{{position:relative;background:#0b0b0b url({bg}) center / cover no-repeat;color:#fff;font-family:'Poppins',sans-serif}}
.gold{{background:url({ink}) center / 100% 100%;-webkit-background-clip:text;background-clip:text;color:transparent}}
.logo{{position:absolute;left:{lx0:.1f}px;top:{ly0:.1f}px;width:{lx1 - lx0:.1f}px;height:{ly1 - ly0:.1f}px;
  background:url({ink}) center / 100% 100%;-webkit-mask:url({logo}) center / 100% 100% no-repeat;mask:url({logo}) center / 100% 100% no-repeat}}
.top{{position:absolute;top:84px;left:70px;right:70px;text-align:center;transform:skewX(-8deg)}}
.kick{{font-size:19px;letter-spacing:.3em;text-transform:uppercase}}
.title{{margin-top:4px;font-family:'Dharma';font-size:128px;line-height:.9;letter-spacing:.01em;white-space:nowrap}}
.grid{{position:absolute;top:262px;bottom:96px;left:50px;right:50px;display:flex;flex-wrap:wrap;justify-content:center;align-content:center;gap:var(--gy) var(--gx)}}
.p{{width:var(--u)}}
.card{{position:relative;width:var(--u);height:calc(var(--u) * {PANEL_H})}}
.pan{{position:absolute;inset:0;clip-path:polygon({100 - cut}% 0,100% 0,{cut}% 100%,0 100%);overflow:hidden}}
.pan img{{width:100%;height:100%;object-fit:cover}}
.pan::after{{content:'';position:absolute;inset:0;background:linear-gradient(160deg,rgba(255,255,255,.12),transparent 40%,rgba(0,0,0,.45))}}
/* giocatore: dentro il pannello; sopra il pannello esce la testa */
.pw{{position:absolute;inset:0;clip-path:polygon(0 -60%,100% -60%,100% 0,{cut}% 100%,0 100%,{100 - cut}% 0,0 0)}}
.ph{{position:absolute;left:calc(var(--u) * var(--pl));top:calc(var(--u) * var(--pt));width:calc(var(--u) * {PHOTO_W});
  filter:drop-shadow(8px 4px 12px rgba(0,0,0,.55))}}
.bar{{position:absolute;left:0;width:{cut}%;bottom:-8px;height:5px;background:url({ink}) center/cover;transform:skewX(-8deg)}}
.tx{{width:{cut}%;display:flex;flex-direction:column;align-items:center;text-align:center}}
.nm{{margin-top:11px;font-family:'Dharma';font-size:calc(var(--u) * .16);line-height:1;letter-spacing:.03em;white-space:nowrap;transform:skewX(-8deg)}}
.ct{{margin-top:-3px;font-size:calc(var(--u) * .056);letter-spacing:.24em;white-space:nowrap;opacity:.85}}
.foot{{position:absolute;left:0;right:0;bottom:44px;text-align:center;font-size:20px;letter-spacing:.16em;text-transform:uppercase}}
</style></head><body>
<div class="logo"></div>
<div class="top"><div class="kick gold">{_esc(kicker or KICKER_DEFAULT)}</div><div class="title" id="title">{head}</div></div>
<div class="grid" id="grid">{''.join(cards)}</div>
<div class="foot gold">{_esc(foot)}</div>
<script>
// Pannelli il più grandi possibile tra titolo e riga in basso; titolo, nomi e nazioni dentro la larghezza.
const grid = document.getElementById('grid'), n = {n}, cols = {cols}, rows = Math.ceil(n / cols);
const gx = 24, gy = 54, W = grid.clientWidth, H = grid.clientHeight;
const u = Math.min((W - gx * (cols - 1)) / cols, (H - gy * (rows - 1)) / rows / 1.36, 300);
// Larghezza esatta per le colonne scelte (senza, con pannelli piccoli ne entrerebbero di più per riga).
const side = (W - (cols * u + (cols - 1) * gx)) / 2;
grid.style.paddingLeft = grid.style.paddingRight = Math.max(0, side - 1) + 'px';
// Spazio tra le righe: quasi tutto lo spazio verticale che avanza (resta un margine di 15 px sopra e sotto),
// al massimo un pannello in più
const free = H - rows * u * 1.36 - gy * (rows - 1) - 30;
const gyFit = rows > 1 ? Math.min(gy + Math.max(0, free) / (rows - 1), gy + u) : gy;
grid.style.setProperty('--u', u + 'px'); grid.style.setProperty('--gx', gx + 'px'); grid.style.setProperty('--gy', gyFit + 'px');
const width = el => {{ const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect().width; }};
const fit = (el, max) => {{ let s = parseFloat(getComputedStyle(el).fontSize); while (width(el) > max && s > 8) {{ s -= .5; el.style.fontSize = s + 'px'; }} }};
window.__ready = document.fonts.ready.then(() => {{
  fit(document.getElementById('title'), 940);
  // Nomi e nazioni tutti della stessa grandezza: i lunghi si allargano oltre il pannello (centrati,
  // fino allo spazio tra i pannelli); se uno proprio non ci sta, si rimpiccioliscono tutti insieme.
  const room = u + gx - 6;
  ['.nm', '.ct'].forEach(sel => {{
    const els = [...document.querySelectorAll(sel)];
    const k = Math.min(1, ...els.map(el => room / width(el)));
    if (k < 1) els.forEach(el => el.style.fontSize = parseFloat(getComputedStyle(el).fontSize) * k + 'px');
  }});
  return Promise.all([...document.images].map(i => i.decode().catch(() => {{}})));
}});
</script>
</body></html>"""


def render(players, title=TITLE_DEFAULT, kicker=KICKER_DEFAULT, footer=None):
    """PNG 1920x2560 (il logo JR è già nella pagina, con lo stesso oro delle scritte)."""
    return render_html(build_html(players, title, kicker, footer))
