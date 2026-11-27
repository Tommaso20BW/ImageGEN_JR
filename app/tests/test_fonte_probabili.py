import unittest

import _percorsi  # noqa: F401

import caption

FIO = {'name': 'ACF Fiorentina', 'aliases': ['ACF Fiorentina', 'Fiorentina']}
PXI = {'kind': 'pxi', 'competition': 'ita.1', 'side': 'away', 'opponent': FIO}


class FontePxiTest(unittest.TestCase):
    def setUp(self):
        self.custom, caption.CUSTOM = caption.CUSTOM, {}

    def tearDown(self):
        caption.CUSTOM = self.custom

    def test_sky_and_gazzetta_get_their_pack_emoji(self):
        sky = caption.build({**PXI, 'source': 'sky'})
        self.assertIn('<i><tg-emoji emoji-id="5974058122984038105">📰</tg-emoji> Sky Sport</i>', sky)
        gaz = caption.build({**PXI, 'source': 'gazzetta'})
        self.assertIn('<i><tg-emoji emoji-id="5974032198561439462">📰</tg-emoji> La Gazzetta dello Sport</i>', gaz)

    def test_x_uses_the_profile(self):
        text = caption.build({**PXI, 'source': 'gazzetta'})
        x = caption.copy_messages({**PXI, 'source': 'gazzetta'}, text)[1]
        self.assertTrue(x.rstrip().endswith('📲 @Gazzetta_it'), x)

    def test_no_source_no_line(self):
        self.assertNotIn('📰', caption.build({**PXI, 'source': ''}))
        self.assertNotIn('📰', caption.build(PXI))
        self.assertNotIn('{fonte}', caption.build({**PXI, 'source': 'nope'}))

    def test_placeholder_puts_it_where_written(self):
        caption.CUSTOM = {'pxi': 'Fonte: {fonte}\n\nProbabile {hashtag}'}
        text = caption.build({**PXI, 'source': 'sky'})
        self.assertTrue(text.startswith('Fonte: <i><tg-emoji emoji-id="5974058122984038105">'), text)
        self.assertEqual(text.count('Sky Sport'), 1)


    def test_coppa_italia_matchday_tv_is_sportmediaset(self):
        from unittest import mock
        with mock.patch('team_emoji.find', return_value=None):
            text = caption.x_text({'kind': 'md', 'competition': 'ita.coppa_italia', 'side': 'home',
                                   'opponent': FIO, 'info': {'stadium': 'ALLIANZ STADIUM', 'time': '21:00'}})
        self.assertIn('📺 @sportmediaset', text)
        self.assertIn('📲 #JuveFiorentina', text)          # l'hashtag della partita resta com'e'

    def test_sources_written_in_a_template_become_profiles(self):
        caption.CUSTOM = {'x:potm': '{giocatore} eletto.\n\n__📰 Sky Sport__\n📲 Gianluca Di Marzio\n📰 Il Bianconero'}
        text = caption.x_text({'kind': 'potm', 'name': 'NICK', 'surname': 'WOLTEMADE'},
                              caption.build({'kind': 'potm', 'name': 'NICK', 'surname': 'WOLTEMADE'}))
        self.assertIn('📲 @SkySport', text)
        self.assertIn('📲 @DiMarzio', text)
        self.assertIn('📲 Il Bianconero', text)            # senza profilo noto: il nome, con 📲
        self.assertNotIn('📰', text)


if __name__ == '__main__':
    unittest.main()
