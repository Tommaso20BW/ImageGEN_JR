"""Editor libero: modelli salvati, file per la Mini App, payload, didascalia e render dell'immagine finita."""
import io
import threading
import unittest
from datetime import datetime
from unittest import mock

from PIL import Image

import caption
import render
import sent_store
import service
from webapp_payload import parse_webapp_request

DOC = {'v': 1, 'w': 1500, 'h': 2000, 'bg': '#000000',
       'layers': [{'id': 'a', 'type': 'photo', 'src': 'data:xxx'}, {'id': 'b', 'type': 'text', 'text': 'Ciao'}]}


def bare_service():
    s = object.__new__(service.Service)
    s.history_lock = threading.Lock()
    s.editor_templates = []
    s.overlays = {}
    return s


class TemplateTest(unittest.TestCase):
    def test_clean(self):
        t = sent_store.clean_template({'id': 'abc123', 'name': '  Lutto   bianco ', 'doc': DOC})
        self.assertEqual(t['name'], 'Lutto bianco')
        self.assertNotIn('src', t['doc']['layers'][0])           # niente foto nel modello
        for bad in ({'id': 'abc123', 'name': '', 'doc': DOC}, {'id': 'AB', 'name': 'x', 'doc': DOC},
                    {'id': 'abc123', 'name': 'x', 'doc': {}},
                    {'id': 'abc123', 'name': 'x', 'doc': {'layers': [{'t': 'x' * 13000}]}}, 'nope'):
            with self.assertRaises(ValueError):
                sent_store.clean_template(bad)

    def test_list_save_delete(self):
        s = bare_service()
        with mock.patch.object(sent_store, 'save_templates') as save:
            self.assertEqual(s.templates({'action': 'list'}), {'templates': []})
            save.assert_not_called()
            s.templates({'action': 'save', 'template': {'id': 'aaaaaa', 'name': 'Uno', 'doc': DOC}})
            s.templates({'action': 'save', 'template': {'id': 'bbbbbb', 'name': 'Due', 'doc': DOC}})
            out = s.templates({'action': 'save', 'template': {'id': 'aaaaaa', 'name': 'Uno bis', 'doc': DOC}})
            self.assertEqual([t['name'] for t in out['templates']], ['Uno bis', 'Due'])   # stesso id: sovrascrive, in cima
            out = s.templates({'action': 'delete', 'id': 'bbbbbb'})
            self.assertEqual([t['id'] for t in out['templates']], ['aaaaaa'])
            self.assertEqual(save.call_count, 4)
        with self.assertRaises(ValueError):
            s.templates({'action': 'boh'})

    def test_editor_files(self):
        s = bare_service()
        png, ctype = s.editor_file('jrlogo')
        self.assertEqual(ctype, 'image/png')
        with Image.open(io.BytesIO(png)) as im:
            self.assertEqual(im.mode, 'RGBA')
            self.assertEqual(im.getchannel('A').getbbox(), (0, 0) + im.size)   # ritagliato
        data, ctype = s.editor_file('Poppins-Medium.ttf')
        self.assertEqual(ctype, 'font/ttf')
        self.assertGreater(len(data), 1000)
        for bad in ('../secret.ttf', 'x.py', 'Nessuno.ttf', ''):
            with self.assertRaises(ValueError):
                s.editor_file(bad)


