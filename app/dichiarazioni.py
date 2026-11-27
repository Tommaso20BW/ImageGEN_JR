"""Dichiarazioni: conferenze e interviste (o notizie) -> post pronto in due versioni, solo testo.

Il testo incollato va a Claude con le regole delle news (data/regole_news.md) e con il modo in cui
il canale scrive il parlato: «🇨🇮🗣 <b>Jeremie Boga</b> a Sky Sport dopo #JuveOmonia: “…”.»
Claude scrive UNA volta il testo con i segni {Nome|Hashtag} e {@Testata}; le due versioni le fa
questo file, così sono per forza identiche:
  Telegram: nomi in grassetto, emoji del canale, firma in fondo;
  X:        Jeremie #Boga a @SkySport dopo #JuveOmonia: “…”. (come sul profilo, senza firma)
Il limite di 240 caratteri si conta come X (emoji = 2): se una proposta sfora si chiede di accorciarla.
"""
from __future__ import annotations

import html
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

MODEL = 'claude-opus-5-5'
LIMIT = 240
MAX_TEXT = 40000                 # caratteri incollati (una conferenza lunga sta ben sotto)
MAX_POSTS = 3
RULES_FILE = Path(__file__).resolve().parent / 'data' / 'regole_news.md'

# Testate con la loro pagina su X (come le scrive il profilo); le altre restano scritte.
OUTLETS = {
    'sky sport': '@SkySport', 'sky': '@SkySport', 'skysport': '@SkySport',
    'dazn': '@DAZN_IT',
    'la gazzetta dello sport': '@Gazzetta_it', 'gazzetta dello sport': '@Gazzetta_it', 'gazzetta': '@Gazzetta_it',
    'tuttosport': '@tuttosport', 'la stampa': '@LaStampa', 'corriere dello sport': '@CorSport',
    'sportmediaset': '@SportMediaset', 'sport mediaset': '@SportMediaset', 'rai sport': '@RaiSport',
}

# Emoji personalizzate usate dal canale nelle dichiarazioni (le bandiere arrivano da caption.flag).
CUSTOM_EMOJI = {
    '🗣': '5370765563226236970', '👨‍🦲': '5785405760431207322', '🤵‍♂️': '5940305400933917185',
    '👀': '5424885441100782420',
}
# Bandiere animate prese dai post del canale, per le nazioni che caption.FLAGS non ha ancora.
CHANNEL_FLAGS = {
    'CI': '5789597223310335831', 'DE': '5816639114795033093', 'US': '5789765362690039962',
    'TR': '5789644098583404844', 'CO': '5789843990656328355', 'BA': '5789842410108361950',
    'SN': '5816763346724069174', 'CL': '5222427035023977899', 'GB-ENG': '5789901070771691820',
}

