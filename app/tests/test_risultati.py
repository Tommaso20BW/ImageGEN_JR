import unittest
from datetime import date
from unittest.mock import patch

import _percorsi  # noqa: F401 - prima degli import del servizio
import caption
import log
import risultati_data
import webapp_payload
from graphics import classifica, risultati


def envelope(competition, view=None, story=False):
    data = {'kind': 'table', 'competition': competition}
    if view:
        data['view'] = view
    if story:
        data['story'] = True
    return {'v': 1, 'action': 'render', 'session': 's1', 'data': data}


DATA = {'competition': 'SA', 'giornata': 12, 'turno': 'Giornata 12', 'date': '21–23 Novembre', 'stagione': '2026/27',
        'partite': [{'home': 'Juventus', 'away': 'Venezia', 'home_logo': 'data:image/png;base64,AA',
                     'away_logo': 'data:image/png;base64,AA', 'stato': 'finita', 'gol_casa': 4, 'gol_trasferta': 0,
                     'quando': 'Dom 22/11 · 12:30'}]}


class PayloadTests(unittest.TestCase):
    def test_results_view_for_serie_a_and_cups(self):
        for comp in ('SA', 'UCL'):
            state = webapp_payload.parse_webapp_request(envelope(comp, 'results'), None, 0, 's1')
            self.assertEqual(state['data'], {'kind': 'table', 'competition': comp, 'view': 'results'})

    def test_results_have_no_story(self):
        state = webapp_payload.parse_webapp_request(envelope('SA', 'results', story=True), None, 0, 's1')
        self.assertNotIn('story', state['data'])
        state = webapp_payload.parse_webapp_request(envelope('SA', story=True), None, 0, 's1')
        self.assertTrue(state['data']['story'])           # la classifica la storia ce l'ha

    def test_serie_a_has_no_bracket_and_ci_only_bracket(self):
        with self.assertRaises(ValueError):
            webapp_payload.parse_webapp_request(envelope('SA', 'bracket'), None, 0, 's1')
        state = webapp_payload.parse_webapp_request(envelope('CI', 'results'), None, 0, 's1')
        self.assertEqual(state['data']['view'], 'bracket')


class DataTests(unittest.TestCase):
    def test_team_pages_follow_names_not_link_order(self):
        row = {'home': 'Monza', 'away': 'Fiorentina',
               'link': 'https://www.diretta.it/partita/calcio/fiorentina-Q3A3IbXH/monza-4YSMlwj7/?mid=x'}
        self.assertEqual(risultati_data._team_urls(row), ('/squadra/monza/4YSMlwj7/', '/squadra/fiorentina/Q3A3IbXH/'))

    def test_date_label(self):
        self.assertEqual(risultati_data._date_label([date(2026, 11, 21), date(2026, 11, 23)]), '21–23 Novembre')
        self.assertEqual(risultati_data._date_label([date(2026, 11, 30), date(2026, 12, 1)]), '30 Novembre – 1 Dicembre')

    def test_match_states(self):
        base = {'home': 'A', 'away': 'B', 'time': '22.11. 18:00', 'link': ''}
        done = risultati_data._partita({**base, 'hs': '2', 'as': '1'})
        self.assertEqual((done['stato'], done['gol_casa'], done['gol_trasferta']), ('finita', 2, 1))
        todo = risultati_data._partita({**base, 'hs': '-', 'as': '-', 'scheduled': True})
        self.assertEqual(todo['stato'], 'da_giocare')
        self.assertTrue(todo['quando'].endswith('22/11 · 18:00'))


class PageTests(unittest.TestCase):
    def test_page_is_self_contained(self):
        with patch.object(classifica, '_font_css', return_value='@font-face{}'):
            html = risultati.build_html(DATA)
        self.assertIn('window.__RISULTATI__ = {"competition": "SA"', html)
        self.assertIn('renderRisultati', html)
        self.assertNotIn('const CFG', html)                 # via lo script della classifica
        self.assertNotIn('fonts.googleapis', html)
        for name in classifica.IMAGES:
            self.assertNotIn(name, html)

    def test_caption_and_log_name(self):
        risultati._last['SA'] = DATA
        try:
            text = caption.build({'kind': 'table', 'competition': 'SA', 'view': 'results'})
        finally:
            risultati._last.pop('SA', None)
        self.assertIn('Serie A | Risultati', text)
        self.assertIn('12ª Giornata', text)
        self.assertEqual(log.graphic_name({'kind': 'table', 'view': 'results'}), 'Risultati')


if __name__ == '__main__':
    unittest.main()
