"""Testo sotto la foto su Telegram (HTML), come i post del canale Juventus Reborn.

Grafiche della partita (Gol, Half Time, Full Time, Statistiche...): stesso testo dei messaggi
di LiveScore (nomi italiani e hashtag di Impostazioni › Nomi). Le altre (Matchday, XI,
Classifica, Convocati...) seguono i post fatti a mano, con le emoji personalizzate del canale.
Queste ultime finiscono con la firma 👉 @Juventus_Reborn; quelle della diretta no, come sul canale.
Compleanni: auguri con torta e bandiera della nazionale. Post, Storie e Citazioni partono senza testo,
il Rinnovo solo finché non gli scrivi un modello.
Convocati, XI, Here We Go, MOTM e POTM seguono i modelli di Impostazioni › Messaggi (TEMPLATE_KINDS).
"""
import html


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
E_UCL = emoji('5800776293037384533', '🇪🇺')        # Champions League
E_UECL = emoji('5800893141917638105', '🇪🇺')       # Conference League
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
E_CAKE = emoji('5370999492914976897', '🎂')
E_STAR = emoji('5438496463044752972', '⭐️')
E_TOP = emoji('5422354988103901774', '🔝')
E_EYES = emoji('5424885441100782420', '👀')
E_SOURCE = emoji('5785366354106261925', '📲')     # fonte del mercato (📲 Fabrizio Romano)
E_SIGNED = emoji('5470060791883374114', '✍️')
# Fonti delle probabili (stesse emoji del pack usate dal bot delle notizie): nome, emoji, profilo su X.
PXI_SOURCES = {'sky': ('Sky Sport', emoji('5974058122984038105', '📰'), '@SkySport'),
               'gazzetta': ('La Gazzetta dello Sport', emoji('5974032198561439462', '📰'), '@Gazzetta_it')}


# --- Modelli dei messaggi (Impostazioni › Messaggi) ---------------------------------------------
# Testo semplice scritto nella Mini App: **grassetto**, __corsivo__, {segnaposto}. Le emoji del canale
# (☑️ 📝 🆕 ✅ ...) diventano da sole quelle personalizzate. La firma 👉 @Juventus_Reborn si aggiunge sempre.
TEMPLATE_KINDS = {   # tipo -> (nome nella Mini App, testo di base, segnaposto)
    'squad': ('Convocati', '☑️📝 I convocati per {hashtag}.', ('hashtag', 'avversario')),
    'pxi': ('Probabile XI', '🆕📋 𝐏𝐑𝐎𝐁𝐀𝐁𝐈𝐋𝐄 𝐗𝐈 {hashtag}', ('hashtag', 'avversario', 'fonte')),
    'xi': ('XI ufficiale', '✅📋 𝐗𝐈 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄 {hashtag}', ('hashtag', 'avversario')),
    'conv': ('Convocati nazionali', '🌍📋 I bianconeri convocati dalle rispettive nazionali.', ()),
    'af': ('Here We Go', '✅ HERE WE GO: **{giocatore}** alla **Juventus**.\n\n__📲 Fabrizio Romano__', ('giocatore',)),
    'motm': ('MOTM', '⭐️🔝 𝐌𝐎𝐓𝐌 {hashtag}: **{giocatore}**', ('hashtag', 'giocatore')),
    'potm': ('POTM', '📊👀 Il verdetto del sondaggio su __Telegram__ è netto: **{giocatore}** è stato eletto '
                     'miglior giocatore della **Juventus** {mesi}.', ('giocatore', 'mesi')),
    # Come sul canale: 🇦🇷✅ UFFICIALE | Nico Gonzalez rinnova con la Juventus fino al 2030.
    'rin': ('Rinnovo', '{bandiera}✅ **UFFICIALE** | **{giocatore}** rinnova con la **Juventus** fino al {anno}.',
            ('bandiera', 'giocatore', 'anno')),
}
# Gli stessi modelli per X (scheda 𝕏 di Impostazioni › Messaggi), come i post di @Juventus_Reborn:
# emoji normali, niente firma, hashtag al posto del grassetto. {giocatore} = Nick #Woltemade.
X_TEMPLATES = {
    'squad': '☑️📝 I convocati per {hashtag}.',
    'pxi': '🆕📋 𝐏𝐑𝐎𝐁𝐀𝐁𝐈𝐋𝐄 𝐗𝐈 {hashtag}',
    'xi': '✅📋 𝐗𝐈 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄 {hashtag}',
    'conv': '🌍📋 I bianconeri convocati dalle rispettive nazionali.',
    'af': '✅{bandiera} HERE WE GO: {giocatore} alla #Juventus.\n\n📲 @FabrizioRomano',
    'motm': '⭐️🔝 𝐌𝐎𝐓𝐌 {hashtag}: {giocatore}',
    'potm': '📊👀 Il verdetto del sondaggio su Telegram è netto: {giocatore} è stato eletto miglior giocatore '
            'della #Juventus {mesi}.',
    'rin': '✅{bandiera} UFFICIALE | {giocatore} rinnova con la #Juventus fino al {anno}.',
}
X_FIELDS = {'af': ('giocatore', 'bandiera')}      # segnaposto in più nella scheda 𝕏
X_KEY = 'x:'                       # in CUSTOM (e in captions.json) il modello X di un tipo è "x:<tipo>"
TEMPLATE_MAX = 900                 # caratteri: la didascalia di Telegram arriva a 1024, firma compresa
CUSTOM = {}                        # tipo (o x:tipo) -> testo scritto nella Mini App (lo carica il servizio)
PREMIUM = {   # emoji scritta nel modello -> emoji personalizzata del canale
    '☑️': E_CHECK, '📝': E_NOTE, '🆕': E_NEW, '✅': E_OFFICIAL, '🌍': E_WORLD, '📲': E_SOURCE,
    '⭐️': E_STAR, '🔝': E_TOP, '📊': E_STATS, '👀': E_EYES, '📰': E_NEWS, '📆': E_DAY, '🔥': E_FIRE,
    '⚔️': E_VS, '⏰': E_TIME, '📺': E_TV, '🏟': E_HOME, '✈️': E_AWAY, '🆙': E_UP, '🤝': E_FRIENDLY,
    '🎂': E_CAKE, '👉': SIGN, '✍️': E_SIGNED,
}