CHANNEL_STYLE = """COME IL CANALE SCRIVE LE DICHIARAZIONI (seguilo come le regole)
- Forma: [emoji]🗣 {Nome Cognome|Cognome} a {@Testata} [pre|dopo] #HashtagPartita: “Citazione”.
  Esempi veri del canale (già con i segni del formato):
  🇨🇮🗣 {Jeremie Boga|Boga} a {@Sky Sport} dopo #JuveOmonia: “Abbiamo fatto molto bene, è bello vedere tutti gli attaccanti in gol. Lavoro spesso sul tiro a giro. Le vittorie ci danno fiducia, ora dobbiamo trovare continuità e iniziare meglio le partite”.
  👨‍🦲🗣 {Luciano Spalletti|Spalletti} a {@DAZN} pre #FiorentinaJuve: “A Firenze il clima sarà molto caldo, con il pubblico e la città che faranno sentire la loro presenza”.
  🤵‍♂️🗣 {Giovanni Carnevali|Carnevali} ai soci {Juventus|Juventus}: “Spalletti è l’allenatore della Juventus e noi lo sosteniamo”.
  🇺🇸🗣 {Weston McKennie|McKennie}: “Voglio chiarire che non ho intenzione di lasciare la Juventus. Sono felice qui. Per questo ho firmato un nuovo contratto”.
  🧐🗣 {Mateu Alemany|Alemany}, ds {Atletico Madrid|AtleticoMadrid}: “Non abbiamo novità sul riscatto di Jonathan David”.
  🇨🇱🗣 {Arturo Vidal|Vidal} alla {@Gazzetta dello Sport}: “Tornerò alla Juventus da allenatore. Il sesto posto è un fallimento: la Juve deve lottare per vincere”.
- Emoji iniziale: la bandiera della nazionalità di chi parla (giocatori, ex giocatori, allenatori); 👨‍🦲 per Luciano Spalletti; 🤵‍♂️ per i dirigenti della Juventus; 👀 per chi non ha una bandiera sicura. Subito dopo sempre 🗣.
- Citazione tra virgolette tipografiche “ ”, il punto finale DOPO la virgoletta di chiusura: “…”.
- Dentro le virgolette ci sono solo parole dette davvero: puoi scegliere i passaggi, tagliare e unire frasi vicine, ma non cambiare il senso, non aggiungere parole e non rendere più forte quello che ha detto. Una domanda del giornalista si rende come “Tema? Risposta”, ad esempio “Conceição? Ha fatto una grande partita”.
- Se la fonte non è in italiano, traduci la citazione in un italiano naturale e fedele.
- Dentro le virgolette i nomi restano scritti normali (niente segni { }).
- Hashtag della partita (es. #JuveOmonia) solo se la dichiarazione è legata a quella partita: "pre" se detta prima, "dopo" se detta dopo. Se non è chiaro, non metterlo.
- Nelle dichiarazioni la testata si scrive (a Sky Sport, a DAZN, alla Gazzetta dello Sport, in conferenza stampa) quando è nota: è la "necessità" del punto 9.
- Se il testo non è una dichiarazione ma una notizia, scrivila secondo le regole (emoji ⚪ ecc.), senza virgolette inventate.
"""

FORMAT = f"""COME RESTITUIRE IL TESTO
Il punto 13 (le due versioni) lo fa il programma: tu scrivi il testo UNA volta, con questi segni.
- {{Nome visibile|Hashtag}} per ogni nome di persona o club FUORI dalle virgolette. L'hashtag è senza # e senza spazi e corrisponde alla parte finale del nome visibile:
  {{Luciano Spalletti|Spalletti}} diventa "<b>Luciano Spalletti</b>" su Telegram e "Luciano #Spalletti" su X;
  {{Randal Kolo Muani|KoloMuani}} -> "Randal #KoloMuani"; {{Juventus|Juventus}} -> "#Juventus"; {{Aston Villa|AstonVilla}} -> "#AstonVilla".
- {{@Testata}} per giornale, TV o sito: {{@Sky Sport}} diventa "Sky Sport" su Telegram e "@SkySport" su X.
- Nient'altro: niente **, niente <b>, niente # davanti ai nomi, niente firma, niente fonte in fondo, niente titolo. L'hashtag della partita scrivilo così com'è (#JuveOmonia).
LIMITE: ogni proposta al massimo {LIMIT} caratteri contati come X (ogni emoji vale 2; contano anche # e @ della versione X). Stai fra 200 e 235.
PROPOSTE: da 1 a {MAX_POSTS}. Un'intervista breve: 1. Una conferenza o un'intervista lunga: i passaggi più forti, uno diverso per proposta, prima quelli più importanti per la Juventus.
"tema": 1-3 parole che dicono di cosa parla la proposta (es. "Ekhator", "Mercato", "Infortuni")."""

