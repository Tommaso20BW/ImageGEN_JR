"""Compleanno, Starting XI, Probabili, Squad List, Classifica/Tabellone e Man of the Match in due versioni: 3:4 e storia IG (9:16)."""
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
        self.assertEqual(set(webapp_payload.STORY_KINDS), {'bday', 'bdold', 'xi', 'pxi', 'squad', 'table', 'motm', 'igc'})


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
        svc._render_and_cache = lambda state, **kw: (b'png', 1)
        return svc

    def test_story_saved(self):
        svc = self.svc({'kind': 'bday', 'story': True})
        path = svc.save_file({})['path']
        self.assertEqual(svc.saved_file(path.split('/')[-1][:-4]), b'png')

    def test_34_not_saved(self):
        with self.assertRaises(ValueError):
            self.svc({'kind': 'bday'}).save_file({})


class PostToGalleryTests(unittest.TestCase):
    """Il post inviato (1 foto, o 2 per l'album classifica + risultati) va anche nella galleria."""
    def svc(self, data):
        import threading
        svc = service.Service.__new__(service.Service)
        svc.operation_lock, svc.preview_cache_lock = threading.Lock(), threading.Lock()
        svc.preview_cache = svc.preview_cache_prev = svc.preview_cache_old = None
        svc.saved_files, svc.recent_sends, svc.generated_message_ids = {}, {}, []
        svc._parse_request = lambda env: {'data': dict(data), 'id': 1}
        svc.renderer = type('R', (), {'render': lambda self, d: b'post'})()
        svc._table_version = lambda d: 'v'
        svc._results_png = lambda d: b'risultati'
        svc._send_photo = lambda *a: 41
        svc._send_album = lambda *a: [51, 52]
        svc._remember_send = svc._remember_ig_name = lambda *a: None
        return svc

    def files(self, svc, message_id):
        return [svc.saved_file(p.split('/')[-1][:-4]) for p in svc.post_files_for(message_id)]

    def test_single_photo(self):
        svc = self.svc({'kind': 'bday'})
        self.assertEqual(svc.submit({'data': {}}), 41)
        self.assertEqual(self.files(svc, 41), [b'post'])

    def test_album_in_order(self):
        svc = self.svc({'kind': 'table', 'competition': 'SA', 'with_results': True})
        self.assertEqual(svc.submit({'data': {}}), 51)
        self.assertEqual(self.files(svc, 51), [b'post', b'risultati'])     # prima la 1, poi la 2

    def test_story_sent_not_kept(self):
        svc = self.svc({'kind': 'bday', 'story': True})
        self.assertEqual(svc.post_files_for(svc.submit({'data': {}})), [])

    def test_unknown_message(self):
        self.assertEqual(self.svc({'kind': 'bday'}).post_files_for(99), [])

    def test_answer_has_files(self):
        from pathlib import Path
        src = Path(service.__file__).read_text(encoding='utf-8')
        self.assertIn("'files': self.service.post_files_for(message_id)", src)


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
        svc.preview_cache = svc.preview_cache_prev = svc.preview_cache_old = None
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

    def test_motm_story(self):
        from PIL import Image
        from graphics import motm
        args = dict(surname='YILDIZ', name='Kenan', home='Juventus', away='Inter', comp='Serie A', ghost=True)
        self.assertEqual(Image.open(io.BytesIO(motm.render(**args))).size, (1500, 2000))
        self.assertEqual(Image.open(io.BytesIO(motm.render(story=True, **args))).size, (1500, 2667))

    def test_story_stamp(self):
        self.assertEqual(common.story_jr_stamp_alpha().height, common.STORY_JR_H)

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


class PhotoRotTests(unittest.TestCase):
    def test_rotated_photo_covers_page(self):
        import math
        from graphics.starting_xi import photo_box
        for rot in (-45, -12.5, 7, 30):
            for x, y in ((0, 0), (.4, -.3), (-3, 3)):
                left, top, w, h = photo_box((1600, 1000), {'zoom': 1, 'x': x, 'y': y, 'rot': rot})
                cx, cy, a = left + w / 2, top + h / 2, math.radians(rot)
                for px, py in ((0, 0), (1080, 0), (0, 1440), (1080, 1440)):
                    u = (px - cx) * math.cos(a) + (py - cy) * math.sin(a)
                    v = -(px - cx) * math.sin(a) + (py - cy) * math.cos(a)
                    self.assertLessEqual(abs(u), w / 2 + .01)
                    self.assertLessEqual(abs(v), h / 2 + .01)

    def test_payload_rot(self):
        from webapp_payload import _frame
        self.assertEqual(_frame({'x': 0, 'y': 0, 'zoom': 1}), {'x': 0.0, 'y': 0.0, 'zoom': 1.0})
        self.assertEqual(_frame({'zoom': 1, 'rot': 90})['rot'], 45.0)
        self.assertEqual(_frame({'zoom': .5}, min_zoom=.5)['zoom'], .5)


class PersonRotTests(unittest.TestCase):
    def test_clean_frames_keep_rot(self):
        from graphics import affare_fatto, compleanno, motm
        for mod in (affare_fatto, compleanno, motm):
            self.assertEqual(mod.clean_frame({'x': 0, 'y': 0, 'zoom': 1, 'rot': -80})['rot'], -45)
            self.assertNotIn('rot', mod.clean_frame({'x': 0, 'y': 0, 'zoom': 1}))

    def test_rotate_person_keeps_center(self):
        from PIL import Image
        p = Image.new('RGBA', (100, 300), (255, 0, 0, 255))
        r, x, y = common.rotate_person(p, 10, 20, {'rot': 30})
        self.assertGreater(r.width, 100)
        self.assertAlmostEqual(x + r.width / 2, 60, delta=1)
        self.assertAlmostEqual(y + r.height / 2, 170, delta=1)
        self.assertEqual(common.rotate_person(p, 10, 20, {})[1:], (10, 20))
