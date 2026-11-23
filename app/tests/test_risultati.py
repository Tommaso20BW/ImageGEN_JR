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


class GiornataTests(unittest.TestCase):
    """La giornata unisce i risultati e le partite del calendario anche se l'etichetta non è identica."""

    @staticmethod
    def riga(home, away, hs='', as_='', scheduled=False, time='22.11. 15:00'):
        return {'home': home, 'away': away, 'hs': hs, 'as': as_, 'scheduled': scheduled, 'live': False,
                'time': time, 'stage': '', 'home_logo': '', 'away_logo': '', 'link': ''}

    def fetch(self, risultati, calendario):
        pagine = {'risultati': risultati, 'calendario': calendario}
        with patch.object(risultati_data, '_scrape', return_value=(pagine, 'Serie A 2026/2027')), \
                patch.object(risultati_data, '_loghi', lambda partite: None):
            return risultati_data._fetch('SA')

    def test_chiave_giornata(self):
        k = risultati_data._chiave_giornata
        self.assertEqual(k('Giornata 12'), k('Giornata\xa012 '))
        self.assertEqual(k('Giornata 12'), k('GIORNATA 12 · Mostra'))
        self.assertNotEqual(k('Giornata 12'), k('Giornata 13'))

    def test_partita_del_calendario_con_etichetta_diversa(self):
        finite = [{'round': 'Giornata 12'}, self.riga('Juventus', 'Venezia', '4', '0')]
        da_giocare = [{'round': 'Giornata\xa012 '}, self.riga('Fiorentina', 'Monza', '-', '-', True, '23.11. 20:45'),
                      {'round': 'Giornata 13'}, self.riga('Venezia', 'Bologna', '-', '-', True, '27.11. 20:45')]
        out = self.fetch(finite, da_giocare)
        self.assertEqual({(p['home'], p['away']) for p in out['partite']},
                         {('Juventus', 'Venezia'), ('Fiorentina', 'Monza')})
        self.assertEqual(out['giornata'], 12)

    def test_coppe_tutta_la_fase_senza_limite_di_settimana(self):
        """Coppa Italia ed europee: tutte le partite del turno, anche giocate in settimane diverse."""
        finite = [{'round': 'Ottavi di finale'}, self.riga('Juventus', 'Venezia', '2', '1', time='02.12. 21:00'),
                  self.riga('Milan', 'Lecce', '1', '0', time='16.12. 21:00')]
        da_giocare = [{'round': 'Ottavi di finale'}, self.riga('Inter', 'Como', '-', '-', True, '13.01. 21:00'),
                      {'round': 'Quarti di finale'}, self.riga('X', 'Y', '-', '-', True, '10.02. 21:00')]
        for comp in ('CI', 'UCL', 'UEL', 'UECL'):
            pagine = {'risultati': finite, 'calendario': da_giocare}
            with patch.object(risultati_data, '_scrape', return_value=(pagine, 'Coppa 2026/2027')), \
                    patch.object(risultati_data, '_loghi', lambda partite: None):
                out = risultati_data._fetch(comp)
            self.assertEqual(len(out['partite']), 3, comp)
            self.assertEqual(out['turno'], 'Ottavi di finale')

    def test_andata_e_ritorno_una_riga_col_totale(self):
        finite = [{'round': 'Ottavi di finale'},
                  self.riga('Inter', 'Porto', '2', '0', time='10.03. 21:00'),     # andata
                  self.riga('Porto', 'Inter', '1', '1', time='17.03. 21:00'),     # ritorno
                  self.riga('Milan', 'Lecce', '1', '0', time='10.03. 18:45')]     # partita secca
        out = self.fetch(finite, [])
        self.assertEqual(len(out['partite']), 2)
        tie = next(p for p in out['partite'] if p['home'] == 'Inter')
        self.assertEqual((tie['gol_casa'], tie['gol_trasferta']), (3, 1))        # totale 2-0 + 1-1
        self.assertEqual((tie['andata_res'], tie['ritorno_res']), ([2, 0], [1, 1]))
        self.assertEqual(out['date'], '10–17 Marzo')

    def test_ritorno_ai_rigori_nell_orientamento_dell_andata(self):
        a = risultati_data._partita(self.riga('Inter', 'Porto', '1', '0', time='10.03. 21:00'))
        r = risultati_data._partita({**self.riga('Porto', 'Inter', '1(4)', '0(5)', time='17.03. 21:00')})
        tie = risultati_data._accoppia([a, r])[0]
        self.assertEqual((tie['gol_casa'], tie['gol_trasferta']), (1, 1))
        self.assertEqual(tie['rigori'], [5, 4])                                   # Inter 5, Porto 4

    def test_solo_andata_giocata(self):
        finite = [{'round': 'Ottavi di finale'}, self.riga('Inter', 'Porto', '2', '0', time='10.03. 21:00')]
        calendario = [{'round': 'Ottavi di finale'},
                      self.riga('Porto', 'Inter', '-', '-', True, '17.03. 21:00')]
        out = self.fetch(finite, calendario)
        self.assertEqual(len(out['partite']), 1)
        p = out['partite'][0]
        self.assertEqual((p['stato'], p['gol_casa'], p['gol_trasferta']), ('finita', 2, 0))
        self.assertTrue(p['ritorno_quando'].endswith('17/3 · 21:00'))
        self.assertEqual(out['date'], '10–17 Marzo')

    def test_nessun_doppione_tra_risultati_e_calendario(self):
        finite = [{'round': 'Giornata 12'}, self.riga('Juventus', 'Venezia', '4', '0')]
        calendario = [{'round': 'Giornata 12'}, self.riga('Juventus', 'Venezia', '-', '-', True)]
        self.assertEqual(len(self.fetch(finite, calendario)['partite']), 1)


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
