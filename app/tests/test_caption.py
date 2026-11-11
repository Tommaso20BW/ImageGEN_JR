import io
import re
import unittest
from unittest import mock

import _percorsi  # noqa: F401

import caption
import telegram

FIO = {'name': 'ACF Fiorentina', 'aliases': ['ACF Fiorentina', 'Fiorentina']}
SIGN = '<tg-emoji emoji-id="5985659276327132147">👉</tg-emoji> @Juventus_Reborn'


def plain(text):
    """Emoji personalizzate ridotte al simbolo di riserva, per confrontare il testo."""
    return re.sub(r'<tg-emoji emoji-id="\d+">([^<]*)</tg-emoji>', r'\1', text)


class CaptionTest(unittest.TestCase):
    def test_goal_like_livescore(self):
        text = caption.build({'kind': 'goal', 'competition': 'ita.1', 'side': 'away', 'opponent': FIO,
                              'goal_type': 'penalty', 'player': 'Dusan Vlahovic', 'minute': '90+2',
                              'score': (2, 1)})
        self.assertEqual(text, "<b>GOAL · 90+2' 🎙</b>\n\nFiorentina 2-<b>1 Juventus</b>\n"
                               "⚽️ <i>D. Vlahovic (Rig.)</i>\n\n🇮🇹 #FiorentinaJuve")

    def test_full_time_with_penalties(self):
        text = caption.build({'kind': 'full', 'competition': 'ita.coppa_italia', 'side': 'home', 'opponent': FIO,
                              'score': (1, 1), 'shootout': (4, 3)})
        self.assertIn('<b>Juventus 1 (4)</b>-(3) 1 Fiorentina', text)
        self.assertTrue(text.startswith('<b>FINE PARTITA 🏁</b>'))

    def test_matchday_rows(self):
        with mock.patch('team_emoji.find', return_value=None):     # squadra senza emoji: resta 🆚
            text = plain(caption.build({
                'kind': 'md', 'competition': 'ita.1', 'side': 'away',
                'opponent': {'name': 'US Lecce', 'aliases': ['US Lecce', 'Lecce']},
                'info': {'stadium': 'STADIO VIA DEL MARE', 'time': '18:00 CEST', 'date': '25 OTTOBRE 2026'}}))
        self.assertIn('<i>🇮🇹 Serie A</i>\n<i>🆚 Lecce</i>\n<i>✈️ Stadio Via del Mare</i>\n<i>📺 DAZN</i>\n'
                      '<i>⏰ 18:00</i>\n<i>📲 #LecceJuve</i>', text)

    def test_matchday_home_friendly(self):
        text = caption.build({'kind': 'md', 'competition': 'club.friendly', 'side': 'home', 'opponent': FIO,
                              'info': {'stadium': 'ALLIANZ STADIUM', 'time': '18:00 CEST'}})
        self.assertIn('<i><tg-emoji emoji-id="5357080225463149588">🤝</tg-emoji> Amichevole</i>', text)
        self.assertIn('<i><tg-emoji emoji-id="5789811507818668397">🏟</tg-emoji> Allianz Stadium</i>', text)
        self.assertIn('Juventus.com', text)

    def test_table_round_and_bracket(self):
        from graphics import classifica
        classifica._last['UEL'] = {'giornata': 4}
        try:
            self.assertEqual(plain(caption.build({'kind': 'table', 'competition': 'UEL'})),
                             '🇪🇺📊<b> UEL | Classifica</b>\n📆<i> 4ª Giornata</i>\n\n👉 @Juventus_Reborn')
        finally:
            classifica._last.pop('UEL', None)
        self.assertEqual(plain(caption.build({'kind': 'table', 'competition': 'CI', 'view': 'bracket'})),
                         '🆙🇮🇹 Tabellone<b> Coppa Italia </b>aggiornato.\n\n👉 @Juventus_Reborn')

    def test_other_graphics(self):
        self.assertEqual(plain(caption.build({'kind': 'table', 'competition': 'SA'})),
                         '🇮🇹📊<b> Serie A | Classifica</b>\n\n👉 @Juventus_Reborn')
        self.assertEqual(plain(caption.build({'kind': 'cal', 'month': 11, 'year': 2026})),
                         '⚔️📆 𝐍𝐎𝐕𝐄𝐌𝐁𝐑𝐄 𝟐𝟎𝟐𝟔\n\n👉 @Juventus_Reborn')
        for kind in ('jr', 'igbn', 'igq', 'xq', 'thq'):
            self.assertEqual(caption.build({'kind': kind, 'text': 'x'}), '', kind)

    def test_names_are_escaped(self):
        text = caption.build({'kind': 'goal', 'team': 'italy', 'competition': 'uefa.nations', 'side': 'home',
                              'opponent': {'name': 'A<B'}, 'player': 'X&Y', 'minute': '3', 'score': (1, 0)})
        self.assertIn('A&lt;B', text)
        self.assertIn('X&amp;Y', text)

    def test_live_posts_have_no_signature(self):
        for kind in ('goal', 'kick', 'half', 'second', 'end_of_90', 'full', 'stats'):
            data = {'kind': kind, 'competition': 'ita.1', 'side': 'home', 'opponent': FIO,
                    'score': (1, 0), 'moment': 'FT', 'player': 'Kenan Yildiz', 'minute': '5'}
            self.assertNotIn('@Juventus_Reborn', caption.build(data), kind)
        italy_xi = {'kind': 'xi', 'team': 'italy', 'competition': 'uefa.nations', 'side': 'home',
                    'opponent': {'name': 'Francia'}}
        self.assertNotIn('@Juventus_Reborn', caption.build(italy_xi))
        for kind in ('xi', 'pxi', 'squad', 'md'):
            data = {'kind': kind, 'competition': 'ita.1', 'side': 'home', 'opponent': FIO, 'info': {}}
            self.assertTrue(caption.build(data).endswith(SIGN), kind)

    def test_broken_data_sends_photo_without_text(self):
        self.assertEqual(caption.safe_build({'kind': 'full', 'side': 'home', 'opponent': FIO}), '')


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.sent = list(responses), []

    def post(self, url, data=None, files=None, timeout=None):
        self.sent.append(dict(data or {}))
        return self.responses.pop(0)

    def close(self):
        pass