SCHEMA = {
    'type': 'object',
    'properties': {
        'proposte': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'tema': {'type': 'string'}, 'testo': {'type': 'string'}},
                'required': ['tema', 'testo'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['proposte'],
    'additionalProperties': False,
}

_NAME = re.compile(r'\{([^{}|@][^{}|]*)\|([^{}|]*)\}')
_OUTLET = re.compile(r'\{@([^{}]+)\}')


def system_prompt():
    rules = RULES_FILE.read_text(encoding='utf-8').strip()
    return f"Sei la redazione di Juventus Reborn (canale Telegram e profilo X).\n\n{rules}\n\n{CHANNEL_STYLE}\n{FORMAT}"


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
    return any(ord(c) >= 0x1F000 or 0x2600 <= ord(c) <= 0x27BF or ord(c) == 0xFE0F for c in g)


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


# --- le due versioni ------------------------------------------------------------------------------
def _word(text):
    return re.sub(r'[^\w]', '', str(text or ''))


def x_name(visible, tag):
    """Nome per X: l'hashtag prende il posto della parte finale del nome (Luciano #Spalletti)."""
    tag = _word(tag) or _word(visible.split()[-1] if visible.split() else '')
    words = visible.split()
    for i in range(len(words)):
        if _word(''.join(words[i:])).lower() == tag.lower():
            return ' '.join(words[:i] + [f'#{tag}'])
    return f'#{tag}' if tag else visible


def x_outlet(name):
    return OUTLETS.get(re.sub(r'\s+', ' ', name.strip().lower()), name.strip())


def _clean(text):
    text = str(text or '').replace('\r', '')
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'</?b>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def plain_version(text):
    """Testo visibile (versione 1 senza grassetto)."""
    text = _OUTLET.sub(lambda m: m.group(1).strip(), _clean(text))
    return _NAME.sub(lambda m: m.group(1).strip(), text).replace('{', '').replace('}', '')


def x_version(text):
    text = _OUTLET.sub(lambda m: x_outlet(m.group(1)), _clean(text))
    return _NAME.sub(lambda m: x_name(m.group(1).strip(), m.group(2)), text).replace('{', '').replace('}', '')


def _lead_emoji(text):
    """(emoji iniziali, resto del testo)."""
    gs = graphemes(text)
    i = 0
    while i < len(gs) and _is_emoji(gs[i]):
        i += 1
    return gs[:i], ''.join(gs[i:])


def _premium(g):
    """Emoji iniziale come la usa il canale: bandiere animate e le emoji del pack."""
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


def telegram_version(text, sign=True):
    """Versione 1 in HTML di Telegram: nomi in grassetto, emoji del canale, firma in fondo."""
    import caption
    lead, rest = _lead_emoji(_clean(text))
    pieces, pos = [], 0
    for m in re.finditer(f'{_NAME.pattern}|{_OUTLET.pattern}', rest):
        pieces.append(html.escape(rest[pos:m.start()], quote=False))
        if m.group(1) is not None:
            pieces.append(f'<b>{html.escape(m.group(1).strip(), quote=False)}</b>')
        else:
            pieces.append(html.escape(m.group(3).strip(), quote=False))
        pos = m.end()
    pieces.append(html.escape(rest[pos:], quote=False))
    body = ''.join(_premium(g) for g in lead) + ''.join(pieces).replace('{', '').replace('}', '')
    return f'{body}\n\n{caption.SIGN} @Juventus_Reborn' if sign else body


def render(item):
    """Proposta di Claude -> le due versioni pronte, con i caratteri contati."""
    raw = _clean(item.get('testo'))
    v1, v2 = plain_version(raw), x_version(raw)
    l1, l2 = x_length(v1), x_length(v2)
    return {'tema': str(item.get('tema') or '').strip()[:40], 'raw': raw, 'tg': telegram_version(raw),
            'tg_text': v1, 'x': v2, 'tg_len': l1, 'x_len': l2, 'limit': LIMIT, 'over': max(l1, l2) > LIMIT}


# --- partita vicina (per #JuveOmonia, pre/dopo) ---------------------------------------------------
def match_context(fixtures, now=None):
    """Righe sulle partite Juve di questi giorni, da dare a Claude ('' se il calendario non risponde)."""
    if fixtures is None:
        return ''
    from zoneinfo import ZoneInfo
    now = now or datetime.now(ZoneInfo('Europe/Rome'))
    try:
        rows = fixtures((now - timedelta(days=3)).strftime('%Y-%m-%d'), (now + timedelta(days=3)).strftime('%Y-%m-%d'))
    except Exception:  # noqa: BLE001 - senza calendario si va avanti lo stesso
        return ''
    lines = []
    for m in rows or []:
        try:
            from livescore.core import team_names
            other = m.get('opponent_espn') or m.get('opponent') or ''
            home, away = ('Juventus', other) if m.get('side') == 'home' else (other, 'Juventus')
            tag = html.unescape(team_names.build_hashtag(home, away))
        except Exception:  # noqa: BLE001
            continue
        lines.append(f"- {tag}: {m.get('date')} ore {m.get('time')}")
    return '\n'.join(lines)


# --- Claude --------------------------------------------------------------------------------------
def _client():
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ValueError('Manca la chiave di Claude: aggiungi il secret ANTHROPIC_API_KEY al repo di ImageGEN.')
    import anthropic
    return anthropic.Anthropic(timeout=150, max_retries=2)


def _ask(client, messages):
    import anthropic
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
            system=[{'type': 'text', 'text': system_prompt(), 'cache_control': {'type': 'ephemeral'}}],
            output_config={'effort': 'medium', 'format': {'type': 'json_schema', 'schema': SCHEMA}},
            messages=messages,
        )
    except anthropic.AuthenticationError as exc:
        raise ValueError('Chiave di Claude non valida: controlla il secret ANTHROPIC_API_KEY.') from exc
    except anthropic.PermissionDeniedError as exc:
        raise ValueError('La chiave di Claude non ha i permessi (o il credito è finito).') from exc
    except anthropic.RateLimitError as exc:
        raise ValueError('Claude è occupato. Riprova tra un minuto.') from exc
    except anthropic.APIStatusError as exc:
        raise ValueError(f'Claude non ha risposto (errore {exc.status_code}). Riprova.') from exc
    except anthropic.APIConnectionError as exc:
        raise ValueError('Claude non raggiungibile. Riprova tra poco.') from exc
    if response.stop_reason == 'refusal':
        raise ValueError('Claude non ha voluto scrivere questo testo.')
    text = next((b.text for b in response.content if getattr(b, 'type', '') == 'text'), '')
    try:
        items = json.loads(text).get('proposte') or []
    except (ValueError, AttributeError) as exc:
        raise ValueError('Risposta di Claude non leggibile. Riprova.') from exc
    return response, [i for i in items if isinstance(i, dict) and str(i.get('testo') or '').strip()]


