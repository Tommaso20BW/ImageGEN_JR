"""Testi da copiare dopo la foto: X come i post di @Juventus_Reborn, Telegram/IG come la didascalia."""
import unittest
from unittest import mock

import _percorsi  # noqa: F401

import caption

OMONIA = {'name': 'Omonia Nicosia', 'aliases': ['Omonia Nicosia', 'Omonia']}
FIO = {'name': 'ACF Fiorentina', 'aliases': ['ACF Fiorentina', 'Fiorentina']}


def x(data):
    return caption.x_text(data)


class XTextTest(unittest.TestCase):
    def test_squad_xi_pxi(self):
        data = {'competition': 'ita.1', 'side': 'away', 'opponent': FIO}
        self.assertEqual(x({**data, 'kind': 'squad'}), '☑️📝 I convocati di #Spalletti per #FiorentinaJuve.')
        self.assertEqual(x({**data, 'kind': 'xi'}), '✅📋 𝐗𝐈 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄 #FiorentinaJuve')
        self.assertEqual(x({**data, 'kind': 'pxi'}), '🆕📋 𝐏𝐑𝐎𝐁𝐀𝐁𝐈𝐋𝐄 𝐗𝐈 #FiorentinaJuve')

    def test_matchday_like_profile(self):
        with mock.patch('team_emoji.find', return_value=None):
            text = x({'kind': 'md', 'competition': 'ita.1', 'side': 'away', 'opponent': FIO,
                      'info': {'stadium': 'ARTEMIO FRANCHI', 'time': '20:45 CET'}})
        self.assertEqual(text, '𝐌𝐀𝐓𝐂𝐇𝐃𝐀𝐘 🔥⚔️\n\n🇮🇹 #SerieA\n🆚 #Fiorentina\n✈️ Artemio Franchi\n'
                               '📺 @DAZN_IT\n⏰ 20:45\n📲 #FiorentinaJuve')

    def test_full_time_teams_with_hashtag(self):
        text = x({'kind': 'full', 'competition': 'ita.1', 'side': 'away', 'opponent': FIO, 'score': (2, 2)})
        self.assertEqual(text, 'FINE PARTITA 🏁\n\n#Fiorentina 2-2 #Juventus\n\n🇮🇹 #FiorentinaJuve')
        text = x({'kind': 'half', 'competition': 'ita.1', 'side': 'home', 'opponent': FIO, 'score': (1, 0)})
        self.assertEqual(text, 'FINE PRIMO TEMPO 🏁\n\n#Juventus 1-0 #Fiorentina\n\n🇮🇹 #JuveFiorentina')

    def test_motm_and_birthday(self):
        self.assertEqual(x({'kind': 'motm', 'name': 'NICK', 'surname': 'WOLTEMADE',
                            'home': 'JUVENTUS', 'away': 'VENEZIA'}),
                         '⭐️🔝 𝐌𝐎𝐓𝐌 #JuveVenezia: Nick #Woltemade')
        with mock.patch('graphics.compleanno.nationality', return_value='IT'), \
                mock.patch('player_emoji.find', return_value=None):
            self.assertEqual(x({'kind': 'bday', 'player': 'Vincenzo IAQUINTA'}),
                             '🎂🇮🇹 Tanti auguri a Vincenzo #Iaquinta!')

    def test_table_and_results(self):
        from graphics import classifica
        classifica._last['SA'] = {'giornata': 12}
        try:
            self.assertEqual(x({'kind': 'table', 'competition': 'SA'}), '📊🇮🇹 #SerieA | Classifica\n📆 12ª Giornata')
        finally:
            classifica._last.pop('SA', None)
        self.assertEqual(x({'kind': 'table', 'competition': 'UEL'}), '📊🇪🇺 #UEL | Classifica')
        self.assertEqual(x({'kind': 'table', 'competition': 'CI', 'view': 'bracket'}),
                         '🆙🇮🇹 Tabellone #CoppaItalia aggiornato.')

    def test_templates_get_hashtags(self):
        self.assertEqual(x({'kind': 'af', 'name': 'JONATHAN', 'surname': 'DAVID'}),
                         '✅ HERE WE GO: Jonathan #David alla #Juventus.\n\n📲 @FabrizioRomano')
        text = x({'kind': 'potm', 'name': 'NICO', 'surname': 'GONZALEZ', 'month': 'AGOSTO/SETTEMBRE'})
        self.assertIn('netto: Nico #Gonzalez è stato eletto miglior giocatore della #Juventus nei mesi di agosto e '
                      'settembre', text)
        self.assertNotIn('*', text)

    def test_fallback_is_plain_caption_without_signature(self):
        self.assertEqual(x({'kind': 'cal', 'month': 11, 'year': 2026}), '⚔️📆 𝐍𝐎𝐕𝐄𝐌𝐁𝐑𝐄 𝟐𝟎𝟐𝟔')
        self.assertEqual(x({'kind': 'conv'}), '🌍📋 I bianconeri convocati dalle rispettive nazionali.')
        self.assertEqual(x({'kind': 'jr'}), '')


class CopyTextsTest(unittest.TestCase):
    def test_two_messages_x_then_telegram(self):
        data = {'kind': 'squad', 'competition': 'ita.1', 'side': 'away', 'opponent': FIO}
        pieces = caption.copy_texts(data, caption.build(data))
        self.assertEqual([t for t, _ in pieces], ['𝕏 Testo per X', '✈️ Testo per Telegram / IG'])
        self.assertEqual(pieces[1][1], '☑️📝 I convocati di Spalletti per #FiorentinaJuve.\n\n👉 @Juventus_Reborn')
        self.assertNotIn('<', pieces[1][1])

    def test_no_caption_no_messages(self):
        self.assertEqual(caption.copy_texts({'kind': 'jr'}, ''), [])

    def test_telegram_message_is_copy_block(self):
        import telegram
        tg = telegram.Telegram('t', '1')
        with mock.patch.object(tg, 'call', return_value={'message_id': 7}) as call:
            self.assertEqual(tg.copy_text('𝕏 Testo per X', 'A & B <3'), 7)
        sent = call.call_args.args[1]
        self.assertEqual(sent['text'], '<b>𝕏 Testo per X</b>\n<pre>A &amp; B &lt;3</pre>')
        self.assertEqual(sent['parse_mode'], 'HTML')


if __name__ == '__main__':
    unittest.main()
