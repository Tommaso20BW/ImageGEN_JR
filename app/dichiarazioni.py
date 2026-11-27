"""Dichiarazioni: testo già scritto (conferenza, intervista) -> versione Telegram e versione X.

Si incolla il testo così come va pubblicato, anche diviso in blocchi con un'etichetta da sola sulla
riga (COMPLETO, 240...): il completo va su Telegram, il 240 su X; con un blocco solo, va su tutti e due.
  Telegram: emoji del canale, chi parla in grassetto, temi in grassetto, parlato e testata in corsivo
            (<b>PARTITA</b> – <i>“…”.</i>),
            firma 👉 @Juventus_Reborn in fondo, come i post del canale;
  X:        chi parla con l'hashtag sul cognome e la testata con la sua pagina, come il profilo:
            🇮🇹🗣️ Luciano #Spalletti a @SkySport post #JuveOmonia: “…”.
Chi parla sempre con nome e cognome (rosa del motore grafico + staff). Prima di una partita
"pre #Hashtag", dopo "post #Hashtag" (mai prima/dopo); senza hashtag della partita resta com'è.
Dentro le virgolette non si tocca niente. Un'etichetta numerica (240) è il limite di caratteri,
contato come X (emoji = 2).
"""
from __future__ import annotations

import html
import re

MAX_TEXT = 40000

# Testate con la loro pagina su X (come le scrive il profilo); le altre restano scritte.
OUTLETS = {
    'Sky Sport': '@SkySport', 'SkySport': '@SkySport', 'DAZN': '@DAZN_IT',
    'La Gazzetta dello Sport': '@Gazzetta_it', 'Gazzetta dello Sport': '@Gazzetta_it', 'Gazzetta': '@Gazzetta_it',
    'Tuttosport': '@tuttosport', 'La Stampa': '@LaStampa', 'Corriere dello Sport': '@CorSport',
    'Sportmediaset': '@SportMediaset', 'Sport Mediaset': '@SportMediaset', 'Rai Sport': '@RaiSport',
    'Prime Video': '@PrimeVideoIT', 'Juventus TV': '@juventusfc', 'JTV': '@juventusfc',
}
_OUTLET_RE = re.compile(r'(?<![\w@#])(' + '|'.join(re.escape(k) for k in sorted(OUTLETS, key=len, reverse=True))
                        + r')(?!\w)', re.I)

# Emoji personalizzate usate dal canale nelle dichiarazioni (le bandiere arrivano da caption.flag).
CUSTOM_EMOJI = {
    '🗣': '5370765563226236970', '👨‍🦲': '5785405760431207322', '🤵‍♂': '5940305400933917185',
    '👀': '5424885441100782420',
}
# Bandiere animate prese dai post del canale, per le nazioni che caption.FLAGS non ha ancora.
CHANNEL_FLAGS = {
    'CI': '5789597223310335831', 'DE': '5816639114795033093', 'US': '5789765362690039962',
    'TR': '5789644098583404844', 'CO': '5789843990656328355', 'BA': '5789842410108361950',
    'SN': '5816763346724069174', 'CL': '5222427035023977899', 'GB-ENG': '5789901070771691820',
}

# Allenatore e dirigenti come li scrive il canale (i giocatori arrivano dalla rosa del motore grafico).
STAFF = ['Luciano Spalletti', 'Giovanni Carnevali', 'Frederic Massara', 'Giorgio Chiellini', 'Gianluca Ferrero',
         'Damien Comolli', 'John Elkann']

_UP = 'A-ZÀ-ÖØ-Þ'
_LABEL = re.compile(rf'^[{_UP}0-9][{_UP}0-9 ]{{0,24}}$')                     # COMPLETO, 240 (da sola sulla riga)
_THEME = re.compile(rf'^([{_UP}0-9][{_UP}0-9’\'.,&/ ]{{0,60}}?)\s+[–—-]\s+(.*)$')  # PARTITA – “…”
_NAME_WORD = rf"[{_UP}][\w’'.\-]*"
_SPEAKER = re.compile(rf"{_NAME_WORD}(?:\s+(?:(?:de|da|di|del|dos|van|der|von)\s+)*{_NAME_WORD})*")