class EraseTest(unittest.TestCase):
    """Gomma: la zona bianca della maschera va a inpaint.remove, torna un JPEG della stessa misura."""
    @staticmethod
    def _png(image, fmt='PNG'):
        buf = io.BytesIO()
        image.save(buf, fmt)
        return buf.getvalue()

    def test_erase(self):
        import base64
        from livescore.graphics import inpaint
        s = bare_service()
        s.photos = {'p': self._png(Image.new('RGB', (300, 400), (200, 10, 10)), 'JPEG')}
        mask = Image.new('L', (150, 200), 0)
        mask.paste(255, (40, 40, 80, 90))
        s.photos['m'] = self._png(mask)
        seen = {}

        def fake(image, m):
            seen['size'], seen['box'] = m.size, m.point(lambda v: 255 if v > 24 else 0).getbbox()
            return Image.new('RGB', image.size, (0, 0, 255))
        with mock.patch.object(inpaint, 'remove', fake):
            out = s.erase_image({'photo_id': 'p', 'mask_id': 'm'})
        self.assertEqual(seen['size'], (300, 400))                 # maschera portata alla misura della foto
        for got, want in zip(seen['box'], (80, 80, 160, 180)):    # bordo sfumato dal ridimensionamento
            self.assertLessEqual(abs(got - want), 2)
        raw = base64.b64decode(out['image'].split(',', 1)[1])
        with Image.open(io.BytesIO(raw)) as im:
            self.assertEqual((im.format, im.size), ('JPEG', (300, 400)))

    def test_erase_subject(self):
        from livescore.graphics import inpaint
        s = bare_service()
        s.photos = {'p': self._png(Image.new('RGB', (300, 400), (200, 10, 10)), 'JPEG')}
        cut = Image.new('RGBA', (150, 200), (0, 0, 0, 0))
        cut.paste((255, 255, 255, 255), (50, 20, 100, 190))
        s.renderer = mock.Mock(cutout=mock.Mock(return_value=self._png(cut)))
        seen = {}

        def fake(image, m):
            seen['box'] = m.point(lambda v: 255 if v > 24 else 0).getbbox()
            return image
        with mock.patch.object(inpaint, 'remove', fake):
            s.erase_image({'photo_id': 'p', 'subject': True})            # senza maschera: basta la persona
        for got, want in zip(seen['box'], (100, 40, 200, 380)):
            self.assertLessEqual(abs(got - want), 2)
        s.renderer.cutout.return_value = self._png(Image.new('RGBA', (30, 40), (0, 0, 0, 0)))
        with self.assertRaises(ValueError):
            s.erase_image({'photo_id': 'p', 'subject': True})            # nessuna persona trovata

    def test_erase_job(self):
        s = bare_service()
        s.erase_jobs, s.erase_jobs_lock = {}, threading.Lock()
        go = threading.Event()

        def slow(env):
            go.wait(5)
            return {'image': 'data:x'}
        with mock.patch.object(s, 'erase_image', slow), mock.patch.object(service, '_lower_priority', lambda: None):
            env = {'photo_id': 'p', 'subject': True}
            self.assertEqual(s.erase(env)['state'], 'running')
            self.assertEqual(s.erase(env)['state'], 'running')       # la stessa: non riparte
            go.set()
            for _ in range(50):
                out = s.erase(env)
                if out['state'] != 'running':
                    break
                threading.Event().wait(0.05)
            self.assertEqual((out['state'], out['image']), ('ready', 'data:x'))
            self.assertEqual(s.erase_jobs, {})                       # consegnato e tolto

    def test_erase_errors(self):
        s = bare_service()
        s.photos = {'p': self._png(Image.new('RGB', (30, 40)), 'JPEG'), 'm': self._png(Image.new('L', (30, 40), 0))}
        with self.assertRaises(ValueError):
            s.erase_image({'photo_id': 'p', 'mask_id': 'm'})             # niente dipinto
        with self.assertRaises(ValueError):
            s.erase_image({'photo_id': 'p', 'mask_id': 'x'})


class PayloadTest(unittest.TestCase):
    def test_free(self):
        env = {'v': 1, 'action': 'render', 'session': 's',
               'data': {'kind': 'free', 'photo_id': 'a' * 16, 'title': 'Lutto', 'caption': ' Ciao   a tutti \r\n\nRiga  due '}}
        state = parse_webapp_request(env, None, datetime.now(), 's')
        self.assertEqual(state['data'], {'kind': 'free', 'photo_id': 'a' * 16, 'title': 'Lutto', 'caption': 'Ciao a tutti\n\nRiga due'})

    def test_caption(self):
        self.assertTrue(caption.build({'kind': 'free', 'caption': 'Ciao <3'}).startswith('Ciao &lt;3'))
        self.assertEqual(caption.build({'kind': 'free', 'caption': ''}), '')
        self.assertEqual(service._history_summary({'kind': 'free', 'title': 'Lutto'})['note'], 'Editor libero') \
            if hasattr(service, '_history_summary') else None


class RenderTest(unittest.TestCase):
    def test_render_free(self):
        r = render.Renderer()
        buf = io.BytesIO()
        Image.new('RGB', (1500, 2000), (10, 20, 30)).save(buf, 'JPEG')
        r.photos['b' * 16] = buf.getvalue()
        png = r.render({'kind': 'free', 'photo_id': 'b' * 16})
        with Image.open(io.BytesIO(png)) as im:
            self.assertEqual(im.size, (1500, 2000))
        with self.assertRaises(ValueError):
            r.render({'kind': 'free', 'photo_id': 'c' * 16})


if __name__ == '__main__':
    unittest.main()
