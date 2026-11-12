"""Testo sotto la foto su Telegram (HTML), come i post del canale Juventus Reborn.

Grafiche della partita (Gol, Half Time, Full Time, Statistiche...): stesso testo dei messaggi
di LiveScore (nomi italiani e hashtag di Impostazioni › Nomi). Le altre (Matchday, XI,
Classifica, Convocati...) seguono i post fatti a mano, con le emoji personalizzate del canale.
Queste ultime finiscono con la firma 👉 @Juventus_Reborn; quelle della diretta no, come sul canale.
Post, Storie e Citazioni partono senza testo.
"""
import html

ALLENATORE = 'Spalletti'          # nel testo della Squad List ("I convocati di Spalletti")


def emoji(emoji_id, fallback):
    """Emoji personalizzata di Telegram (chi non la vede legge `fallback`)."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


SIGN = emoji('5985659276327132147', '👉')
E_NEWS = emoji('5433982607035474385', '📰')
E_STATS = emoji('5431577498364158238', '📊')
E_DAY = emoji('5431897022456145283', '📆')
E_ITA = emoji('5861702401290936738', '🇮🇹')        # Serie A
E_CI = emoji('5861593197452468452', '🇮🇹')         # Coppa Italia
E_UEFA = emoji('5800778775528479618', '🇪🇺')       # Europa League
E_FRIENDLY = emoji('5357080225463149588', '🤝')
E_HOME = emoji('5789811507818668397', '🏟')
E_TV = emoji('5373330964372004748', '📺')
E_UP = emoji('5364105043907716258', '🆙')
E_FIRE = emoji('5420315771991497307', '🔥')
E_VS = emoji('5408935401442267103', '⚔️')
E_AWAY = emoji('5361600266225326825', '✈️')
E_TIME = emoji('5413704112220949842', '⏰')
E_PHONE = emoji('5406809207947142040', '📲')
E_OFFICIAL = emoji('5427009714745517609', '✅')
E_NEW = emoji('5361979468887893611', '🆕')
E_CHECK = emoji('5454096630372379732', '☑️')
E_NOTE = emoji('5334882760735598374', '📝')
E_WORLD = emoji('5399898266265475100', '🌍')

# Testi delle fasi come LiveScore (livescore/constants.py e match/*.py).
PHASES = {
    'kick': 'INIZIO PARTITA ⚡️',
    'half': 'FINE PRIMO TEMPO 🏁',
    'second': 'INIZIO SECONDO TEMPO ⚡️',
    'end_of_90': 'FINE TEMPI REGOLAMENTARI 🏁',
    'full': 'FINE PARTITA 🏁',
}
COMPETITION_NAMES = {
    'ita.1': 'Serie A', 'ita.coppa_italia': 'Coppa Italia', 'ita.super_cup': 'Supercoppa Italiana',
    'uefa.champions': 'Champions League', 'uefa.europa': 'Europa League',
    'uefa.europa.conf': 'Conference League', 'uefa.super_cup': 'Supercoppa UEFA',
    'fifa.cwc': 'Mondiale per Club', 'club.friendly': 'Amichevole',
}
TABLES = {   # classifica: emoji e nome della competizione, come nei post del canale
    'SA': (E_ITA, 'Serie A'), 'UCL': ('🇪🇺', 'UCL'), 'UEL': (E_UEFA, 'UEL'), 'UECL': ('🇪🇺', 'UECL'),
}
# Matchday: emoji della competizione e canale TV di solito (la Mini App non chiede la TV).
MD_COMPETITION = {'ita.1': E_ITA, 'ita.coppa_italia': E_CI, 'uefa.europa': E_UEFA, 'club.friendly': E_FRIENDLY}
MD_TV = {'ita.1': 'DAZN', 'ita.coppa_italia': 'Mediaset', 'ita.super_cup': 'Mediaset',
         'uefa.champions': 'Sky Sport', 'uefa.europa': 'Sky Sport', 'uefa.europa.conf': 'Sky Sport',
         'uefa.super_cup': 'Sky Sport', 'club.friendly': 'Juventus.com'}
MONTHS = ('GENNAIO', 'FEBBRAIO', 'MARZO', 'APRILE', 'MAGGIO', 'GIUGNO', 'LUGLIO', 'AGOSTO',
          'SETTEMBRE', 'OTTOBRE', 'NOVEMBRE', 'DICEMBRE')
_SMALL = {'di', 'del', 'della', 'dei', 'degli', 'delle', 'de', 'da', 'la', 'le', 'il', 'lo', 'e'}


def _serif(text):
    """Lettere e cifre in grassetto Unicode (𝐍𝐎𝐕𝐄𝐌𝐁𝐑𝐄 𝟐𝟎𝟐𝟔), come nei post del canale."""
    out = []
    for ch in str(text):
        if 'A' <= ch <= 'Z':
            ch = chr(0x1D400 + ord(ch) - ord('A'))
        elif 'a' <= ch <= 'z':
            ch = chr(0x1D41A + ord(ch) - ord('a'))
        elif '0' <= ch <= '9':
            ch = chr(0x1D7CE + ord(ch) - ord('0'))
        out.append(ch)
    return esc(''.join(out))


def esc(value):
    return html.escape(str(value or ''), quote=False)


def _espn_key(names):
    """Nome ESPN della squadra (chiave di teams.json o di Impostazioni › Nomi) tra i suoi nomi."""
    from livescore.core.team_names import TEAM_MAP
    from livescore.core import team_overrides
    keys = {k.casefold(): k for k in TEAM_MAP}
    for name in names:
        name = str(name or '').strip()
        if not name:
            continue
        if name.casefold() in keys:
            return keys[name.casefold()]
        try:
            if team_overrides.name_entry(name):
                return name
        except Exception:  # noqa: BLE001 - una correzione rotta non deve fermare l'invio
            pass
    # Nome del catalogo loghi diverso da quello ESPN ("FC Bayern Munchen" / "Bayern Munich"):
    # stesso abbinamento di LiveScore, solo se il migliore è netto.
    from livescore.core import team_matching as tm
    best = []
    for key in TEAM_MAP:
        score = max((tm.name_score(n, key) for n in names if n), default=0)
        best.append((score, key))
    best.sort(reverse=True)
    if best and best[0][0] >= tm.MIN_SCORE and (len(best) < 2 or best[0][0] - best[1][0] >= tm.MIN_MARGIN):
        return best[0][1]
    return None


def _plain(name):
    """Squadra senza nome ESPN: via le parole generiche ("FC Bayern Munchen" -> "Bayern Munchen")."""
    from livescore.core import team_matching as tm
    words = str(name or '').split()
    kept = [w for w in words if tm.normalize_team_name(w) not in tm.GENERIC_TOKENS]
    return ' '.join(kept or words)


def _teams(data):
    """(casa, trasferta) come nomi ESPN, da passare a translate_team e build_hashtag."""
    opponent = data.get('opponent') or {}
    if data.get('team') == 'italy':
        ours, theirs = 'Italy', str(opponent.get('name') or '')
        theirs = _espn_key([theirs]) or theirs
    else:
        ours = 'Juventus'
        names = [opponent.get('name'), opponent.get('display_name'), *(opponent.get('aliases') or [])]
        theirs = _espn_key(names) or _plain(opponent.get('display_name') or opponent.get('name'))
    return (ours, theirs) if data.get('side') != 'away' else (theirs, ours)


def _match(data):
    """Nomi italiani (già con l'escape), hashtag ed emoji della competizione."""
    from livescore.core import leagues, team_names
    home, away = _teams(data)
    return {
        'home': esc(team_names.translate_team(home)),
        'away': esc(team_names.translate_team(away)),
        'tag': team_names.build_hashtag(home, away),
        'comp': leagues.get_league_emoji(str(data.get('competition') or '')),
        'juve_home': data.get('side') != 'away',
    }


def _score(m, score, scorer_home=None):
    """Risultato come LiveScore: in grassetto chi è avanti (nel Gol: chi ha segnato)."""
    h, a = int(score[0]), int(score[1])
    lead = scorer_home if scorer_home is not None else (True if h > a else False if a > h else None)
    if lead is True:
        return f"<b>{m['home']} {h}</b>-{a} {m['away']}"
    if lead is False:
        return f"{m['home']} {h}-<b>{a} {m['away']}</b>"
    return f"{m['home']} {h}-{a} {m['away']}"


def _player(name):
    from livescore.core import text as txt
    return txt.fmt_player(str(name or ''))


def _stadium(name):
    words = str(name or '').lower().split()
    return ' '.join(w if i and w in _SMALL else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _team_emoji(data):
    """Emoji dell'avversario dai pack (come sul canale); 🆚 se non c'è."""
    import team_emoji
    found = None if data.get('team') == 'italy' else team_emoji.find(data.get('opponent'))
    return emoji(*found) if found else '🆚'


def _match_caption(data):
    kind = data['kind']
    m = _match(data)
    tail = f"{m['comp']} {m['tag']}"
    score = data.get('score')
    if kind in ('goal', 'saved'):
        minute = esc(data.get('minute'))
        if kind == 'goal':
            # Gol (anche l'autogol avversario) sempre a favore della nostra squadra.
            suffix = {'penalty': ' (Rig.)', 'own': ' (Autogol)'}.get(data.get('goal_type'), '')
            head, line = f"<b>GOAL · {minute}' 🎙</b>", f"⚽️ <i>{_player(data.get('player'))}{suffix}</i>"
            board = _score(m, score, scorer_home=m['juve_home']) if score else ''
        else:
            head, line = f"<b>PARATA · {minute}' 🧤</b>", f"🧤 <i>{_player(data.get('player'))}</i>"
            board = _score(m, score) if score else ''
        return f"{head}\n\n" + (f"{board}\n" if board else '') + f"{line}\n\n{tail}"
    if kind == 'kick':
        return f"<b>{PHASES[kind]}</b>\n\n{m['home']} - {m['away']}\n\n{tail}"
    if kind in PHASES:
        board = _score(m, score)
        shootout = data.get('shootout') if kind == 'full' else None
        if shootout:
            sh, sa = int(shootout[0]), int(shootout[1])
            h, a = int(score[0]), int(score[1])
            board = (f"<b>{m['home']} {h} ({sh})</b>-({sa}) {a} {m['away']}" if sh > sa
                     else f"{m['home']} {h} ({sh})-<b>({sa}) {a} {m['away']}</b>")
        title = PHASES[kind]
        if kind == 'full' and data.get('extra_time') and not shootout:
            title = 'FINE PARTITA (d.t.s.) 🏁'
        return f"<b>{title}</b>\n\n{board}\n\n{tail}"
    if kind == 'stats':
        from livescore.constants import MOMENTI_CONFIG
        return f"{MOMENTI_CONFIG[data['moment']]['titolo']}\n\n{tail}"
    if kind == 'xi':
        if data.get('team') == 'italy':
            return f"✅📋 𝐗𝐈 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄 𝐈𝐓𝐀𝐋𝐈𝐀\n\n{tail}"
        return f"{E_OFFICIAL}<b>📋</b> 𝐗𝐈 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄 {m['tag']}"
    if kind == 'pxi':
        return f"{E_NEW}<b>📋</b> 𝐏𝐑𝐎𝐁𝐀𝐁𝐈𝐋𝐄 𝐗𝐈 {m['tag']}"
    if kind == 'squad':
        return f"{E_CHECK}{E_NOTE} I convocati di <b>{esc(ALLENATORE)}</b> per {m['tag']}."
    if kind == 'md':
        competition = str(data.get('competition') or '')
        comp_emoji = MD_COMPETITION.get(competition, m['comp'])
        opponent = m['away'] if m['juve_home'] else m['home']
        info = data.get('info') or {}
        place = E_HOME if m['juve_home'] else E_AWAY
        rows = [f"{comp_emoji} {esc(COMPETITION_NAMES.get(competition, ''))}",
                f"{_team_emoji(data)} {opponent}",
                f"{place} {esc(_stadium(info.get('stadium')))}",
                f"{E_TV} {esc(MD_TV.get(competition, ''))}",
                f"{E_TIME} {esc(str(info.get('time') or '').split(' ')[0])}",
                f"{E_PHONE} {m['tag']}"]
        return f"𝐌𝐀𝐓𝐂𝐇𝐃𝐀𝐘 {E_FIRE}{E_VS}\n\n" + '\n'.join(f'<i>{r}</i>' for r in rows if r.split(' ', 1)[-1].strip())
    return ''


def _giornata(comp):
    """Giornata della classifica appena letta da Diretta.it per la grafica (None se non c'è)."""
    try:
        from graphics import classifica
        value = int((classifica._last.get(comp) or {}).get('giornata') or 0)
    except Exception:  # noqa: BLE001
        return None
    return value or None


def _other_caption(data):
    kind = data['kind']
    if kind == 'table':
        comp = str(data.get('competition') or '').upper()
        if data.get('view') == 'bracket' or comp == 'CI':
            return f"{E_UP}{E_CI} Tabellone<b> Coppa Italia </b>aggiornato."
        flag, name = TABLES.get(comp, ('', ''))
        text = f"{flag}{E_STATS}<b> {name} | Classifica</b>"
        round_ = _giornata(comp)
        return text + (f"\n{E_DAY}<i> {round_}ª Giornata</i>" if round_ else '')
    if kind == 'conv':
        return f"{E_WORLD}<b>📋</b> I bianconeri convocati dalle rispettive nazionali."
    if kind == 'cal':
        month = int(data.get('month') or 0)
        name = MONTHS[month - 1] if 1 <= month <= 12 else ''
        when = ' '.join(str(part) for part in (name, data.get('year')) if part)
        return f"{E_VS}{E_DAY} {_serif(when)}"
    return ''


MATCH_KINDS = {'goal', 'saved', 'kick', 'half', 'second', 'end_of_90', 'full', 'stats', 'xi', 'pxi',
               'squad', 'md'}


# Post della diretta (come quelli di LiveScore): sul canale non hanno la firma.
LIVE_KINDS = {'goal', 'saved', 'kick', 'half', 'second', 'end_of_90', 'full', 'stats'}


# Post (testo scritto ogni volta a mano), Storie e Citazioni (per Instagram, X, Threads): niente testo.
NO_CAPTION = {'jr', 'igbn', 'igq', 'xq', 'thq', 'rin'}


def _live(data):
    return data.get('kind') in LIVE_KINDS or (data.get('kind') == 'xi' and data.get('team') == 'italy')


def build(data):
    """Didascalia HTML della grafica ('' se non ne ha); firma in fondo tranne che nella diretta."""
    kind = data.get('kind')
    if kind in NO_CAPTION:
        return ''
    body = _match_caption(data) if kind in MATCH_KINDS else _other_caption(data)
    if _live(data) or not body:
        return body
    return f"{body}\n\n{SIGN} @Juventus_Reborn"


def safe_build(data):
    """Come build, ma un errore nel testo non deve mai fermare l'invio della foto."""
    try:
        return build(data)
    except Exception as exc:  # noqa: BLE001
        import log
        log.warn('INVIO', f'Didascalia non creata ({type(exc).__name__}: {exc}): invio la foto senza testo')
        return ''
