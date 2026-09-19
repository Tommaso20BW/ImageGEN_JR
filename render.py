"""Adapters to the production graphics core."""
from functools import lru_cache
import json
from pathlib import Path
import shutil
import tempfile

import requests

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
    teams_path = core_dir / 'teams.json'
    manifest_path = (
        core_dir
        / 'assets'
        / 'goal_graphics'
        / 'team_logos'
        / 'fclogo_cache'
        / 'manifest.json'
    )

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
        core_dir = Path(portrait_module.__file__).resolve().parent
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
    def __init__(self, token_provider=None, design_id='DAHI3ytu6yQ'):
        self.token_provider = token_provider
        self.design_id = design_id

    def render(self, data):
        import goal_graphics as g
        import portrait_graphics as p
        from canva_page_one import export_page_one

        kind = data['kind']
        common = {
            **teams(data),
            'kit': data['kit'],
            'competition': data['competition'],
        }
        score = data.get('score') or (0, 0)

        if kind in ('goal', 'saved'):
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

        if kind in ('kick', 'half', 'full', 'end_of_90'):
            layers = None

            if kind != 'kick':
                if not self.token_provider:
                    raise ValueError('Canva non configurato per questa grafica.')

                with tempfile.TemporaryDirectory(prefix='jr_manual_') as cache:
                    with requests.Session() as session:
                        layers = export_page_one(
                            session,
                            self.token_provider(),
                            self.design_id,
                            Path(cache),
                        )

                    phase_args = {
                        **common,
                        'kind': kind,
                        'home_goals': score[0],
                        'away_goals': score[1],
                        'layers': layers,
                    }

                    if kind == 'full' and data.get('shootout'):
                        return _phase_with_translated_shootout(
                            p,
                            shootout=data.get('shootout'),
                            **phase_args,
                        )

                    return p.phase(
                        **phase_args,
                        shootout=None,
                    )

            return p.phase(
                **common,
                kind='kick',
                home_goals=0,
                away_goals=0,
                shootout=None,
                layers=None,
            )

        if kind == 'stats':
            import stats_graphics as stats

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