def _request(text, note, context, today):
    parts = [f'Oggi è {today}.']
    if context:
        parts.append(f'Partite della Juventus di questi giorni (per l\'hashtag e per pre/dopo):\n{context}')
    if note:
        parts.append(f'Nota di chi incolla (chi parla, dove, quando): {note}')
    parts.append(f'TESTO DA CONVERTIRE:\n"""\n{text}\n"""')
    return '\n\n'.join(parts)


def convert(text, note='', fixtures=None, client=None, now=None):
    """{'posts': [...]} con 1-3 proposte; ognuna ha la versione Telegram (HTML, firma compresa) e X."""
    text = str(text or '').replace('\r', '').strip()
    note = re.sub(r'\s+', ' ', str(note or '')).strip()[:300]
    if len(text) < 20:
        raise ValueError('Incolla il testo della conferenza o dell’intervista.')
    if len(text) > MAX_TEXT:
        raise ValueError(f'Testo troppo lungo (massimo {MAX_TEXT} caratteri).')
    client = client or _client()
    from zoneinfo import ZoneInfo
    now = now or datetime.now(ZoneInfo('Europe/Rome'))
    messages = [{'role': 'user', 'content': _request(text, note, match_context(fixtures, now),
                                                     now.strftime('%d/%m/%Y %H:%M'))}]
    response, items = _ask(client, messages)
    posts = [render(i) for i in items[:MAX_POSTS]]
    over = [(n, p) for n, p in enumerate(posts, 1) if p['over']]
    if over:                                           # una seconda volta, con i conti fatti qui
        counts = ', '.join(f"proposta {n}: {max(p['tg_len'], p['x_len'])}/{LIMIT}" for n, p in over)
        messages += [{'role': 'assistant', 'content': response.content},
                     {'role': 'user', 'content': f'Troppo lunghe ({counts}, contate come X). Restituisci di nuovo '
                                                 f'tutte le proposte, quelle lunghe accorciate sotto {LIMIT} '
                                                 'senza perdere il senso e le informazioni importanti.'}]
        try:
            _, again = _ask(client, messages)
            fixed = [render(i) for i in again[:MAX_POSTS]]
            if fixed and sum(p['over'] for p in fixed) < len(over):
                posts = fixed
        except ValueError:
            pass
    if not posts:
        raise ValueError('Claude non ha scritto nessuna proposta. Riprova.')
    return {'posts': posts}