def png():
    from PIL import Image
    out = io.BytesIO()
    Image.new('RGB', (4, 4)).save(out, 'PNG')
    return out.getvalue()


class PhotoCaptionTest(unittest.TestCase):
    def _send(self, responses, text):
        session = FakeSession(responses)
        tg = telegram.Telegram('1:x', '42')
        telegram.requests.Session, original = (lambda: session), telegram.requests.Session
        try:
            return tg, tg.photo(png(), 'a.png', text), session
        finally:
            telegram.requests.Session = original

    def test_caption_sent_as_html(self):
        ok = FakeResponse(200, {'ok': True, 'result': {'message_id': 7}})
        tg, message_id, session = self._send([ok], '<b>x</b>')
        self.assertEqual(message_id, 7)
        self.assertEqual(session.sent[0]['caption'], '<b>x</b>')
        self.assertEqual(session.sent[0]['parse_mode'], 'HTML')
        self.assertFalse(tg.caption_dropped)

    def test_rejected_caption_resends_photo_without_text(self):
        bad = FakeResponse(400, {'ok': False})
        ok = FakeResponse(200, {'ok': True, 'result': {'message_id': 8}})
        tg, message_id, session = self._send([bad, ok], '<b>x')
        self.assertEqual(message_id, 8)
        self.assertNotIn('caption', session.sent[1])
        self.assertTrue(tg.caption_dropped)


if __name__ == '__main__':
    unittest.main()