# --- conteggio come X ----------------------------------------------------------------------------
def _joins(cp, prev):
    return (cp == 0x200D or prev == 0x200D or 0xFE00 <= cp <= 0xFE0F or 0x1F3FB <= cp <= 0x1F3FF
            or 0xE0020 <= cp <= 0xE007F or cp == 0x20E3)


def graphemes(text):
    """Caratteri come li vede chi legge: un'emoji composta (bandiera, 👨‍🦲) è uno solo."""
    out, prev, flag_open = [], None, False
    for ch in str(text or ''):
        cp = ord(ch)
        regional = 0x1F1E6 <= cp <= 0x1F1FF
        if out and (_joins(cp, prev) or (regional and flag_open)):
            out[-1] += ch
            flag_open = False if regional else flag_open
        else:
            out.append(ch)
            flag_open = regional
        prev = cp
    return out


def _is_emoji(g):
    return any(ord(c) >= 0x1F000 or 0x2600 <= ord(c) <= 0x27BF for c in g)


def x_length(text):
    """Lunghezza contata come X: emoji 2, lettere latine e punteggiatura 1 (anche “ ” ’ –), il resto 2."""
    n = 0
    for g in graphemes(text):
        if _is_emoji(g):
            n += 2
            continue
        for c in g:
            cp = ord(c)
            n += 1 if cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247 else 2
    return n


# --- lettura del testo ----------------------------------------------------------------------------
def _clean(text):
    text = str(text or '').replace('\r', '')
    text = '\n'.join(re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n'))
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def blocks(text):
    """[(etichetta, testo)]: le righe COMPLETO / 240 da sole dividono i blocchi ('' se non ce ne sono)."""
    out, label, lines = [], '', []
    for line in _clean(text).split('\n'):
        if _LABEL.match(line) and not _THEME.match(line):
            if '\n'.join(lines).strip():
                out.append((label, '\n'.join(lines).strip()))
            label, lines = line.strip(), []
        else:
            lines.append(line)
    if '\n'.join(lines).strip():
        out.append((label, '\n'.join(lines).strip()))
    if len(out) == 1 and not out[0][0]:
        return _split_versions(out[0][1])
    return out


def _is_head(line):
    """Riga d'apertura: emoji e poi chi parla (🇮🇹🗣️ Spalletti a Sky Sport…)."""
    lead, rest = _lead(line)
    return bool(lead and _SPEAKER.match(rest.strip()))


def _split_versions(block):
    """Senza COMPLETO / 240: una nuova riga d'apertura dopo una riga vuota è un'altra versione.
    La più lunga è il completo (Telegram), la più corta la breve (X)."""
    lines, starts = block.split('\n'), [0]
    for n in range(1, len(lines)):
        if not lines[n - 1].strip() and _is_head(lines[n]):
            starts.append(n)
    if len(starts) != 2:
        return [('', block)]
    a, b = ('\n'.join(lines[i:j]).strip() for i, j in zip(starts, starts[1:] + [len(lines)]))
    full, short = (a, b) if x_length(a) >= x_length(b) else (b, a)
    return [('COMPLETO', full), ('BREVE', short)]


def _lead(line):
    """(emoji iniziali, resto della riga)."""
    gs = graphemes(line)
    i = 0
    while i < len(gs) and _is_emoji(gs[i]):
        i += 1
    return ''.join(gs[:i]), ''.join(gs[i:])


def _parts(block):
    """Righe del blocco come pezzi: ('head', emoji, spazio, chi parla, resto) / ('theme', tema, resto) / ('text', riga)."""
    lines = block.split('\n')
    has_themes = any(_THEME.match(line) for line in lines)
    out = []
    for n, line in enumerate(lines):
        lead, rest = _lead(line)
        theme = _THEME.match(line)
        if lead and n == 0:
            gap = rest[:len(rest) - len(rest.lstrip())]
            rest = rest.lstrip()
            m = _SPEAKER.match(rest)
            who, rest = (full_name(m.group(0)), rest[m.end():]) if m else ('', rest)
            rest = _outside_quotes(rest, _pre_post)
            if has_themes and rest and not rest.rstrip().endswith(':'):   # come il canale: "dopo #JuveOmonia:"
                rest = rest.rstrip() + ':'
            out.append(('head', lead, gap, who, rest))
        elif theme:
            out.append(('theme', theme.group(1).strip(), theme.group(2)))
        else:
            out.append(('text', line))
    return out


def _key(text):
    import unicodedata
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z]', '', text.lower())