# --- lavoro in sottofondo: il tunnel chiude le richieste dopo ~100 s, Claude può metterci di più ----
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
JOB_TTL = 900


def start(text, note='', fixtures=None, client=None):
    """Fa partire convert() in sottofondo e restituisce {'job': codice} (controlli veloci prima)."""
    text = str(text or '').strip()
    if len(text) < 20:
        raise ValueError('Incolla il testo della conferenza o dell’intervista.')
    if len(text) > MAX_TEXT:
        raise ValueError(f'Testo troppo lungo (massimo {MAX_TEXT} caratteri).')
    client = client or _client()
    job = secrets.token_hex(8)
    with _JOBS_LOCK:
        for key in [k for k, v in _JOBS.items() if time.time() - v['at'] > JOB_TTL]:
            del _JOBS[key]
        _JOBS[job] = {'at': time.time(), 'done': False}

    def run():
        try:
            out = {'done': True, **convert(text, note, fixtures=fixtures, client=client)}
        except ValueError as exc:
            out = {'done': True, 'error': str(exc)}
        except Exception as exc:  # noqa: BLE001 - qualsiasi guasto torna alla Mini App come errore
            out = {'done': True, 'error': f'Notizia non scritta ({type(exc).__name__}). Riprova.'}
        with _JOBS_LOCK:
            if job in _JOBS:
                _JOBS[job].update(out)

    threading.Thread(target=run, name='dichiarazioni', daemon=True).start()
    return {'job': job}


def status(job):
    """{'done': False} finché Claude scrive; poi le proposte (o ValueError con il motivo)."""
    with _JOBS_LOCK:
        state = dict(_JOBS.get(str(job or '')) or {})
    if not state:
        raise ValueError('Richiesta scaduta. Premi di nuovo “Scrivi la notizia”.')
    if not state['done']:
        return {'done': False}
    with _JOBS_LOCK:
        _JOBS.pop(str(job), None)
    if state.get('error'):
        raise ValueError(state['error'])
    return {'done': True, 'posts': state.get('posts') or []}


def send(telegram, post):
    """Bot JR: versione Telegram (pronta per il canale) e, in risposta, la versione per X. -> id."""
    raw = _clean((post or {}).get('raw'))
    if not raw:
        raise ValueError('Nessuna proposta scelta.')
    first = int(telegram.copy_text(telegram_version(raw)))
    second = int(telegram.copy_text(html.escape(x_version(raw), quote=False), reply_to=first))
    return [first, second]
