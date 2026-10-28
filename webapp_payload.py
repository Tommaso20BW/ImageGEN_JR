"""Validate ImageGEN Mini App requests."""
import json
import math
import re
import uuid

from constants import COMPETITIONS, KINDS, STATS, parse_minute, parse_stat_pair
from graphics.squad_list import BACKGROUNDS as SQUAD_COMPETITIONS, parse_squad
from graphics.starting_xi import PLAYERS as PLAYERS_IN_XI, parse_lineup
from graphics.matchday import parse_info
from graphics.photo_jr import COLORS as JR_COLORS
from graphics import photo_jr
from graphics.calendar import parse_matches

VALID_KINDS = {value for _, value in KINDS}
VALID_COMPETITIONS = {value for _, value in COMPETITIONS}
VALID_KITS = {'home', 'away', 'third'}
VALID_SIDES = {'home', 'away'}
VALID_POSES = {'arms_crossed', 'pointing'}
VALID_MOMENTS = {'HT', '2H_END', 'FT'}
BUSY = {'ready', 'rendering', 'sending'}


def _score(value, *, optional=False, shootout=False):
    if value in (None, '', []):
        if optional:
            return None
        raise ValueError('Risultato mancante.')
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('Risultato non valido.')
    try:
        home, away = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        raise ValueError('Risultato non valido.') from None
    if not (0 <= home <= 99 and 0 <= away <= 99):
        raise ValueError('Risultato fuori intervallo.')
    if shootout and home == away:
        raise ValueError('I rigori devono avere un vincitore.')
    return home, away


def _canonical_team(catalog, value):
    if not isinstance(value, dict):
        raise ValueError('Avversario non valido.')
    name = str(value.get('name') or '').strip()
    if not name:
        raise ValueError('Avversario mancante.')
    matches = catalog.teams(name)
    if not matches:
        raise ValueError('Avversario non presente nel catalogo.')
    exact = [row for row in matches if row['name'].casefold() == name.casefold()]
    return exact[0] if exact else matches[0]


def _canonical_player(catalog, value, *, goalkeeper=False):
    name = str(value or '').strip()
    if not name:
        raise ValueError('Giocatore mancante.')
    matches = catalog.players(name, goalkeeper=goalkeeper)
    if not matches:
        raise ValueError('Giocatore non presente nel catalogo.')
    exact = [candidate for candidate in matches if candidate.casefold() == name.casefold()]
    if exact:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    raise ValueError('Giocatore ambiguo: selezionalo dall’elenco.')


def _lineup_name(catalog, value):
    """Starting XI: nome del catalogo se il giocatore è in rosa, altrimenti il nome scritto."""
    try:
        return _canonical_player(catalog, value)
    except ValueError:
        name = ' '.join(str(value or '').split())
        if not name or len(name) > 30:
            raise ValueError('Nome giocatore non valido.')
        return name


def _photo_id(value):
    value = str(value or '')
    if not re.fullmatch(r'[0-9a-f]{16}', value):
        raise ValueError('Carica una foto.')
    return value


def _frame(value, min_zoom=1.0):
    """Posizione della foto: spostamento del centro (frazione pagina) e zoom."""
    if not isinstance(value, dict):
        raise ValueError('Posizione foto non valida.')
    try:
        frame = {k: float(value.get(k, d)) for k, d in (('x', 0), ('y', 0), ('zoom', 1))}
    except (TypeError, ValueError):
        raise ValueError('Posizione foto non valida.') from None
    if not all(math.isfinite(v) for v in frame.values()):
        raise ValueError('Posizione foto non valida.')
    frame['x'] = max(-3.0, min(3.0, frame['x']))
    frame['y'] = max(-3.0, min(3.0, frame['y']))
    frame['zoom'] = max(min_zoom, min(6.0, frame['zoom']))
    return {k: round(v, 5) for k, v in frame.items()}


def _rows(value):
    if not isinstance(value, list):
        return []
    rows, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('Statistiche non valide.')
        label = str(item.get('label') or '').strip()
        if label not in STATS or label in seen:
            raise ValueError('Statistica non valida.')
        home = str(item.get('home') or '').strip()
        away = str(item.get('away') or '').strip()
        if not home and not away:
            continue
        if not home or not away:
            raise ValueError(f'{label}: inserisci entrambi i valori.')
        pair = parse_stat_pair(f'{home}/{away}')
        if not pair:
            continue
        if label in ('POSSESSO', 'PRECISIONE PASSAGGI'):
            if any(float(v.rstrip('%')) > 100 for v in pair):
                raise ValueError(f'{label}: percentuale oltre 100.')
            pair = tuple(v.rstrip('%') + '%' for v in pair)
        for cell in pair:
            number = float(cell.rstrip('%'))
            if not math.isfinite(number):
                raise ValueError('Statistica non valida.')
        rows.append((label, pair[0], pair[1]))
        seen.add(label)
    return sorted(rows, key=lambda row: STATS.index(row[0]))