def clean_template(text):
    """Testo del modello come si salva: a capo uniformi, niente spazi in fondo alle righe."""
    lines = [line.rstrip() for line in str(text or '').replace('\r', '').split('\n')]
    return '\n'.join(lines).strip()[:TEMPLATE_MAX]


def template_text(kind, x=False):
    """Modello in uso (Telegram, o X con x=True): quello scritto nella Mini App, o quello di base."""
    if x:
        return CUSTOM.get(X_KEY + kind) or X_TEMPLATES[kind]
    return CUSTOM.get(kind) or TEMPLATE_KINDS[kind][1]


def template_key(key):
    """Chiave salvata valida (squad, x:squad...) o None."""
    key = str(key or '')
    kind = key[len(X_KEY):] if key.startswith(X_KEY) else key
    return key if kind in TEMPLATE_KINDS else None


def template_default(key):
    return X_TEMPLATES[key[len(X_KEY):]] if key.startswith(X_KEY) else TEMPLATE_KINDS[key][1]


def _premium(text):
    import re
    keys = {plain.replace('️', ''): tag for plain, tag in PREMIUM.items()}   # con o senza variante
    pattern = '|'.join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    return re.sub(f'(?:{pattern})️?', lambda m: keys[m.group(0).replace('️', '')], text)


def render_template(text, values):
    """Modello -> HTML di Telegram: escape, emoji del canale, **grassetto**, __corsivo__, {segnaposto}.
    `values` sono già HTML (con l'escape); un segnaposto sconosciuto resta com'è."""
    import re
    out = _premium(esc(text))
    out = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', out, flags=re.S)
    out = re.sub(r'__(.+?)__', r'<i>\1</i>', out, flags=re.S)
    return re.sub(r'\{(\w+)\}', lambda m: values.get(m.group(1).lower(), m.group(0)), out)


def _from_template(kind, **values):
    return render_template(template_text(kind), values)


