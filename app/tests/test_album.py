"""Classifica (e tabellone della Coppa Italia) + risultati: un album di 2 foto su Telegram."""
import io
import json
import threading
import unittest

import _percorsi  # noqa: F401 - prima degli import del servizio
import service
import telegram
import webapp_payload
from PIL import Image


def png():
    buf = io.BytesIO()
    Image.new('RGB', (30, 40), (10, 20, 30)).save(buf, 'PNG')
    return buf.getvalue()


def table(**data):
    return {'v': 1, 'action': 'render', 'session': 's1', 'data': {'kind': 'table', **data}}


class PayloadTests(unittest.TestCase):
    def parse(self, env):
        return webapp_payload.parse_webapp_request(env, None, 0, 's1')['data']

    def test_classifica_with_results(self):
        self.assertIs(self.parse(table(competition='SA', with_results=True))['with_results'], True)
        self.assertIs(self.parse(table(competition='UCL', view='table', with_results=True))['with_results'], True)

    def test_coppa_italia_tabellone_without_results(self):
        data = self.parse(table(competition='CI', with_results=True))
        self.assertEqual(data['view'], 'bracket')
        self.assertNotIn('with_results', data)           # il tabellone ha già i risultati dentro

    def test_not_for_european_bracket(self):
        self.assertNotIn('with_results', self.parse(table(competition='UCL', view='bracket', with_results=True)))

    def test_only_when_true(self):
        self.assertNotIn('with_results', self.parse(table(competition='SA', with_results='yes')))
        self.assertNotIn('with_results', self.parse(table(competition='SA')))

    def test_story_without_album(self):
        data = self.parse(table(competition='SA', with_results=True, story=True))
        self.assertEqual((data.get('story'), 'with_results' in data), (True, False))


class FakeTelegram(telegram.Telegram):
    def __init__(self, fail_caption=False):
        super().__init__('t', 1, session=object())
        self.calls, self.fail_caption = [], fail_caption

    def call(self, method, data=None, files=None, timeout=25, fresh=False):
        media = json.loads(data['media'])
        self.calls.append((method, media, sorted(files)))
        if self.fail_caption and 'caption' in media[0]:
            raise telegram.TelegramError('HTTP 400: caption')
        return [{'message_id': 7, 'photo': [{'file_id': 'a', 'width': 320}, {'file_id': 'b', 'width': 1280}]},
                {'message_id': 8}]


class AlbumTests(unittest.TestCase):
    def test_two_photos_caption_on_first(self):
        tg = FakeTelegram()
        self.assertEqual(tg.album([png(), png()], 'table-1', 'Testo'), [7, 8])
        method, media, files = tg.calls[0]
        self.assertEqual((method, files), ('sendMediaGroup', ['p0', 'p1']))
        self.assertEqual([m['media'] for m in media], ['attach://p0', 'attach://p1'])
        self.assertEqual(media[0]['caption'], 'Testo')
        self.assertNotIn('caption', media[1])
        self.assertEqual(tg.last_photo, {'file_id': 'b', 'thumb_id': 'a'})

    def test_caption_refused_resends_without(self):
        tg = FakeTelegram(fail_caption=True)
        self.assertEqual(tg.album([png(), png()], 'table-1', 'Testo'), [7, 8])
        self.assertTrue(tg.caption_dropped)
        self.assertNotIn('caption', tg.calls[-1][1][0])

    def test_not_png(self):
        with self.assertRaises(telegram.TelegramError):
            FakeTelegram().album([b'nope', png()])


class ResultsPngTests(unittest.TestCase):
    def svc(self):
        svc = service.Service.__new__(service.Service)
        svc.preview_cache_lock = threading.Lock()
        svc.preview_cache = svc.preview_cache_prev = svc.preview_cache_old = None
        svc.renderer = type('R', (), {'render': lambda self, data: b'nuovo'})()
        return svc

    def test_uses_fresh_preview(self):
        svc = self.svc()
        results = {'kind': 'table', 'competition': 'SA', 'view': 'results'}
        svc._cache_put({'fingerprint': svc._fingerprint(results), 'png': b'anteprima', 'updated': 1e12})
        self.assertEqual(svc._results_png({'kind': 'table', 'competition': 'SA', 'with_results': True}), b'anteprima')

    def test_other_preview_not_used(self):
        svc = self.svc()
        svc._cache_put({'fingerprint': 'classifica', 'png': b'classifica', 'updated': 1e12})
        self.assertEqual(svc._results_png({'kind': 'table', 'competition': 'SA'}), b'nuovo')

    def test_three_previews_kept(self):
        svc = self.svc()
        for f in ('34', 'story', 'res'):
            svc._cache_put({'fingerprint': f, 'png': f.encode()})
        self.assertEqual([svc._cache_get(f)['png'] for f in ('34', 'story', 'res')], [b'34', b'story', b'res'])


if __name__ == '__main__':
    unittest.main()