def _build_state(envelope, catalog, now, expected_session):
    if not isinstance(envelope, dict):
        raise ValueError('Richiesta non valida.')

    raw_size = len(json.dumps(envelope, ensure_ascii=False).encode('utf-8'))
    if raw_size > 4096:
        raise ValueError('Dati Mini App troppo lunghi.')

    if str(envelope.get('session') or '') != str(expected_session):
        raise ValueError('Sessione non valida.')

    if envelope.get('v') != 1 or envelope.get('action') != 'render':
        raise ValueError('Versione Mini App non supportata.')

    incoming = envelope.get('data')
    if not isinstance(incoming, dict):
        raise ValueError('Richiesta non valida.')

    kind = str(incoming.get('kind') or '')
    competition = str(incoming.get('competition') or '')
    kit = str(incoming.get('kit') or '')
    side = str(incoming.get('side') or '')

    if kind not in VALID_KINDS:
        raise ValueError('Tipo grafica non valido.')

    # CALENDARIO: mese e partite (avversario e casa/trasferta per riga).
    if kind == 'cal':
        try:
            month, year = int(incoming.get('month')), int(incoming.get('year'))
        except (TypeError, ValueError):
            raise ValueError('Mese non valido.') from None
        if not 2000 <= year <= 2100:
            raise ValueError('Anno non valido.')
        rows = incoming.get('matches')
        matches = parse_matches(month, year, rows)
        for match in matches:
            match['opponent'] = _canonical_team(catalog, match['opponent'])
        return {
            'id': uuid.uuid4().hex[:10],
            'data': {'kind': 'cal', 'month': month, 'year': year, 'matches': matches},
            'status': 'ready',
            'updated': now,
            'source': 'webapp-direct',
        }

    # FOTO + JR: niente partita, solo foto e colore del logo.
    if kind == 'jr':
        color = str(incoming.get('color') or '')
        if color not in JR_COLORS:
            raise ValueError('Scegli il colore del JR.')
        style = str(incoming.get('style') or 'classic')
        if style not in photo_jr.STYLES:
            raise ValueError('Stile non valido.')
        if style == 'blur':
            # Sfocata (pagina 26 Canva): 1-4 foto con posizione e larghezza, una è lo sfondo.
            cards = incoming.get('cards')
            if not isinstance(cards, list) or not 1 <= len(cards) <= photo_jr.MAX_CARDS:
                raise ValueError(f'Carica da 1 a {photo_jr.MAX_CARDS} foto.')
            cards = [{'photo_id': _photo_id(c.get('photo_id') if isinstance(c, dict) else None),
                      **photo_jr.clean_card(c)} for c in cards]
            background = _photo_id(incoming.get('background_id'))
            if background not in {c['photo_id'] for c in cards}:
                raise ValueError('Scegli la foto per lo sfondo.')
            jr_data = {'kind': 'jr', 'style': 'blur', 'color': color,
                       'background_id': background, 'cards': cards}
        elif style == 'collage':
            # Collage: da 2 a 9 riquadri già calcolati dalla Mini App, ognuno con la sua foto.
            jr_data = {'kind': 'jr', 'style': 'collage', 'color': color,
                       'cells': photo_jr.clean_cells(incoming.get('cells'), _photo_id)}
        else:
            jr_data = {'kind': 'jr', 'style': 'classic', 'color': color,
                       'photo_id': _photo_id(incoming.get('photo_id')),
                       'frame': _frame(incoming.get('frame'))}
        return {
            'id': uuid.uuid4().hex[:10],
            'data': jr_data,
            'status': 'ready',
            'updated': now,
            'source': 'webapp-direct',
        }
    if competition not in VALID_COMPETITIONS:
        raise ValueError('Competizione non valida.')
    if kit not in VALID_KITS:
        raise ValueError('Kit non valido.')
    if side not in VALID_SIDES:
        raise ValueError('Casa/trasferta non valido.')

    data = {
        'kind': kind,
        'competition': competition,
        'kit': kit,
        'side': side,
        'opponent': _canonical_team(catalog, incoming.get('opponent')),
    }

    if kind in ('goal', 'saved'):
        data['player'] = _canonical_player(
            catalog,
            incoming.get('player'),
            goalkeeper=(kind == 'saved'),
        )
        data['minute'] = parse_minute(str(incoming.get('minute') or ''))
        # Score shown next to the minute on the card; older clients may not send it.
        data['score'] = _score(incoming.get('score'), optional=True)
        pose = str(incoming.get('pose') or '')
        if pose not in VALID_POSES:
            raise ValueError('Posa non valida.')
        data['pose'] = pose

    elif kind in ('second', 'half', 'full', 'end_of_90'):
        data['score'] = _score(incoming.get('score'))
        if kind != 'second':
            # Sfondo (foto) + persona: scontornata dalla foto stessa (person_id
            # assente) o caricata a parte; person_frame assente = segue lo sfondo.
            data['photo_id'] = _photo_id(incoming.get('photo_id'))
            data['frame'] = _frame(incoming.get('frame'))
            person_id = incoming.get('person_id')
            data['person_id'] = _photo_id(person_id) if person_id else None
            person_frame = incoming.get('person_frame')
            data['person_frame'] = _frame(person_frame, min_zoom=0.2) if person_frame else None
        if kind == 'full':
            # Spunta "Supplementari": solo dicitura sotto il risultato.
            data['extra_time'] = incoming.get('extra_time') is True
            data['shootout'] = _score(
                incoming.get('shootout'),
                optional=True,
                shootout=True,
            )

    elif kind == 'xi':
        lineup = parse_lineup(incoming.get('lineup'))
        if isinstance(incoming.get('lineup'), list):
            # Chi è in rosa prende il nome del catalogo; gli altri restano come scritti.
            lineup = [(number, _lineup_name(catalog, name)) for number, name in lineup]
            if len({name for _n, name in lineup}) != PLAYERS_IN_XI:
                raise ValueError('Lo stesso giocatore è stato scelto due volte.')
        data['lineup'] = lineup
        data['photo_id'] = _photo_id(incoming.get('photo_id'))
        data['frame'] = _frame(incoming.get('frame'))

    elif kind == 'md':
        data['photo_id'] = _photo_id(incoming.get('photo_id'))
        data['frame'] = _frame(incoming.get('frame'))
        data['info'] = parse_info(incoming.get('stadium'), incoming.get('time'), incoming.get('date'))

    elif kind == 'pxi':
        module = str(incoming.get('module') or '')
        import layouts as _layouts
        if not _layouts.exists(module):
            raise ValueError('Modulo non valido.')
        names = incoming.get('players')
        if not isinstance(names, list) or len(names) != 11:
            raise ValueError('Scegli 11 giocatori.')
        players = [_canonical_player(catalog, n) for n in names]
        if len(set(players)) != 11:
            raise ValueError('Lo stesso giocatore è stato scelto due volte.')
        data['module'] = module
        data['players'] = players
        # Disposizione di "Modifica" (assente = salvata o Canva).
        if incoming.get('layout') is not None:
            import layouts
            data['layout'] = layouts.clean(module, incoming.get('layout'))

    elif kind == 'squad':
        if competition not in SQUAD_COMPETITIONS:
            raise ValueError('Squad List solo per Serie A, Coppa Italia ed Europa League.')
        data['players'] = parse_squad(incoming.get('squad'))

    elif kind == 'stats':
        moment = str(incoming.get('moment') or '')
        if moment not in VALID_MOMENTS:
            raise ValueError('Momento statistiche non valido.')
        data['moment'] = moment
        data['rows'] = _rows(incoming.get('rows'))
        if not data['rows']:
            raise ValueError('Inserisci almeno una statistica.')

    return {
        'id': uuid.uuid4().hex[:10],
        'data': data,
        'status': 'ready',
        'updated': now,
        'source': 'webapp-direct',
    }


def parse_webapp_request(envelope, catalog, now, expected_session):
    return _build_state(
        envelope,
        catalog,
        now,
        expected_session,
    )


def parse_webapp_envelope(state, envelope, catalog, now, expected_session):
    if state.get('status') in BUSY:
        return state, [{
            'text': 'Sto già generando una grafica. Attendi il PNG prima di inviarne un’altra.'
        }]

    try:
        return parse_webapp_request(
            envelope,
            catalog,
            now,
            expected_session,
        ), []
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return state, [{'text': f'Mini App: {exc}'}]


def parse_webapp_update(state, update, catalog, now, expected_session):
    """Legacy Telegram web_app_data parser, kept only for compatibility/tests."""
    try:
        message = update.get('message') or {}
        raw = str((message.get('web_app_data') or {}).get('data') or '')
        if not raw or len(raw.encode('utf-8')) > 4096:
            raise ValueError('Dati Mini App mancanti o troppo lunghi.')
        envelope = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return state, [{'text': f'Mini App: {exc}'}]

    return parse_webapp_envelope(
        state,
        envelope,
        catalog,
        now,
        expected_session,
    )
