"""Adapters to the production graphics core."""
from functools import lru_cache
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading


from constants import COMPETITIONS


def teams(data):
    opponent = data['opponent']
    juve = {'name': 'Juventus', 'id': '111'}
    home, away = (
        (juve, opponent)
        if data['side'] == 'home'
        else (opponent, juve)
    )
    return {
        'home_name': home['name'],
        'home_id': home.get('id', ''),
        'away_name': away['name'],
        'away_id': away.get('id', ''),
    }


def _name_key(value):
    return ' '.join(str(value or '').casefold().split())


@lru_cache(maxsize=4)
def _team_display_names(core_dir_text):
    """Build display-name aliases from the LiveScore translation table.

    Example:
      AC Milan -> Milan
      FC Inter Milan -> Inter  (via manifest alias "Internazionale")
    """
    core_dir = Path(core_dir_text)
    teams_path = core_dir / 'data' / 'teams.json'
    logos_dir = core_dir / 'assets' / 'goal_graphics' / 'team_logos'
    manifest_path = logos_dir / 'manifest.json'
    if not manifest_path.is_file():
        manifest_path = logos_dir / 'fclogo_cache' / 'manifest.json'

    translated = {}

    try:
        payload = json.loads(teams_path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        payload = {}

    if isinstance(payload, dict):
        for source_name, values in payload.items():
            display = None
            if isinstance(values, (list, tuple)) and values:
                display = values[0]
            elif isinstance(values, str):
                display = values

            if display:
                translated[_name_key(source_name)] = str(display).strip()

    aliases = dict(translated)

    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        rows = manifest.get('teams', []) if isinstance(manifest, dict) else []
    except (OSError, ValueError, TypeError):
        rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        variants = [
            row.get('name'),
            *(row.get('aliases') or []),
        ]
        variants = [str(value).strip() for value in variants if value]

        display = None
        for variant in variants:
            display = translated.get(_name_key(variant))
            if display:
                break

        if display:
            for variant in variants:
                aliases[_name_key(variant)] = display

    return aliases


def translated_team_name(name, portrait_module):
    try:
        core_dir = Path(portrait_module.__file__).resolve().parents[2]
        return _team_display_names(str(core_dir)).get(
            _name_key(name),
            str(name),
        )
    except Exception:
        return str(name)


def _phase_with_translated_shootout(p, *, shootout=None, **kwargs):
    """Render a phase while translating only the shootout winner caption.

    Team names used for crest resolution stay untouched. Only the textual
    "X VINCE ... AI RIGORI" line is translated.
    """
    if not shootout:
        return p.phase(shootout=shootout, **kwargs)

    original_number = p.number

    def number_with_translated_winner(value, *args, **number_kwargs):
        text = str(value)
        marker = ' VINCE '

        if marker in text and text.endswith(' AI RIGORI'):
            winner, rest = text.split(marker, 1)
            display = translated_team_name(winner, p)
            text = f'{display}{marker}{rest}'.upper()

        return original_number(text, *args, **number_kwargs)

    p.number = number_with_translated_winner
    try:
        return p.phase(shootout=shootout, **kwargs)
    finally:
        p.number = original_number


class Renderer:
    def __init__(self):
        # Foto caricate dalla Mini App (id -> byte), riempito da service.Service.
        self.photos = {}
        # Persone scontornate (id foto -> PNG), riusate da anteprima e invio.
        self.cutouts = {}
        self.cutout_lock = threading.Lock()

    def cutout(self, photo_id):
        """Persona scontornata da una foto caricata (PNG, calcolata una volta sola)."""
        from livescore.graphics import phase_layers

        with self.cutout_lock:
            if photo_id not in self.cutouts:
                raw = self.photos.get(photo_id)
                if not raw:
                    raise ValueError('Foto non trovata: ricaricala nella Mini App.')
                image = phase_layers.open_photo(raw)
                if phase_layers.has_transparency(image):
                    # PNG già scontornato caricato come persona: resta com'è.
                    self.cutouts[photo_id] = raw
                else:
                    out = io.BytesIO()
                    phase_layers.cutout(image).save(out, 'PNG')
                    self.cutouts[photo_id] = out.getvalue()
                while len(self.cutouts) > 6:
                    self.cutouts.pop(next(iter(self.cutouts)))
            return self.cutouts[photo_id]

    def _photo(self, data):
        photo = self.photos.get(data.get('photo_id'))
        if not photo:
            raise ValueError('Foto non trovata: ricaricala nella Mini App.')
        return photo

    def render(self, data, progress=None, ghost=False):
        """ghost=True (grafiche con foto): versione leggera senza foto per l'editor."""
        """Render a graphic. `progress(stage)` is called at the real steps of HALF/END/FULL TIME."""
        from livescore.graphics import goal as g
        from livescore.graphics import portrait as p

        def note(stage):
            if progress:
                try:
                    progress(stage)
                except Exception:
                    pass

        kind = data['kind']
        if kind == 'cal':
            from graphics import calendar

            return calendar.render(month=data['month'], matches=data['matches'])

        if kind == 'jr':
            from graphics import photo_jr

            if data.get('style') == 'blur':
                def photo(photo_id):
                    raw = self.photos.get(photo_id)
                    if not raw:
                        raise ValueError('Foto non trovata: ricaricala nella Mini App.')
                    return raw
                return photo_jr.render(
                    color=data['color'], style='blur', ghost=ghost,
                    background=None if ghost else photo(data['background_id']),
                    cards=[] if ghost else [(photo(c['photo_id']), c) for c in data['cards']],
                )
            return photo_jr.render(color=data['color'], photo=None if ghost else self._photo(data),
                                   frame=data['frame'], ghost=ghost)

        common = {
            **teams(data),
            'kit': data['kit'],
            'competition': data['competition'],
        }

        if kind in ('goal', 'saved'):
            # Risultato accanto al minuto (assente nei payload vecchi: la card lo omette).
            score = data.get('score') or (None, None)
            args = {
                **common,
                'minute': data['minute'],
                'home_goals': score[0],
                'away_goals': score[1],
                'pose': data.get('pose', 'arms_crossed'),
            }
            if kind == 'goal':
                return g.render_goal_card(
                    **args,
                    scorer_name=data['player'],
                ).png
            return g.render_saved_card(
                **args,
                goalkeeper_name=data['player'],
            ).png

        if kind in ('half', 'full', 'end_of_90'):
            # Sfondo e persona dalle foto caricate nella Mini App (prima: pagina 1 Canva).
            from livescore.graphics import phase_layers

            score = data.get('score') or (0, 0)
            phase_args = {
                **common,
                'kind': kind,
                'home_goals': score[0],
                'away_goals': score[1],
                'extra_time': kind == 'full' and bool(data.get('extra_time')),
            }
            shootout = data.get('shootout') if kind == 'full' else None

            def draw(layers):
                return _phase_with_translated_shootout(p, shootout=shootout, layers=layers, **phase_args)

            if ghost:
                return phase_layers.ghost(draw)

            note('cutout')
            person = self.cutout(data.get('person_id') or data['photo_id'])
            note('compose')
            with tempfile.TemporaryDirectory(prefix='jr_manual_') as cache:
                layers = phase_layers.build_layers(
                    Path(cache),
                    background=self._photo(data),
                    person=person,
                    background_frame=data['frame'],
                    person_frame=data.get('person_frame'),
                )
                return draw(layers)

        if kind in ('kick', 'second'):
            score = data.get('score') or (0, 0)
            # KICK OFF e 2ND HALF: senza foto (2ND HALF mostra il risultato).
            return p.phase(
                **common,
                kind=kind,
                home_goals=score[0] if kind == 'second' else 0,
                away_goals=score[1] if kind == 'second' else 0,
                shootout=None,
                layers=None,
            )

        if kind == 'xi':
            from graphics import starting_xi

            from graphics.probabili import label_name, plain
            from livescore.graphics import goal as g

            # Nomi dalla rosa -> nome breve come su Canva ("MCKENNIE", "NICO GONZALEZ").
            roster = {p.name: p for p in g.load_players()}
            lineup = [(number, label_name(roster[name]) if name in roster else plain(name))
                      for number, name in data['lineup']]
            return starting_xi.render(
                **teams(data),
                kit=data['kit'],
                lineup=lineup,
                photo=None if ghost else self._photo(data),
                ghost=ghost,
                frame=data['frame'],
            )

        if kind == 'md':
            from graphics import matchday

            return matchday.render(
                **teams(data),
                kit=data['kit'],
                photo=None if ghost else self._photo(data),
                ghost=ghost,
                frame=data['frame'],
                info=data['info'],
                competition=data['competition'],
            )

        if kind == 'pxi':
            from graphics import probabili
            from livescore.graphics import goal as g

            roster = {p.name: p for p in g.load_players()}
            return probabili.render(
                **teams(data),
                kit=data['kit'],
                module=data['module'],
                players=[roster[name] for name in data['players']],
                layout=data.get('layout'),
            )

        if kind == 'squad':
            from graphics import squad_list

            return squad_list.render(
                **teams(data),
                players=data['players'],
                competition=data['competition'],
            )

        if kind == 'stats':
            from livescore.graphics import stats

            html = stats.build_html(
                **common,
                rows=data.get('rows', []),
                momento=data['moment'],
                league_name=dict((v, k) for k, v in COMPETITIONS)[
                    data['competition']
                ],
            )
            target = Path(stats.render(html, hd_output=True))
            try:
                return target.read_bytes()
            finally:
                if (
                    target.name == 'stats.png'
                    and target.parent.name.startswith('jr_stats_')
                ):
                    shutil.rmtree(target.parent)

        raise ValueError('Tipo grafica non supportato')
