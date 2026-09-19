"""Adapters to the production graphics core. Canva-free version."""
from pathlib import Path
import shutil

from .constants import COMPETITIONS


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


class Renderer:
    def render(self, data):
        import goal_graphics as g
        import portrait_graphics as p

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

        if kind == 'kick':
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

        raise ValueError('Tipo grafica non supportato in modalità senza Canva')
