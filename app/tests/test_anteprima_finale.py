"""La grafica salvata o inviata è quella dell'anteprima, con lo scontorno giusto."""
import threading
import unittest
from unittest import mock

import _percorsi  # noqa: F401 - prima degli import del servizio
import render
import service
import webapp_payload
from graphics import squad_list


def story(text='Notizia'):
    env = {'v': 1, 'action': 'render', 'session': 's1', 'data': {'kind': 'igbn', 'text': text}}
    return webapp_payload.parse_webapp_request(env, None, 0, 's1')['data']


class SeedTests(unittest.TestCase):
    def test_same_story_same_seed(self):
        self.assertEqual(story()['seed'], story()['seed'])

    def test_other_story_other_seed(self):
        self.assertNotEqual(story('Una')['seed'], story('Altra')['seed'])


class FastCutoutTests(unittest.TestCase):
    def svc(self):
        svc = service.Service.__new__(service.Service)
        svc.preview_cache_lock = threading.Lock()
        svc.preview_cache = svc.preview_cache_prev = svc.preview_cache_old = None
        svc.renderer = mock.Mock(used_fast_cutout=False)
        svc.renderer.render.return_value = b'fine'
        svc._set_stage = lambda stage: None
        data = {'kind': 'igbn', 'text': 'x'}
        svc._cache_put({'fingerprint': svc._fingerprint(data), 'request_id': 'r', 'data': data,
                        'png': b'veloce', 'updated': 1e12, 'fast_cutout': True})
        return svc, {'id': 'r', 'data': data}

    def test_preview_reuses_fast(self):
        svc, state = self.svc()
        self.assertEqual(svc._render_and_cache(state)[0], b'veloce')

    def test_final_file_redone(self):
        svc, state = self.svc()
        self.assertEqual(svc._render_and_cache(state, final=True)[0], b'fine')

    def test_flag_not_shared_between_threads(self):
        renderer = render.Renderer()
        renderer.used_fast_cutout = True
        seen = []
        def other():
            renderer.used_fast_cutout = False
            seen.append(renderer.used_fast_cutout)
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        self.assertEqual((seen, renderer.used_fast_cutout), ([False], True))


class SquadWarmUpTests(unittest.TestCase):
    def test_warm_up_uses_render_key(self):
        with mock.patch.object(squad_list, '_geometry') as geometry:
            squad_list.warm_up()
        path = squad_list._photo_path()
        self.assertEqual([c.args for c in geometry.call_args_list],
                         [(path, squad_list.OUT_H), (path, squad_list.STORY_OUT_H)])


if __name__ == '__main__':
    unittest.main()