def templates_list():
    """Per la Mini App: ogni modello con il testo in uso, quello di base e i segnaposto, per Telegram e per X."""
    return [{'kind': k, 'name': name, 'text': template_text(k), 'default': base, 'fields': list(fields),
             'custom': k in CUSTOM,
             'x': {'text': template_text(k, x=True), 'default': X_TEMPLATES[k],
                   'fields': list(X_FIELDS.get(k, fields)), 'custom': X_KEY + k in CUSTOM}}
            for k, (name, base, fields) in TEMPLATE_KINDS.items()]

# Bandiere animate del canale (codice ISO -> emoji personalizzata); le altre nazioni hanno la bandiera normale.
FLAGS = {
    'IT': '5449723275628259037', 'AR': '5262873863036872166', 'BR': '5202074005346983800',
    'FR': '5202132623060640759', 'PT': '5382075788369605892', 'NL': '5411124743841524806',
    'NO': '5382300771641470186', 'DK': '5381854399985366436', 'CA': '5382084502858249131',
    'DE': '5409360418520967565', 'ES': '5201957744877248121', 'BE': '5411564862025244994',
    'SE': '5384542551296455687', 'TR': '5226948110873278599', 'ME': '5440827745523216914',
    'GR': '5381889099026149370', 'HU': '5409065547541260699', 'BA': '5382033281078275575',
    'CL': '5222427035023977899', 'CO': '5341564321098907092', 'UY': '5269256068474616775',
    'CZ': '5429496861587156146',
}

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
    'SA': (E_ITA, 'Serie A'), 'UCL': (E_UCL, 'UCL'), 'UEL': (E_UEFA, 'UEL'), 'UECL': (E_UECL, 'UECL'),
}
BRACKET_NAMES = {'UCL': 'Champions League', 'UEL': 'Europa League', 'UECL': 'Conference League'}
# Matchday: emoji della competizione e canale TV di solito (la Mini App non chiede la TV).
MD_COMPETITION = {'ita.1': E_ITA, 'ita.coppa_italia': E_CI, 'uefa.champions': E_UCL, 'uefa.europa': E_UEFA,
                  'uefa.europa.conf': E_UECL, 'club.friendly': E_FRIENDLY}
MD_TV = {'ita.1': 'DAZN', 'ita.coppa_italia': 'Mediaset', 'ita.super_cup': 'Mediaset',
         'uefa.champions': 'Sky Sport', 'uefa.europa': 'Sky Sport', 'uefa.europa.conf': 'Sky Sport',
         'uefa.super_cup': 'Sky Sport', 'club.friendly': 'Juventus.com'}
TV_CUSTOM = {}     # Impostazioni › Matchday: canale scritto nella Mini App (competizione -> canale)
TV_MAX = 30


def clean_tv(value):
    return ' '.join(str(value or '').split())[:TV_MAX]


def tv_for(competition):
    return TV_CUSTOM.get(competition) or MD_TV.get(competition, '')


def tv_list():
    """Per la Mini App: ogni competizione con il canale in uso e quello di base."""
    return [{'competition': c, 'name': COMPETITION_NAMES.get(c, c), 'tv': tv_for(c), 'default': base,
             'custom': c in TV_CUSTOM} for c, base in MD_TV.items()]
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
        return _from_template('xi', hashtag=m['tag'], avversario=m['away'] if m['juve_home'] else m['home'])
    if kind == 'pxi':
        return _with_source(data, _from_template(kind, hashtag=m['tag'],
                                                 avversario=m['away'] if m['juve_home'] else m['home']))
    if kind == 'squad':
        return _from_template(kind, hashtag=m['tag'], avversario=m['away'] if m['juve_home'] else m['home'])
    if kind == 'md':
        competition = str(data.get('competition') or '')
        comp_emoji = MD_COMPETITION.get(competition, m['comp'])
        opponent = m['away'] if m['juve_home'] else m['home']
        info = data.get('info') or {}
        place = E_HOME if m['juve_home'] else E_AWAY
        rows = [f"{comp_emoji} {esc(COMPETITION_NAMES.get(competition, ''))}",
                f"{_team_emoji(data)} {opponent}",
                f"{place} {esc(_stadium(info.get('stadium')))}",
                f"{E_TV} {esc(tv_for(competition))}",
                f"{E_TIME} {esc(str(info.get('time') or '').split(' ')[0])}",
                f"{E_PHONE} {m['tag']}"]
        return f"𝐌𝐀𝐓𝐂𝐇𝐃𝐀𝐘 {E_FIRE}{E_VS}\n\n" + '\n'.join(f'<i>{r}</i>' for r in rows if r.split(' ', 1)[-1].strip())
    return ''


