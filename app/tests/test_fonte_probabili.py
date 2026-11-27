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


if __name__ == '__main__':
    unittest.main()
