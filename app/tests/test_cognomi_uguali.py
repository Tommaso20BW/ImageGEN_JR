"""Due cognomi uguali nella formazione: iniziale del nome (S. ESPOSITO, P. ESPOSITO), se no si chiede."""
import unittest
from types import SimpleNamespace

import _percorsi  # noqa: F401

import webapp_payload as wp
from constants import ITALY_COMPETITIONS
from graphics import probabili

XI = ['Donnarumma', 'Di Lorenzo', 'S. Esposito', 'Bastoni', 'Dimarco', 'Barella', 'Tonali',
      'Frattesi', 'Raspadori', 'P. Esposito', 'Chiesa']


def italy_xi(players):
    incoming = {'opponent': {'name': 'Francia'}, 'formation': '4-3-3', 'players': players}
    competition = ITALY_COMPETITIONS[0][1]
    kit = sorted(wp.ITALY_KITS)[0]
    side = sorted(wp.VALID_SIDES)[0]
    return wp._italy_state(incoming, 'xi', competition, kit, side, 0)


class ItaliaTests(unittest.TestCase):
    def test_initials_that_differ_are_kept(self):
        self.assertEqual(italy_xi(XI)['data']['players'][2], 'S. Esposito')

    def test_missing_initial_is_asked(self):
        for players in (XI[:2] + ['Esposito'] + XI[3:],
                        XI[:2] + ['Esposito'] + XI[3:9] + ['Esposito'] + XI[10:],
                        XI[:2] + ['P. Esposito'] + XI[3:]):
            with self.assertRaisesRegex(ValueError, "due ESPOSITO: scrivi anche l'iniziale"):
                italy_xi(players)


class JuveTests(unittest.TestCase):
    def player(self, name):
        return SimpleNamespace(name=name, slug='x', aliases=[])

    def test_same_surname_gets_initial(self):
        players = [self.player('Sebastiano Esposito'), self.player('Pio Esposito'),
                   self.player('Federico Gatti')]
        self.assertEqual(probabili.label_names(players), ['S. ESPOSITO', 'P. ESPOSITO', 'GATTI'])


if __name__ == '__main__':
    unittest.main()