def _people():
    """{cognome (o alias) senza accenti -> nome e cognome}: rosa del motore grafico + staff."""
    out = {}
    try:
        from livescore.graphics import goal as g
        for player in g.load_players():
            names = [player.name, *(getattr(player, 'aliases', None) or [])]
            for alias in names:
                if alias and not re.match(r'^\w\.', alias):
                    out.setdefault(_key(alias), player.name)
            out.setdefault(_key(player.name.split()[-1]), player.name)
    except Exception:  # noqa: BLE001 - senza rosa i nomi restano come scritti
        pass
    for name in STAFF:
        out.setdefault(_key(name.split()[-1]), name)
        out.setdefault(_key(name), name)
    return out


def full_name(name):
    """'Spalletti' -> 'Luciano Spalletti', 'Kolo Muani' -> 'Randal Kolo Muani' (anche su X serve nome e
    cognome); chi non è nella rosa né nello staff resta com'è."""
    found = _people().get(_key(name))
    return found if found and len(found.split()) > len(name.split()) else name


def _pre_post(text):
    """Come il canale: "pre #JuveOmonia" e "post #JuveOmonia" (non prima/dopo), fuori dalle virgolette."""
    text = re.sub(r'\b(?:dopo|post)\s+(?:la\s+partita\s+)?(?=#\w)', 'post ', text, flags=re.I)
    return re.sub(r'\b(?:prima\s+(?:della\s+partita\s+|di\s+)?|pre\s+)(?=#\w)', 'pre ', text, flags=re.I)


def _outside_quotes(text, fn):
    """Applica fn solo fuori dalle virgolette (“…” e "…")."""
    pieces = re.split(r'(“[^”]*”|"[^"]*")', text)
    return ''.join(p if i % 2 else fn(p) for i, p in enumerate(pieces))


# --- le due versioni ------------------------------------------------------------------------------
def _premium(g):
    """Emoji come la usa il canale: bandiere animate e le emoji del pack."""
    import caption
    custom = {k.replace('️', ''): v for k, v in CUSTOM_EMOJI.items()}.get(g.replace('️', ''))
    if custom:
        return caption.emoji(custom, g)
    cps = [ord(c) for c in g]
    code = ''
    if len(cps) == 2 and all(0x1F1E6 <= c <= 0x1F1FF for c in cps):
        code = ''.join(chr(c - 0x1F1E6 + ord('A')) for c in cps)
    elif cps[:1] == [0x1F3F4] and len(cps) > 2:                       # Inghilterra, Scozia, Galles
        tag = ''.join(chr(c - 0xE0000) for c in cps[1:-1]).upper()
        code = f'GB-{tag[2:]}' if tag.startswith('GB') else ''
    if code:
        if code not in caption.FLAGS and code in CHANNEL_FLAGS:
            return caption.emoji(CHANNEL_FLAGS[code], g)
        return caption.flag(code) or g
    return caption.PREMIUM.get(g, g)


def _tg_text(text, outlets=False):
    """Escape HTML, parlato in corsivo come il canale (<i>“…”.</i>, punto compreso) e, nella riga di chi
    parla, la testata in corsivo (a <i>Sky Sport</i>)."""
    pieces = re.split(r'(“[^”]*”\.?|"[^"]*"\.?)', text)
    out = []
    for i, piece in enumerate(pieces):
        piece = html.escape(piece, quote=False)
        if i % 2:
            out.append(f'<i>{piece}</i>')
        else:
            out.append(_OUTLET_RE.sub(lambda m: f'<i>{m.group(1)}</i>', piece) if outlets else piece)
    return ''.join(out)


