"""CAMBIO dalla Mini App: da 1 a 5 coppie (esce, entra) con numero e nome, testo come il LiveScore."""
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _percorsi  # noqa: F401

import caption
import service
import webapp_payload

FIO = {'name': 'ACF Fiorentina', 'id': '109'}
CATALOG = SimpleNamespace(teams=lambda name: [dict(FIO)])


def envelope(subs, minute='67', **extra):
    data = {'kind': 'sub', 'competition': 'ita.1', 'kit': 'home', 'side': 'home',
            'opponent': {'name': 'Fiorentina', 'id': '109'}, 'subs': subs, 'minute': minute, **extra}
    return {'v': 1, 'action': 'render', 'session': 's1', 'data': data}


def pair(out, out_n, inn, inn_n):
    return {'out': {'name': out, 'number': out_n}, 'in': {'name': inn, 'number': inn_n}}


def parse(subs, **kw):
    return webapp_payload.parse_webapp_request(envelope(subs, **kw), CATALOG, 0, 's1')['data']


class PayloadTests(unittest.TestCase):
    def test_pairs_with_roster_names(self):
        data = parse([pair('Kolo Muani', '9', 'Nick Woltemade', 27),
                      pair('Lloyd Kelly', '6', 'Juan David Cabal', '32')])
        self.assertEqual(data['subs'], [[[9, 'Randal Kolo Muani'], [27, 'Nick Woltemade']],
                                        [[6, 'Lloyd Casius Kelly'], [32, 'Juan David Cabal']]])
        self.assertEqual(data['minute'], '67')

    def test_name_not_in_roster_stays_as_written(self):
        data = parse([pair('Kenan Yildiz', '10', 'Mario Rossi', '45')])
        self.assertEqual(data['subs'][0][1], [45, 'Mario Rossi'])

    def test_from_one_to_five(self):
        names = ['Kenan Yildiz', 'Nick Woltemade', 'Federico Gatti', 'Andrea Cambiaso', 'Manuel Locatelli',
                 'Weston McKennie', 'Teun Koopmeiners', 'Jeff Ekhator', 'Daniele Rugani', 'Edon Zhegrova',
                 'Pierre Kalulu', 'Jérémie Boga']
        five = [pair(names[2 * i], i + 1, names[2 * i + 1], i + 20) for i in range(5)]
        self.assertEqual(len(parse(five)['subs']), 5)
        six = five + [pair(names[10], 11, names[11], 30)]
        for subs in ([], six, None):
            with self.assertRaisesRegex(ValueError, 'da 1 a 5 cambi'):
                parse(subs)

    def test_number_and_duplicates_and_minute(self):
        with self.assertRaisesRegex(ValueError, 'numero di maglia di Nick Woltemade'):
            parse([pair('Kenan Yildiz', '10', 'Nick Woltemade', '')])
        with self.assertRaisesRegex(ValueError, 'numero di maglia'):
            parse([pair('Kenan Yildiz', '0', 'Nick Woltemade', '27')])
        with self.assertRaisesRegex(ValueError, 'scelto due volte'):
            parse([pair('Kenan Yildiz', '10', 'Yildiz', '10')])
        with self.assertRaisesRegex(ValueError, 'scelto due volte'):
            parse([pair('Kenan Yildiz', '10', 'Nick Woltemade', '27'),
                   pair('Federico Gatti', '4', 'Nick Woltemade', '27')])
        with self.assertRaises(ValueError):
            parse([pair('Kenan Yildiz', '10', 'Nick Woltemade', '27')], minute='')
        with self.assertRaisesRegex(ValueError, 'Scegli chi entra e chi esce'):
            parse([{'out': {'name': 'Kenan Yildiz', 'number': '10'}}])


SUBS = [[[9, 'Randal Kolo Muani'], [27, 'Nick Woltemade']], [[6, 'Lloyd Casius Kelly'], [32, 'Juan David Cabal']]]
DATA = {'kind': 'sub', 'competition': 'ita.1', 'kit': 'home', 'side': 'away', 'opponent': FIO,
        'subs': SUBS, 'minute': '67'}


class CaptionTests(unittest.TestCase):
    def setUp(self):
        caption.CUSTOM = {}

    def test_like_livescore(self):
        self.assertEqual(caption.build(DATA),
                         "<b>CAMBIO JUVENTUS · 67' 🔄</b>\n\n🔺 N. Woltemade, J. David Cabal\n"
                         "🔻 R. Kolo Muani, L. Casius Kelly\n\n🇮🇹 #FiorentinaJuve")

    def test_no_text_for_x(self):
        telegram, x = caption.copy_messages(DATA, caption.build(DATA))
        self.assertTrue(telegram.startswith('<b>CAMBIO JUVENTUS'))
        self.assertEqual(x, '')

    def test_recent_sends_row(self):
        row = service._send_detail(DATA)
        self.assertEqual(row['player'], 'IN Woltemade, Cabal · OUT Kolo Muani, Kelly')
        self.assertEqual(row['minute'], "67'")
        self.assertEqual(row['opponent'], 'ACF Fiorentina')


class RenderTests(unittest.TestCase):
    def test_png(self):
        from livescore.graphics import goal as g
        if not (Path(g.DEFAULT_ASSET_DIR) / 'portrait').is_dir():
            self.skipTest('asset grafici non presenti')
        import render
        from PIL import Image
        with mock.patch.object(g, '_remote_espn_team_logo', return_value=None):
            for competition in ('ita.1', 'club.friendly', 'uefa.champions'):
                png = render.Renderer.__new__(render.Renderer)._render({**DATA, 'competition': competition})
                self.assertEqual(Image.open(io.BytesIO(png)).size, (1086, 1448))


if __name__ == '__main__':
    unittest.main()