def _giornata(comp, module='classifica'):
    """Giornata della classifica (o dei risultati) appena letta da Diretta.it per la grafica (None se non c'è)."""
    try:
        import importlib
        value = int((importlib.import_module(f'graphics.{module}')._last.get(comp) or {}).get('giornata') or 0)
    except Exception:  # noqa: BLE001
        return None
    return value or None


def flag(code):
    """Bandiera della nazione (codice ISO o GB-ENG/GB-SCT/GB-WLS): animata se il canale ce l'ha."""
    code = str(code or '').upper()
    if code.startswith('GB-'):
        plain = '\U0001F3F4' + ''.join(chr(0xE0000 + ord(ch)) for ch in ('gb' + code[3:]).lower()) + '\U000E007F'
    elif len(code) == 2 and code.isalpha():
        plain = ''.join(chr(0x1F1E6 + ord(ch) - ord('A')) for ch in code)
    else:
        return ''
    return emoji(FLAGS[code], plain) if code in FLAGS else plain


def _face(name):
    """Faccia del tesserato nel JR Pack (scelta a mano o di base), o ''."""
    try:
        import player_emoji
        hit = player_emoji.find(name)
    except Exception:  # noqa: BLE001
        hit = None
    return emoji(hit[0], hit[1]) if hit else ''


def _person_name(text):
    """Nome per il testo: le parole scritte in maiuscolo sulla grafica in Title Case, una per una
    (Kenan YILDIZ -> Kenan Yildiz); quelle già scritte bene (McKennie) restano come sono."""
    return ' '.join(w.title() if w.isupper() else w for w in str(text or '').split())


def _roster_name(text):
    """Nome sulla maglia (YILDIZ, GONZALEZ) -> nome della rosa (Kenan Yildiz, Nico Gonzalez), se è uno solo."""
    shown = _person_name(text)
    try:
        from livescore.graphics import goal as g
        q = g.normalize_name(text)
        hits = []
        for p in g.load_players():
            names = [g.normalize_name(n) for n in (p.name, *p.aliases)]
            if q in names:
                return p.name
            if q and any(n.split()[-1:] == [q] or n.endswith(' ' + q) for n in names):
                hits.append(p.name)
        return hits[0] if len(set(hits)) == 1 else shown
    except Exception:  # noqa: BLE001 - senza rosa resta il nome della maglia
        return shown


def _player_icon(name):
    """Faccia del giocatore nel JR Pack, altrimenti la bandiera della nazionale, altrimenti niente."""
    face = _face(name)
    if face:
        return face
    try:
        from graphics import compleanno
        return flag(compleanno.nationality(name))
    except Exception:  # noqa: BLE001
        return ''


def _bday_caption(data):
    """Come gli auguri del canale: 🎂🇦🇷 Tanti auguri a <b>Paulo Dybala!</b>"""
    name = _person_name(data.get('player') or data.get('name'))
    if not name:
        return ''
    prep = 'ad' if name[:1].lower() == 'a' else 'a'
    face = _face(name)
    if face:
        icons = face + E_CAKE
    else:
        try:
            from graphics import compleanno
            code = compleanno.nationality(name)
        except Exception:  # noqa: BLE001 - senza rete si manda senza bandiera
            code = None
        icons = E_CAKE + flag(code)
    return f"{icons} Tanti auguri {prep} <b>{html.escape(name)}!</b>"


def _who(data):
    """Nome e cognome della grafica (scritti in maiuscolo) in Title Case: KERIM ALAJBEGOVIĆ -> Kerim Alajbegović."""
    return _person_name(' '.join(str(data.get(k) or '') for k in ('name', 'surname')).strip())


def _poll_year(months, today=None):
    """Anno dei mesi del sondaggio: quello di oggi, o il precedente se i mesi devono ancora venire
    (sondaggio di dicembre pubblicato a gennaio)."""
    import datetime
    today = today or datetime.date.today()
    nums = [MONTHS.index(m.upper()) + 1 for m in months if m.upper() in MONTHS]
    return today.year - 1 if nums and min(nums) > today.month else today.year