def telegram_version(block, sign=True):
    """HTML di Telegram: emoji del canale, chi parla e i temi in grassetto, parlato in corsivo, firma in fondo."""
    import caption
    lines = []
    for p in _parts(block):
        if p[0] == 'head':
            _, lead, gap, who, rest = p
            lines.append(''.join(_premium(g) for g in graphemes(lead)) + gap
                         + (f'<b>{html.escape(who, quote=False)}</b>' if who else '') + _tg_text(rest, outlets=True))
        elif p[0] == 'theme':
            lines.append(f'<b>{html.escape(p[1], quote=False)}</b> – {_tg_text(p[2])}')
        else:
            lines.append(_tg_text(p[1]))
    body = '\n'.join(lines)
    return f'{body}\n\n{caption.SIGN} @Juventus_Reborn' if sign else body


def x_version(block):
    """Testo per X: hashtag sul cognome di chi parla, testata con la sua pagina, niente firma."""
    import caption
    lines = []
    for p in _parts(block):
        if p[0] == 'head':
            _, lead, gap, who, rest = p
            rest = _outside_quotes(rest, lambda s: _OUTLET_RE.sub(
                lambda m: next(v for k, v in OUTLETS.items() if k.lower() == m.group(1).lower()), s))
            lines.append(lead + gap + (caption.x_person(who) if who else '') + rest)
        elif p[0] == 'theme':
            lines.append(f'{p[1]} – {p[2]}')
        else:
            lines.append(p[1])
    return '\n'.join(lines)


def pick(parts):
    """(blocco per Telegram, blocco per X): con COMPLETO e 240 il completo va su Telegram e il 240 su X;
    con un blocco solo, quello va su tutti e due."""
    if not parts:
        return None, None
    tg = next((p for p in parts if not p[0].isdigit()), parts[0])
    x = next((p for p in parts if p[0].isdigit() or p[0] == 'BREVE'), tg)
    return tg, x


def render(parts):
    """Un risultato solo: versione Telegram e versione X pronte, con i caratteri contati come X."""
    import caption
    (tg_label, tg_block), (x_label, x_block) = pick(parts)
    tg, x = telegram_version(tg_block), x_version(x_block)
    limit = int(x_label) if x_label.isdigit() else None
    x_len = x_length(x)
    return {'tg_label': tg_label, 'x_label': x_label, 'raw': {'tg': tg_block, 'x': x_block}, 'tg': tg, 'x': x,
            'tg_len': x_length(caption.plain(telegram_version(tg_block, sign=False))), 'x_len': x_len,
            'limit': limit, 'over': bool(limit and x_len > limit)}


def convert(text):
    """{'post': {...}}: Telegram dal blocco completo, X dal blocco con il limite (o dallo stesso)."""
    text = str(text or '')
    if len(text.strip()) < 5:
        raise ValueError('Incolla il testo da sistemare.')
    if len(text) > MAX_TEXT:
        raise ValueError(f'Testo troppo lungo (massimo {MAX_TEXT} caratteri).')
    parts = blocks(text)
    if not parts:
        raise ValueError('Incolla il testo da sistemare.')
    return {'post': render(parts)}


def send(telegram, post):
    """Bot JR: versione Telegram (pronta per il canale) e, in risposta, la versione per X. -> id."""
    raw = (post or {}).get('raw')
    tg_block, x_block = (raw.get('tg'), raw.get('x')) if isinstance(raw, dict) else (raw, raw)
    tg_block, x_block = _clean(tg_block), _clean(x_block or tg_block)
    if not tg_block:
        raise ValueError('Nessun testo da mandare.')
    first = int(telegram.copy_text(telegram_version(tg_block)))
    second = int(telegram.copy_text(html.escape(x_version(x_block), quote=False), reply_to=first))
    return [first, second]
