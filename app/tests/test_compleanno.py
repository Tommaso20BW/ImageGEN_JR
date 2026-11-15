"""Compleanno: nome, data, età, foto del giocatore e richiesta della Mini App. Avvio (da app/): python -m unittest discover -s tests"""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import _percorsi  # noqa: F401 - prima degli import del servizio
import webapp_payload
from graphics import compleanno as C


class FakeCatalog:
    def players(self, query, goalkeeper=False):
        return ['Kenan Yildiz'] if 'yildiz' in query.casefold() else []


class Player:
    def __init__(self, slug, role='outfield'):
        self.slug, self.role, self.name = slug, role, slug.replace('_', ' ').title()


class TextTests(unittest.TestCase):
    def test_clean_name(self):
        self.assertEqual(C.clean_name('  Khéphren   Thuram-Ulien '), 'KHEPHREN THURAM-ULIEN')
        self.assertEqual(C.clean_name('Lucumí!'), 'LUCUMI')
        self.assertEqual(len(C.clean_name('x' * 80)), C.NAME_MAX)

    def test_parse_birth_and_age(self):
        self.assertEqual(C.parse_birth('2005-05-04'), date(2005, 5, 4))
        self.assertEqual(C.parse_birth('04.05.2005'), date(2005, 5, 4))
        for bad in ('', '2005-13-01', '31.02.2001', 'ieri'):
            self.assertIsNone(C.parse_birth(bad))
        self.assertEqual(C.age_on_birthday(date(2005, 5, 4), date(2026, 5, 4)), 21)


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for folder, names in {
            'players': ['kenan_yildiz_pose_04_point_sky.png', 'kenan_yildiz_away_pink_pose_03_scream.png'],
            'players_matchday': ['kenan_yildiz_pose_01_arms_crossed.png', 'kenan_yildiz_third_black_pose_02_pointing.png'],
        }.items():
            (root / folder / 'kenan_yildiz').mkdir(parents=True)
            for n in names:
                (root / folder / 'kenan_yildiz' / n).write_bytes(b'png')
        self.env = mock.patch.dict(os.environ, {'IMAGEGEN_ASSETS': str(root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_groups_in_order(self):
        rows = C.player_photos(Player('kenan_yildiz'))
        self.assertEqual([(r['group'], r['kit'], r['pose']) for r in rows], [
            ('matchday', 'Third', 'pointing'), ('starting', 'Home', 'arms_crossed'),
            ('goal', 'Away', 'scream'), ('goal', 'Home', 'point_sky')])

    def test_goalkeeper_poses_are_saved(self):
        rows = C.player_photos(Player('kenan_yildiz', 'goalkeeper'))
        self.assertEqual({r['group'] for r in rows}, {'matchday', 'starting', 'saved'})

    def test_photo_path_is_checked(self):
        ok = 'players/kenan_yildiz/kenan_yildiz_pose_04_point_sky.png'
        self.assertTrue(C.photo_path(ok, Player('kenan_yildiz')).is_file())
        for bad in ('../x.png', 'players/kenan_yildiz/../../secret.png', 'canva/kenan_yildiz/a.png',
                    'players/kenan_yildiz/kenan_yildiz_pose_09_nope.png',
                    'players/../kenan_yildiz_pose_04_point_sky.png'):
            with self.assertRaises(ValueError):
                C.photo_path(bad)
        with self.assertRaises(ValueError):
            C.photo_path(ok, Player('andrea_cambiaso'))

    def test_payload(self):
        env = {'v': 1, 'action': 'render', 'session': 's1', 'data': {
            'kind': 'bday', 'player': 'Kenan Yildiz', 'name': 'Kenan Yıldız', 'birth': '2005-05-04', 'age': '',
            'photo': 'players/kenan_yildiz/kenan_yildiz_pose_04_point_sky.png'}}
        data = webapp_payload.parse_webapp_request(env, FakeCatalog(), 0, 's1')['data']
        self.assertEqual((data['player'], data['birth']), ('Kenan Yildiz', '2005-05-04'))
        self.assertTrue(data['name'].startswith('KENAN Y'))
        self.assertEqual(data['age'], date.today().year - 2005)
        env['data']['birth'] = '2005-02-30'
        with self.assertRaises(ValueError):
            webapp_payload.parse_webapp_request(env, FakeCatalog(), 0, 's1')


if __name__ == '__main__':
    unittest.main()
