"""Compleanno, Starting XI, Probabili, Squad List e Classifica/Tabellone in due versioni: 3:4 e storia IG (9:16)."""
import copy
import io
import unittest
from unittest import mock

import _percorsi  # noqa: F401 - prima degli import del servizio
import service
import webapp_payload
from graphics import common
from graphics import compleanno as C


class FakeCatalog:
    def players(self, query, goalkeeper=False):
        return ['Kenan Yildiz'] if 'yildiz' in query.casefold() else []


def bday(**extra):
    return {'v': 1, 'action': 'render', 'session': 's1', 'data': {
        'kind': 'bday', 'player': 'Kenan Yildiz', 'name': 'Kenan Yildiz', 'birth': '2005-05-04', 'age': '',
        'photo': 'players/kenan_yildiz/kenan_yildiz_pose_04_point_sky.png', **extra}}


class PayloadTests(unittest.TestCase):
    def test_story_only_when_asked(self):
        parse = lambda env: webapp_payload.parse_webapp_request(env, FakeCatalog(), 0, 's1')['data']
        self.assertNotIn('story', parse(bday()))
        self.assertNotIn('story', parse(bday(story='yes')))
        self.assertIs(parse(bday(story=True))['story'], True)

    def test_story_kinds(self):
        self.assertEqual(set(webapp_payload.STORY_KINDS), {'bday', 'bdold', 'xi', 'pxi', 'squad', 'table'})


class SubmitTests(unittest.TestCase):
    def submit(self, env):
        svc = service.Service.__new__(service.Service)
        sent = []
        svc._submit_one = lambda e: sent.append(copy.deepcopy(e)) or 100 + len(sent)
        return service.Service.submit(svc, env), sent

    def test_without_formats_sends_the_request(self):
        env = bday()
        message_id, sent = self.submit(env)
        self.assertEqual((message_id, sent), (101, [env]))

    def test_both_formats_two_photos(self):
        message_id, sent = self.submit(bday(formats=['story', '34']))
        self.assertEqual(message_id, 101)
        self.assertEqual([e['data']['story'] for e in sent], [False, True])      # prima il 3:4
        self.assertTrue(all('formats' not in e['data'] for e in sent))

    def test_only_story(self):
        _, sent = self.submit(bday(formats=['story']))
        self.assertEqual([e['data']['story'] for e in sent], [True])

    def test_nothing_chosen(self):
        with self.assertRaises(ValueError):
            self.submit(bday(formats=[]))


class CaptionTests(unittest.TestCase):
    def test_story_without_caption(self):
        from pathlib import Path
        src = Path(service.__file__).read_text(encoding='utf-8')
        self.assertIn("text = None if data.get('story') else caption.safe_build(data)", src)


class SaveFileTests(unittest.TestCase):
    """La storia delle grafiche doppie si salva nella galleria del telefono, come la storia IG."""
    def svc(self, data):
        import threading
        svc = service.Service.__new__(service.Service)
        svc.operation_lock, svc.preview_cache_lock, svc.story_lock = threading.Lock(), threading.Lock(), threading.Lock()
        svc.saved_files = {}
        svc._set_stage = lambda *_: None
        svc._parse_request = lambda env: {'data': data, 'id': 1}
        svc._render_and_cache = lambda state: (b'png', 1)
        return svc

    def test_story_saved(self):
        svc = self.svc({'kind': 'bday', 'story': True})
        path = svc.save_file({})['path']
        self.assertEqual(svc.saved_file(path.split('/')[-1][:-4]), b'png')

    def test_34_not_saved(self):
        with self.assertRaises(ValueError):
            self.svc({'kind': 'bday'}).save_file({})


class LaneTests(unittest.TestCase):
    """3:4 e storia si preparano insieme: la storia delle grafiche doppie ha una corsia sua."""
    def test_story_own_lock(self):
        import threading
        svc = service.Service.__new__(service.Service)
        svc.operation_lock, svc.story_lock = threading.Lock(), threading.Lock()
        self.assertIs(svc._lock_for({'data': {'kind': 'bday', 'story': True}}), svc.story_lock)
        self.assertIs(svc._lock_for({'data': {'kind': 'bday'}}), svc.operation_lock)
        self.assertIs(svc._lock_for({'data': {'kind': 'igbn', 'story': True}}), svc.operation_lock)
        self.assertIs(svc._lock_for(None), svc.operation_lock)


class CacheTests(unittest.TestCase):
    def test_keeps_both_previews(self):
        svc = service.Service.__new__(service.Service)
        svc.preview_cache = svc.preview_cache_prev = None
        svc._cache_put({'fingerprint': 'a', 'png': b'1'})
        svc._cache_put({'fingerprint': 'b', 'png': b'2'})
        self.assertEqual(svc._cache_get('a')['png'], b'1')
        self.assertEqual(svc._cache_get('b')['png'], b'2')
        svc._cache_put({'fingerprint': 'b', 'png': b'3'})      # stessa grafica: la 3:4 resta
        self.assertEqual(svc._cache_get('a')['png'], b'1')


class RenderTests(unittest.TestCase):
    def test_bday_story_size(self):
        from PIL import Image
        args = dict(name='KENAN YILDIZ', birth='2005-05-04', photo='players/kenan_yildiz/kenan_yildiz_pose_04_point_sky.png')
        story = Image.open(io.BytesIO(C.render(story=True, **args)))
        self.assertEqual(story.size, (1500, round(1500 * 16 / 9)))
        self.assertEqual((C.H, C.TOP, C.STRIP_Y), (2000, 0, 2000 - 205))      # dopo la storia torna il 3:4

    def test_story_bg(self):
        import base64
        from PIL import Image
        path = common.asset_dir() / 'canva' / 'probabili_home_bg.png'
        if not path.is_file():
            self.skipTest('sfondo non negli asset')
        raw = base64.b64decode(common.story_bg(str(path)).split(',', 1)[1])
        self.assertEqual(Image.open(io.BytesIO(raw)).size, (1920, common.STORY_OUT_H))


if __name__ == '__main__':
    unittest.main()


class FreePhotoTests(unittest.TestCase):
    def test_free_photo_box(self):
        from graphics.starting_xi import photo_box
        frame = {'zoom': .3, 'x': .6, 'y': .6}
        self.assertEqual(photo_box((1086, 1448), frame), (0, 0, 1080, 1440))
        left, top, w, h = photo_box((1086, 1448), frame, free=True)
        self.assertAlmostEqual(w, 540)
        self.assertAlmostEqual(left, 1080 * .8)
        self.assertAlmostEqual(top, 1440 * .8)