def _motm_tag(data):
    """Hashtag della partita del MOTM (#JuveNapoli) dalle squadre scritte nella grafica."""
    from livescore.core import team_names
    teams = []
    for side in ('home', 'away'):
        name = ' '.join(str(data.get(side) or '').split())
        teams.append(_espn_key([name, name.title()]) or name.title())
    return team_names.build_hashtag(*teams)


def _potm_span(data):
    """Mesi del sondaggio: "nei mesi di agosto e settembre 2026" / "nel mese di ottobre 2026"."""
    months = [m.strip().lower() for m in str(data.get('month') or '').split('/') if m.strip()]
    when = ' e '.join(filter(None, [', '.join(months[:-1]), months[-1] if months else '']))
    span = f"nei mesi di {when}" if len(months) > 1 else f"nel mese di {when}"
    return f"{span} {_poll_year(months)}"


def _other_caption(data):
    kind = data['kind']
    if kind in ('bday', 'bdold'):
        return _bday_caption(data)
    if kind == 'motm':
        # come sul canale: ⭐️🔝 𝐌𝐎𝐓𝐌 #JuveNapoli: <b>Kerim Alajbegovic</b>
        return _from_template('motm', hashtag=_motm_tag(data), giocatore=html.escape(_who(data)))
    if kind == 'potm':
        # come sul canale: 📊👀 Il verdetto del sondaggio su <i>Telegram</i> è netto: <b>Nico Gonzalez</b> è stato
        # eletto miglior giocatore della <b>Juventus</b> nei mesi di agosto e settembre 2026.
        return _from_template('potm', giocatore=html.escape(_who(data)), mesi=html.escape(_potm_span(data)))
    if kind == 'af':
        # ✅ HERE WE GO: <b>Neto</b> alla <b>Juventus</b>.  +  📲 Fabrizio Romano (senza bandiera)
        return _from_template('af', giocatore=html.escape(_who(data)))
    if kind == 'rin':
        name = _roster_name(data.get('name'))
        return _from_template('rin', bandiera=_player_icon(name), giocatore=esc(name), anno=esc(data.get('year')))
    if kind == 'free':
        return html.escape(str(data.get('caption') or '').strip())      # testo scritto a mano, o niente
    if kind == 'table':
        comp = str(data.get('competition') or '').upper()
        if comp == 'CI' or (data.get('view') == 'bracket' and comp not in BRACKET_NAMES):
            return f"{E_CI}{E_UP} Tabellone<b> Coppa Italia </b>aggiornato."
        flag, name = TABLES.get(comp, ('', ''))
        if data.get('view') == 'results':
            text = f"{flag}⚽️<b> {name} | Risultati</b>"
            round_ = _giornata(comp, 'risultati')
            return text + (f"\n{E_DAY}<i> {round_}ª Giornata</i>" if round_ else '')
        if data.get('view') == 'bracket':        # coppe europee: come quello della Coppa Italia
            return f"{flag}{E_UP} Tabellone<b> {BRACKET_NAMES[comp]} </b>aggiornato."
        text = f"{flag}{E_STATS}<b> {name} | Classifica</b>"
        round_ = _giornata(comp)
        return text + (f"\n{E_DAY}<i> {round_}ª Giornata</i>" if round_ else '')
    if kind == 'conv':
        return _from_template('conv')
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
X_LIVE_KINDS = {'half', 'end_of_90', 'full'}      # su X solo le fine dei tempi


# Post (testo scritto ogni volta a mano), Storie e Citazioni (per Instagram, X, Threads): niente testo.
NO_CAPTION = {'jr', 'igbn', 'igq', 'igc', 'xq', 'thq'}


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


# --- Testi da copiare (messaggi a parte dopo la foto): uno per X, uno per Telegram/IG ----------------
# X come i post di @Juventus_Reborn: emoji normali, niente grassetto né firma; squadre, cognomi,
# allenatore e competizione con l'hashtag, il canale TV con la sua pagina (📺 @DAZN_IT).
SIGN_PLAIN = '👉 @Juventus_Reborn'
X_FLAGS = {'ita.1': '🇮🇹', 'ita.coppa_italia': '🇮🇹', 'ita.super_cup': '🇮🇹', 'uefa.champions': '🇪🇺',
           'uefa.europa': '🇪🇺', 'uefa.europa.conf': '🇪🇺', 'uefa.super_cup': '🇪🇺', 'fifa.cwc': '🌍',
           'club.friendly': '🤝'}
