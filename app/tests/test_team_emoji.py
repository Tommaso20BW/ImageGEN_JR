import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import _percorsi  # noqa: F401
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import caption
import emoji_squadre as es
import team_emoji


def png(shape, colour, size=100):
    im = Image.new('RGBA', (size, size))
    d = ImageDraw.Draw(im)
    box = (10, 10, size - 10, size - 10)
    if shape == 'circle':
        d.ellipse(box, fill=colour)
    elif shape == 'square':
        d.rectangle(box, fill=colour)
    else:
        d.polygon([(size // 2, 8), (size - 8, size - 8), (8, size - 8)], fill=colour)
    out = io.BytesIO()
    im.save(out, 'PNG')
    return out.getvalue()


RED_CIRCLE = png('circle', (220, 20, 30))
BLUE_SQUARE = png('square', (20, 40, 200))
GREEN_TRI = png('tri', (20, 160, 60))
LEC = {'slug': 'lecce', 'name': 'US Lecce', 'aliases': ['Lecce']}


class Assets:
    """Cartella asset finta con auto.json / emoji.json."""

    def __init__(self, auto=None, manual=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        if auto is not None:
            es.write_json(self.path / team_emoji.AUTO, {'packs': {}, 'teams': auto})
        if manual is not None:
            es.write_json(self.path / team_emoji.MANUAL, {'version': 1, 'teams': manual})

    def __enter__(self):
        self.old = os.environ.get('IMAGEGEN_ASSETS')
        os.environ['IMAGEGEN_ASSETS'] = str(self.path)
        return self.path

    def __exit__(self, *exc):
        if self.old is None:
            os.environ.pop('IMAGEGEN_ASSETS', None)
        else:
            os.environ['IMAGEGEN_ASSETS'] = self.old
        self.tmp.cleanup()


AUTO = {'lecce': {'name': 'US Lecce', 'aliases': ['US Lecce', 'Lecce'], 'id': '111', 'emoji': '🇮🇹',
                  'pack': 'AroundJuventus', 'index': 95}}


class LookupTest(unittest.TestCase):
    def test_auto_by_slug_and_by_name(self):
        with Assets(AUTO) as a:
            self.assertEqual(team_emoji.find(LEC, a), ('111', '🇮🇹'))
            self.assertEqual(team_emoji.find({'name': 'Lecce'}, a), ('111', '🇮🇹'))
            self.assertIsNone(team_emoji.find({'name': 'Pisa'}, a))

    def test_manual_choice_wins(self):
        with Assets(AUTO, {'lecce': {'id': '222', 'emoji': '⚽', 'pack': 'ItalianFootballEmoji', 'index': 4}}) as a:
            self.assertEqual(team_emoji.find(LEC, a), ('222', '⚽'))
        with Assets(AUTO, {'lecce': {'none': True}}) as a:
            self.assertIsNone(team_emoji.find(LEC, a))

    def test_matchday_uses_team_emoji(self):
        data = {'kind': 'md', 'competition': 'ita.1', 'side': 'away', 'opponent': LEC, 'info': {}}
        with Assets(AUTO):
            self.assertIn('<i><tg-emoji emoji-id="111">🇮🇹</tg-emoji> Lecce</i>', caption.build(data))
        with Assets({}):
            self.assertIn('<i>🆚 Lecce</i>', caption.build(data))

    def test_save_manual_choice(self):
        with Assets(AUTO) as a:
            es.write_json(a / team_emoji.PACKS, es.pack_index({'ItalianFootballEmoji': [{'id': '333', 'emoji': '🇮🇹', 'index': 7}]}))
            result = team_emoji.save({'key': 'lecce', 'name': 'Lecce', 'pack': 'ItalianFootballEmoji', 'index': 7}, a, env={})
            self.assertFalse(result['remote'])          # niente token: salvata solo qui
            self.assertEqual(team_emoji.find(LEC, a), ('333', '🇮🇹'))
            team_emoji.save({'key': 'lecce', 'reset': True}, a, env={})
            self.assertEqual(team_emoji.find(LEC, a), ('111', '🇮🇹'))
            with self.assertRaises(ValueError):
                team_emoji.save({'key': 'lecce', 'pack': 'ItalianFootballEmoji', 'index': 99}, a, env={})


    def test_team_page(self):
        auto = {'lecce': {**AUTO['lecce'], 'pack': 'ItalianFootballEmoji', 'index': 7, 'id': '333',
                          'suggest': [{'id': '333', 'score': 0.99}, {'id': '444', 'score': 0.95}, {'id': '555', 'score': 0.6}]}}
        with Assets(auto) as a:
            es.write_json(a / team_emoji.PACKS, es.pack_index({'ItalianFootballEmoji': [
                {'id': '333', 'emoji': '🇮🇹', 'index': 7}, {'id': '444', 'index': 8}, {'id': '555', 'index': 9}]}))
            page = team_emoji.team_detail({'name': 'Lecce'}, a)
            self.assertEqual(page['key'], 'lecce')
            self.assertEqual((page['current']['pack'], page['current']['index']), ('ItalianFootballEmoji', 7))
            self.assertEqual(page['current']['name'], 'Italia')
            self.assertEqual([c['index'] for c in page['suggest']], [7, 8])     # 60%: troppo diversa
            self.assertEqual(page['packs'], [{'pack': 'ItalianFootballEmoji', 'name': 'Italia', 'count': 3}])


class MonthlyCheckTest(unittest.TestCase):
    TEAMS = [{'slug': 'red', 'name': 'Rossi'}, {'slug': 'blue', 'name': 'Blu'}]
    LOGOS = {'red': RED_CIRCLE, 'blue': BLUE_SQUARE}

    def run_update(self, state, packs, images, old=None, overrides=None, teams=None):
        return es.update(state, teams or self.TEAMS, packs,
                         lambda t: es.feature(self.LOGOS[t['slug']]) if t['slug'] in self.LOGOS else None,
                         lambda i: es.feature(images[i]),
                         lambda i: es.feature(old[i]) if old and i in old else None, overrides)

    def state(self):
        return {'packs': {'ItalianFootballEmoji': ['e1', 'e2']},
                'teams': {'red': {'name': 'Rossi', 'id': 'e1', 'pack': 'ItalianFootballEmoji', 'index': 0},
                          'blue': {'name': 'Blu', 'id': 'e2', 'pack': 'ItalianFootballEmoji', 'index': 1}}}

    def test_nothing_new_nothing_said(self):
        state = self.state()
        packs = {'ItalianFootballEmoji': [{'id': 'e1', 'index': 0}, {'id': 'e2', 'index': 1}]}
        self.assertEqual(self.run_update(state, packs, {'e1': RED_CIRCLE, 'e2': BLUE_SQUARE}), [])

    def test_removed_emoji_replaced_when_compatible(self):
        state = self.state()
        packs = {'ItalianFootballEmoji': [{'id': 'e3', 'emoji': '🇮🇹', 'index': 0}, {'id': 'e2', 'index': 1}]}
        report = self.run_update(state, packs, {'e2': BLUE_SQUARE, 'e3': RED_CIRCLE}, old={'e1': RED_CIRCLE})
        self.assertEqual(state['teams']['red']['id'], 'e3')
        self.assertTrue(any('Rossi' in r and '🔁' in r for r in report))
        self.assertEqual(state['packs']['ItalianFootballEmoji'], ['e3', 'e2'])

    def test_removed_emoji_not_replaced_below_90(self):
        state = self.state()
        packs = {'ItalianFootballEmoji': [{'id': 'e3', 'index': 0}, {'id': 'e2', 'index': 1}]}
        report = self.run_update(state, packs, {'e2': BLUE_SQUARE, 'e3': GREEN_TRI}, old={'e1': RED_CIRCLE})
        self.assertIsNone(state['teams']['red']['id'])
        self.assertTrue(any('Rossi' in r and '90%' in r for r in report))

    def test_new_jr_emoji_takes_over(self):
        state = self.state()
        packs = {'ItalianFootballEmoji': [{'id': 'e1', 'index': 0}, {'id': 'e2', 'index': 1}],
                 'AroundJuventus': [{'id': 'j1', 'index': 0}]}
        self.run_update(state, packs, {'e1': RED_CIRCLE, 'e2': BLUE_SQUARE, 'j1': png('square', (20, 40, 200))})
        self.assertEqual(state['teams']['blue']['id'], 'j1')
        self.assertEqual(state['teams']['red']['id'], 'e1')

    def test_manual_choice_removed_from_pack(self):
        packs = {'ItalianFootballEmoji': [{'id': 'e1', 'index': 0}, {'id': 'e2', 'index': 1}]}
        images = {'e1': RED_CIRCLE, 'e2': BLUE_SQUARE}
        # simile al logo: la scelta passa all'emoji compatibile
        overrides = {'red': {'id': 'gone', 'pack': 'ItalianFootballEmoji', 'index': 5}}
        self.run_update(self.state(), packs, images, old={'gone': GREEN_TRI}, overrides=overrides)
        self.assertEqual(overrides['red']['id'], 'e1')
        # niente di compatibile: la scelta a mano sparisce e torna l'automatica
        overrides = {'ghost': {'id': 'gone', 'pack': 'ItalianFootballEmoji', 'index': 5}}
        teams = [*self.TEAMS, {'slug': 'ghost', 'name': 'Verdi'}]
        self.run_update(self.state(), packs, images, old={'gone': GREEN_TRI}, overrides=overrides, teams=teams)
        self.assertNotIn('ghost', overrides)

    def test_runs_only_on_new_season(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            es.write_json(tmp / 'team_emoji/auto.json', {'season': '2026-27', 'packs': {}, 'teams': {}})
            es.write_json(tmp / 'manifest.json', {'season': '2026-27', 'teams': []})
            out = io.StringIO()
            from contextlib import redirect_stdout
            with redirect_stdout(out):
                es.main(tmp, tmp / 'manifest.json', force=False)   # niente token: se andasse avanti fallirebbe
            self.assertIn('2026-27', out.getvalue())
            self.assertEqual(es.season_of(tmp / 'manifest.json'), '2026-27')

    def test_new_team_matched(self):
        state = {'packs': {'ItalianFootballEmoji': ['e1', 'e2']}, 'teams': {}}
        packs = {'ItalianFootballEmoji': [{'id': 'e1', 'index': 0}, {'id': 'e2', 'index': 1}]}
        self.run_update(state, packs, {'e1': RED_CIRCLE, 'e2': BLUE_SQUARE})
        self.assertEqual(state['teams']['red']['id'], 'e1')
        self.assertEqual(state['teams']['blue']['id'], 'e2')
        self.assertEqual(state['teams']['red']['suggest'][0]['id'], 'e1')    # consigliate: la più simile prima

    def test_sprite_keeps_the_picture(self):
        sheet = Image.open(io.BytesIO(es.build_sprite([BLUE_SQUARE, RED_CIRCLE])))
        self.assertGreaterEqual(es.similarity(es.feature(es.sprite_cell(sheet, 1)), es.feature(RED_CIRCLE)), 0.9)
        self.assertLess(es.similarity(es.feature(es.sprite_cell(sheet, 0)), es.feature(RED_CIRCLE)), 0.9)


if __name__ == '__main__':
    unittest.main()
