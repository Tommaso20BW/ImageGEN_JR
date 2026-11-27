"""Dichiarazioni: testo già scritto -> versione Telegram (come il canale) e versione X (come il profilo)."""
import unittest
from unittest import mock

import _percorsi  # noqa: F401

import dichiarazioni as d

TEXT = '''COMPLETO

🗣️ Luciano Spalletti a Sky Sport dopo #JuveOmonia

PARTITA – “Cambiaso ha rimesso a posto le cose con un grande gol”.

EKHATOR – “Ha disputato una buona partita. Merita i complimenti”.

240

🇮🇹🗣️ Spalletti a Sky Sport dopo #JuveOmonia: “Cambiaso ha rimesso a posto le cose. Ekhator merita i complimenti”.'''


class BlocchiTest(unittest.TestCase):
    def test_labels_split_blocks(self):
        parts = d.blocks(TEXT)
        self.assertEqual([label for label, _ in parts], ['COMPLETO', '240'])
        self.assertTrue(parts[0][1].startswith('🗣️ Luciano Spalletti'))
        self.assertEqual(d.blocks('🗣️ Gatti: “Bene”.'), [('', '🗣️ Gatti: “Bene”.')])

    def test_long_block_like_channel(self):
        p = d.convert(TEXT)['posts'][0]
        self.assertEqual(p['tema'], 'COMPLETO')
        self.assertIsNone(p['limit'])
        tg = p['tg']
        self.assertIn('5370765563226236970', tg)                       # 🗣 del canale
        self.assertIn('</tg-emoji> <b>Luciano Spalletti</b> a <i>Sky Sport</i> dopo #JuveOmonia:\n', tg)   # ":" aggiunti
        # parlato in corsivo col punto, nomi nelle virgolette normali
        self.assertIn('<b>PARTITA</b> – <i>“Cambiaso ha rimesso a posto le cose con un grande gol”.</i>\n', tg)
        self.assertTrue(tg.endswith('@Juventus_Reborn'))
        self.assertTrue(p['x'].startswith('🗣️ Luciano #Spalletti a @SkySport dopo #JuveOmonia:\n\nPARTITA – “Cambiaso'))

    def test_short_block_like_profile(self):
        p = d.convert(TEXT)['posts'][1]
        self.assertEqual(p['x'], '🇮🇹🗣️ #Spalletti a @SkySport dopo #JuveOmonia: '
                                 '“Cambiaso ha rimesso a posto le cose. Ekhator merita i complimenti”.')
        self.assertIn('<b>Spalletti</b> a <i>Sky Sport</i> dopo #JuveOmonia: <i>“Cambiaso', p['tg'])
        self.assertIn('complimenti”.</i>\n\n', p['tg'])
        self.assertEqual((p['limit'], p['x_len'], p['over']), (240, d.x_length(p['x']), False))

    def test_over_limit_and_outlets_only_outside_quotes(self):
        p = d.convert('240\n\n⚪🗣️ Kenan Yildiz a DAZN: “Guardo Sky Sport. ' + 'parola ' * 40 + '”.')['posts'][0]
        self.assertTrue(p['over'])
        self.assertTrue(p['x'].startswith('⚪🗣️ Kenan #Yildiz a @DAZN_IT: “Guardo Sky Sport.'))

    def test_x_length(self):
        self.assertEqual(d.x_length('abc'), 3)
        self.assertEqual(d.x_length('⚪ ok'), 5)
        self.assertEqual(d.x_length('🇨🇮🗣️'), 4)
        self.assertEqual(d.x_length('“è”'), 3)

    def test_empty(self):
        with self.assertRaises(ValueError):
            d.convert('  ')


class SendTest(unittest.TestCase):
    def test_telegram_then_x_as_reply(self):
        tg = mock.Mock()
        tg.copy_text.side_effect = [11, 12]
        raw = d.convert(TEXT)['posts'][1]['raw']
        self.assertEqual(d.send(tg, {'raw': raw}), [11, 12])
        first, second = tg.copy_text.call_args_list
        self.assertIn('<b>Spalletti</b>', first.args[0])
        self.assertIn('#Spalletti a @SkySport', second.args[0])
        self.assertEqual(second.kwargs['reply_to'], 11)


if __name__ == '__main__':
    unittest.main()