X_TABLES = {'SA': ('🇮🇹', '#SerieA'), 'UCL': ('🇪🇺', '#UCL'), 'UEL': ('🇪🇺', '#UEL'), 'UECL': ('🇪🇺', '#UECL')}
X_TV = {'DAZN': '@DAZN_IT', 'Sky Sport': '@SkySport'}       # come sul profilo; gli altri restano scritti


def plain(text):
    """HTML di Telegram -> testo semplice da copiare (Instagram, Telegram): emoji normali, niente tag."""
    import re
    text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', str(text or ''), flags=re.S)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    lines = [line.rstrip() for line in text.split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def x_tag(name):
    """Nome -> hashtag di X: "Kolo Muani" -> #KoloMuani, "I. Saibari" -> #Saibari."""
    import re
    words = [w for w in str(name or '').split() if not re.fullmatch(r'\w\.', w)]
    word = re.sub(r"[\s'’.\-]", '', ''.join(words))
    return f'#{word}' if word else ''


def x_person(name):
    """Nome e cognome come su X: Nick #Woltemade, Alessandro #DelPiero; un nome solo: #Neto."""
    words = str(name or '').split()
    if len(words) < 2:
        return x_tag(name)
    return f"{words[0]} {x_tag(' '.join(words[1:]))}"


def _with_source(data, text, x=False):
    """Probabili prese da Sky o Gazzetta: in fondo la fonte con la sua icona, come 📲 Fabrizio Romano
    (Telegram: corsivo con l'emoji del pack; X: 📲 @SkySport, come tutte le fonti). Se il modello ha {fonte}, va li'."""
    source = PXI_SOURCES.get(str(data.get('source') or ''))
    line = '' if not source else (f'📲 {source[2]}' if x else f'<i>{source[1]} {esc(source[0])}</i>')
    if '{fonte}' in text:
        return text.replace('{fonte}', line).strip()
    return f'{text}\n\n{line}' if line else text


