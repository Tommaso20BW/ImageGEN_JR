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

    def setUp(self):
        caption.CUSTOM = {}

    def tearDown(self):
        caption.CUSTOM = {}

    def test_templates_get_hashtags(self):
        # come sul profilo: ✅🇧🇷 HERE WE GO: #Neto alla #Juventus.
        with mock.patch('graphics.compleanno.nationality', return_value='BR'):
            self.assertEqual(x({'kind': 'af', 'name': 'NETO', 'surname': ''}),
                             '✅🇧🇷 HERE WE GO: #Neto alla #Juventus.\n\n📲 @FabrizioRomano')
        with mock.patch('graphics.compleanno.nationality', return_value='AR'), \
                mock.patch('caption._roster_name', return_value='Nico Gonzalez'):
            self.assertEqual(x({'kind': 'rin', 'name': 'GONZALEZ', 'year': '2030'}),
                             '✅🇦🇷 UFFICIALE | Nico #Gonzalez rinnova con la #Juventus fino al 2030.')
        text = x({'kind': 'potm', 'name': 'NICO', 'surname': 'GONZALEZ', 'month': 'AGOSTO/SETTEMBRE'})
        self.assertIn('netto: Nico #Gonzalez è stato eletto miglior giocatore della #Juventus nei mesi di agosto e '
                      'settembre', text)
        self.assertNotIn('*', text)

    def test_friendly_matchday_without_hashtag(self):
        with mock.patch('team_emoji.find', return_value=None):
            text = x({'kind': 'md', 'competition': 'club.friendly', 'side': 'home', 'opponent': FIO,
                      'info': {'stadium': 'ALLIANZ STADIUM', 'time': '18:00 CEST'}})
        self.assertEqual(text, '𝐌𝐀𝐓𝐂𝐇𝐃𝐀𝐘 🔥⚔️\n\n🤝 Amichevole\n🆚 #Fiorentina\n🏟 Allianz Stadium\n'
                               '📺 Juventus.com\n⏰ 18:00\n📲 #JuveFiorentina')

    def test_x_template_written_in_mini_app(self):
        caption.CUSTOM = {'x:motm': '⭐️ MOTM {hashtag} ➜ {giocatore} 🔥', 'motm': 'solo Telegram {giocatore}'}
        data = {'kind': 'motm', 'name': 'NICK', 'surname': 'WOLTEMADE', 'home': 'JUVENTUS', 'away': 'VENEZIA'}
        self.assertEqual(x(data), '⭐️ MOTM #JuveVenezia ➜ Nick #Woltemade 🔥')
        self.assertIn('solo Telegram', caption.build(data))
        rows = {r['kind']: r for r in caption.templates_list()}
        self.assertTrue(rows['motm']['x']['custom'])
        self.assertEqual(rows['motm']['x']['text'], '⭐️ MOTM {hashtag} ➜ {giocatore} 🔥')
        self.assertFalse(rows['xi']['x']['custom'])
        self.assertEqual(rows['af']['x']['fields'], ['giocatore', 'bandiera'])

    def test_save_both_texts(self):
        import threading
        import service
        fake = mock.Mock(history_lock=threading.Lock())
        with mock.patch('sent_store.save_captions') as save:
            body = service.Service.captions(fake, {'action': 'caption_save', 'kind': 'xi',
                                                   'text': caption.TEMPLATE_KINDS['xi'][1],
                                                   'x_text': '✅📋 XI {hashtag} 🔥'})
        self.assertEqual(caption.CUSTOM, {'x:xi': '✅📋 XI {hashtag} 🔥'})
        save.assert_called_once_with({'x:xi': '✅📋 XI {hashtag} 🔥'})
        self.assertEqual(next(r for r in body['captions'] if r['kind'] == 'xi')['x']['text'], '✅📋 XI {hashtag} 🔥')
        with mock.patch('sent_store.save_captions'):     # testo X di base: torna quello di base
            service.Service.captions(fake, {'action': 'caption_save', 'kind': 'xi', 'text': '',
                                            'x_text': caption.X_TEMPLATES['xi']})
        self.assertEqual(caption.CUSTOM, {})

    def test_saved_x_templates_load_back(self):
        import sent_store
        with mock.patch('sent_store._read', return_value={'x:af': 'HWG {giocatore}', 'x:boh': 'no', 'xi': 'XI'}):
            self.assertEqual(sent_store.load_captions(), {'x:af': 'HWG {giocatore}', 'xi': 'XI'})

    def test_fallback_is_plain_caption_without_signature(self):
        self.assertEqual(x({'kind': 'cal', 'month': 11, 'year': 2026}), '⚔️📆 𝐍𝐎𝐕𝐄𝐌𝐁𝐑𝐄 𝟐𝟎𝟐𝟔')
        self.assertEqual(x({'kind': 'conv'}), '🌍📋 I bianconeri convocati dalle rispettive nazionali.')
        self.assertEqual(x({'kind': 'jr'}), '')


class CopyTextsTest(unittest.TestCase):
    def test_telegram_as_caption_then_x_box(self):
        data = {'kind': 'squad', 'competition': 'ita.1', 'side': 'away', 'opponent': FIO}
        tg_text = '<tg-emoji emoji-id="5">☑️</tg-emoji>📝 I convocati di <b>Spalletti</b> &amp; co.'
        with mock.patch('caption.x_text', return_value='☑️📝 I convocati di #Spalletti & co.'):
            tg, xb = caption.copy_messages(data, tg_text)
        self.assertEqual(tg, tg_text)                      # come la didascalia, senza scritte sopra
        self.assertEqual(xb, '☑️📝 I convocati di #Spalletti &amp; co.')

    def test_live_only_end_of_halves_go_to_x(self):
        self.assertEqual(caption.copy_messages({'kind': 'goal'}, '<b>GOAL</b>'), ('<b>GOAL</b>', ''))
        with mock.patch('caption.x_text', return_value='FINE PARTITA 🏁'):
            self.assertEqual(caption.copy_messages({'kind': 'full'}, 'FT')[1], 'FINE PARTITA 🏁')

    def test_no_caption_no_message(self):
        self.assertEqual(caption.copy_messages({'kind': 'jr'}, ''), ('', ''))

    def test_only_x_box_as_reply_to_photo(self):
        import service
        sent = []
        fake = mock.Mock(generated_message_ids=[])
        fake.telegram.copy_text.side_effect = lambda body, reply_to=None: sent.append((body, reply_to)) or 12
        with mock.patch('caption.x_text', return_value='FINE PARTITA 🏁'):
            service.Service._send_copy_texts(fake, {'kind': 'full'}, '<b>FINE PARTITA</b>', 40)
            service.Service._send_copy_texts(fake, {'kind': 'goal'}, '<b>GOAL</b>', 41)   # su X no
        self.assertEqual(sent, [('FINE PARTITA 🏁', 40)])     # la foto ha già il testo Telegram
        self.assertEqual(fake.generated_message_ids, [12])

    def test_telegram_sends_html_silently_and_replies(self):
        import json
        import telegram
        tg = telegram.Telegram('t', '1')
        with mock.patch.object(tg, 'call', return_value={'message_id': 7}) as call:
            self.assertEqual(tg.copy_text('<pre>a</pre>', reply_to=5), 7)
        sent = call.call_args.args[1]
        self.assertEqual(sent['text'], '<pre>a</pre>')
        self.assertEqual((sent['parse_mode'], sent['disable_notification']), ('HTML', 'true'))
        self.assertEqual(json.loads(sent['reply_parameters'])['message_id'], 5)


if __name__ == '__main__':
    unittest.main()
