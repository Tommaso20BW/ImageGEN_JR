"""Dichiarazioni: conferenza/intervista -> notizia Telegram (nomi in grassetto) e X (hashtag), con Claude finto."""
import json
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import _percorsi  # noqa: F401

import dichiarazioni as d

BOGA = '🇨🇮🗣 {Jeremie Boga|Boga} a {@Sky Sport} dopo #JuveOmonia: “Siamo contenti, abbiamo fatto una grande partita”.'


def reply(*testi):
    body = json.dumps({'proposte': [{'tema': f'Tema {i}', 'testo': t} for i, t in enumerate(testi, 1)]})
    return SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text', text=body)])


class FakeClient:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(json.loads(json.dumps(kw, default=lambda o: '<obj>')))
        return self.responses.pop(0)


class VersioniTest(unittest.TestCase):
    def test_x_like_profile(self):
        self.assertEqual(d.x_version(BOGA), '🇨🇮🗣 Jeremie #Boga a @SkySport dopo #JuveOmonia: '
                                            '“Siamo contenti, abbiamo fatto una grande partita”.')

    def test_plain_same_text_without_markup(self):
        self.assertEqual(d.plain_version(BOGA), '🇨🇮🗣 Jeremie Boga a Sky Sport dopo #JuveOmonia: '
                                                '“Siamo contenti, abbiamo fatto una grande partita”.')

    def test_telegram_bold_names_custom_emoji_and_sign(self):
        tg = d.telegram_version(BOGA)
        self.assertIn('<b>Jeremie Boga</b> a Sky Sport', tg)
        self.assertIn('5370765563226236970', tg)              # 🗣 del canale
        self.assertTrue(tg.endswith('@Juventus_Reborn'))
        self.assertNotIn('{', tg)

    def test_x_name_hashtag_replaces_surname(self):
        self.assertEqual(d.x_name('Luciano Spalletti', 'Spalletti'), 'Luciano #Spalletti')
        self.assertEqual(d.x_name('Juventus', 'Juventus'), '#Juventus')
        self.assertEqual(d.x_name('Kenan Yildiz', ''), 'Kenan #Yildiz')

    def test_outlets(self):
        self.assertEqual(d.x_outlet('DAZN'), '@DAZN_IT')
        self.assertEqual(d.x_outlet('La Gazzetta dello Sport'), '@Gazzetta_it')
        self.assertEqual(d.x_outlet('Radio Bianconera'), 'Radio Bianconera')

    def test_x_length_counts_emoji_double(self):
        self.assertEqual(d.x_length('abc'), 3)
        self.assertEqual(d.x_length('⚪ ok'), 5)
        self.assertEqual(d.x_length('🇨🇮🗣'), 4)
        self.assertEqual(d.x_length('“è”'), 3)

    def test_render(self):
        p = d.render({'tema': 'Boga', 'testo': BOGA})
        self.assertEqual(p['x_len'], d.x_length(p['x']))
        self.assertEqual(p['limit'], 240)
        self.assertFalse(p['over'])
        self.assertTrue(d.render({'testo': '⚪ ' + 'parola ' * 50})['over'])


class ConvertTest(unittest.TestCase):
    TEXT = 'Spalletti in conferenza: domani giochiamo una partita importante, la squadra sta bene.'

    def test_one_call_when_short(self):
        client = FakeClient(reply('⚪ {Luciano Spalletti|Spalletti}: “La squadra sta bene”.'))
        out = d.convert(self.TEXT, 'Spalletti in conferenza', client=client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(out['posts'][0]['x'], '⚪ Luciano #Spalletti: “La squadra sta bene”.')
        call = client.calls[0]
        self.assertEqual(call['model'], 'claude-opus-5-5')
        self.assertIn('REGOLE NEWS', call['system'][0]['text'])
        self.assertIn('Spalletti in conferenza', call['messages'][0]['content'])

    def test_retry_when_too_long(self):
        long = '⚪ {Luciano Spalletti|Spalletti}: “' + 'parola ' * 45 + '”.'
        client = FakeClient(reply(long), reply('⚪ {Luciano Spalletti|Spalletti}: “Corta”.'))
        out = d.convert(self.TEXT, client=client)
        self.assertEqual(len(client.calls), 2)
        self.assertIn('Troppo lunghe', client.calls[1]['messages'][-1]['content'])
        self.assertFalse(out['posts'][0]['over'])

    def test_refusal_and_short_text(self):
        with self.assertRaises(ValueError):
            d.convert('corto', client=FakeClient())
        refused = SimpleNamespace(stop_reason='refusal', content=[])
        with self.assertRaises(ValueError):
            d.convert(self.TEXT, client=FakeClient(refused))

    def test_missing_key(self):
        with mock.patch.dict('os.environ', {}, clear=True), self.assertRaises(ValueError) as ctx:
            d.start(self.TEXT)
        self.assertIn('ANTHROPIC_API_KEY', str(ctx.exception))

    def test_job_start_then_status(self):
        client = FakeClient(reply('⚪ {Juventus|Juventus}, ok.'))
        job = d.start(self.TEXT, client=client)['job']
        for _ in range(500):                               # fino a 10 s
            out = d.status(job)
            if out['done']:
                break
            time.sleep(0.02)
        self.assertEqual(out['posts'][0]['x'], '⚪ #Juventus, ok.')
        with self.assertRaises(ValueError):
            d.status(job)                                  # già letta: non c'è più


class SendTest(unittest.TestCase):
    def test_telegram_then_x_as_reply(self):
        tg = mock.Mock()
        tg.copy_text.side_effect = [11, 12]
        self.assertEqual(d.send(tg, {'raw': BOGA}), [11, 12])
        first, second = tg.copy_text.call_args_list
        self.assertIn('<b>Jeremie Boga</b>', first.args[0])
        self.assertIn('Jeremie #Boga a @SkySport', second.args[0])
        self.assertEqual(second.kwargs['reply_to'], 11)


if __name__ == '__main__':
    unittest.main()