def _x_template(kind, **values):
    """Modello per X (Impostazioni › Messaggi, scheda 𝕏): testo semplice, segnaposto già pronti."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', template_text(kind, x=True), flags=re.S)
    text = re.sub(r'__(.+?)__', r'\1', text, flags=re.S)
    return re.sub(r'\{(\w+)\}', lambda m: values.get(m.group(1).lower(), m.group(0)), text).strip()


def _nation_flag(name):
    """Bandiera normale della nazionale del giocatore ('' se non si sa)."""
    try:
        from graphics import compleanno
        return plain(flag(compleanno.nationality(name)))
    except Exception:  # noqa: BLE001 - senza rete niente bandiera
        return ''


def _x_match(data):
    kind = data['kind']
    m = _match(data)
    tag = html.unescape(m['tag'])
    home, away = html.unescape(m['home']), html.unescape(m['away'])
    opponent = away if m['juve_home'] else home
    competition = str(data.get('competition') or '')
    if kind == 'pxi' and data.get('team') != 'italy':
        return _with_source(data, _x_template(kind, hashtag=tag, avversario=x_tag(opponent)), x=True)
    if kind in ('squad', 'xi') and data.get('team') != 'italy':
        return _x_template(kind, hashtag=tag, avversario=x_tag(opponent))
    if kind == 'md':
        info = data.get('info') or {}
        tv = tv_for(competition)
        name = COMPETITION_NAMES.get(competition, '')
        name = name if competition == 'club.friendly' else x_tag(name)      # 🤝 Amichevole, senza hashtag
        rows = [f"{X_FLAGS.get(competition, plain(m['comp']))} {name}",
                f"🆚 {x_tag(opponent)}",
                f"{'🏟' if m['juve_home'] else '✈️'} {_stadium(info.get('stadium'))}",
                f"📺 {X_TV.get(tv, tv)}",
                f"⏰ {str(info.get('time') or '').split(' ')[0]}",
                f"📲 {tag}"]
        return '𝐌𝐀𝐓𝐂𝐇𝐃𝐀𝐘 🔥⚔️\n\n' + '\n'.join(r for r in rows if r.split(' ', 1)[-1].strip())
    if kind in PHASES:
        # come la diretta su X: squadre con l'hashtag (#Juventus 4-1 #Omonia)
        import re
        lines = plain(_match_caption(data)).split('\n')
        for i, line in enumerate(lines):
            if re.search(r'\d+(?: \(\d+\))?-(?:\(\d+\) )?\d+', line) or (kind == 'kick' and ' - ' in line):
                for name in sorted({home, away}, key=len, reverse=True):
                    line = re.sub(rf'(?<![#\w]){re.escape(name)}(?!\w)', x_tag(name), line)
                lines[i] = line
        return '\n'.join(lines)
    return None


def _x_other(data):
    import re
    kind = data['kind']
    if kind in ('bday', 'bdold'):
        # 🎂🇮🇹 Tanti auguri a Vincenzo #Iaquinta!
        name = _person_name(data.get('player') or data.get('name'))
        if not name:
            return ''
        return f"🎂{_nation_flag(name)} Tanti auguri {'ad' if name[:1].lower() == 'a' else 'a'} {x_person(name)}!"
    if kind == 'motm':
        return _x_template('motm', hashtag=html.unescape(_motm_tag(data)), giocatore=x_person(_who(data)))
    if kind == 'af':
        # ✅🇧🇷 HERE WE GO: #Neto alla #Juventus.
        return _x_template('af', bandiera=_nation_flag(_who(data)), giocatore=x_person(_who(data)))
    if kind == 'rin':
        name = _roster_name(data.get('name'))
        return _x_template('rin', bandiera=_nation_flag(name), giocatore=x_person(name),
                           anno=str(data.get('year') or ''))
    if kind == 'conv':
        return _x_template('conv')
    if kind == 'potm':
        return _x_template('potm', giocatore=x_person(_who(data)), mesi=_potm_span(data))
    if kind == 'table':
        comp = str(data.get('competition') or '').upper()
        if comp == 'CI' or (data.get('view') == 'bracket' and comp not in BRACKET_NAMES):
            return '🆙🇮🇹 Tabellone #CoppaItalia aggiornato.'
        icon, name = X_TABLES.get(comp, ('', ''))
        if data.get('view') == 'bracket':
            return f"🆙{icon} Tabellone {x_tag(BRACKET_NAMES[comp])} aggiornato."
        results = data.get('view') == 'results'
        text = f"{'⚽️' if results else '📊'}{icon} {name} | {'Risultati' if results else 'Classifica'}"
        round_ = _giornata(comp, 'risultati' if results else 'classifica')
        return text + (f"\n📆 {round_}ª Giornata" if round_ else '')
    return None


def x_text(data, telegram_text=None):
    """Testo per X della grafica ('' se non ne ha). Senza una regola apposta: il testo Telegram
    semplice, senza firma."""
    if data.get('kind') in NO_CAPTION:
        return ''
    telegram_text = build(data) if telegram_text is None else telegram_text
    if not telegram_text:
        return ''
    try:
        text = _x_match(data) if data['kind'] in MATCH_KINDS else _x_other(data)
    except Exception:  # noqa: BLE001 - una regola rotta: resta il testo Telegram
        text = None
    if text is None:
        text = plain(telegram_text)
        if text.endswith(SIGN_PLAIN):
            text = text[:-len(SIGN_PLAIN)].rstrip()
    return text.strip()


def copy_messages(data, telegram_text):
    """Messaggi da copiare dopo la foto (HTML di Telegram), senza scritte sopra:
    (testo IG/Telegram così com'è, emoji personalizzate comprese;
     testo per X come testo normale, da mandare in risposta, '' se non serve).
    ('', '') se la foto non ha testo."""
    if not telegram_text:
        return '', ''
    # Della partita su X vanno solo le fine dei tempi: gol, parate, inizi e statistiche no.
    x = '' if data.get('kind') in LIVE_KINDS - X_LIVE_KINDS else x_text(data, telegram_text)
    return telegram_text.strip(), (html.escape(x, quote=False) if x else '')
