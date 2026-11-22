import threading
import types
import unittest
from unittest import mock

import _percorsi  # noqa: F401

import sent_store
import service


def _stub():
    return types.SimpleNamespace(history_lock=threading.Lock(), ig_phrases=[],
                                 _phrase_extra=service.Service._phrase_extra)


class FrasiProntePiene(unittest.TestCase):
    def test_salva_etichetta_fonte_link(self):
        svc = _stub()
        with mock.patch.object(sent_store, 'save_phrases') as save:
            out = service.Service.phrases(svc, {'action': 'add', 'text': ' Vlahovic  rinnova ', 'color': 'red',
                                                'label': 'custom', 'label_text': 'esclusiva  jr',
                                                'source': ' Sky   Sport ', 'link_text': 'Leggi  tutto'})
        self.assertEqual(out['phrases'][0], {'text': 'Vlahovic rinnova', 'color': 'red', 'label': 'custom',
                                             'label_text': 'ESCLUSIVA JR', 'source': 'Sky Sport',
                                             'link_text': 'Leggi tutto'})
        save.assert_called_once()

    def test_etichetta_sconosciuta_e_titolo_senza_personalizzato(self):
        svc = _stub()
        with mock.patch.object(sent_store, 'save_phrases'):
            out = service.Service.phrases(svc, {'action': 'add', 'text': 'Ciao', 'label': 'boh', 'label_text': 'X'})
        p = out['phrases'][0]
        self.assertEqual((p['label'], p['label_text'], p['source'], p['link_text']), ('', '', '', ''))

    def test_lettura_vecchie_e_nuove(self):
        rows = ['vecchia', {'text': 'solo colore', 'color': 'blue'},
                {'text': 'piena', 'color': 'black', 'label': 'breaking', 'source': 'Ansa'}]
        with mock.patch.object(sent_store, '_read', return_value=rows):
            out = sent_store.load_phrases()
        self.assertNotIn('label', out[0])
        self.assertNotIn('label', out[1])
        self.assertEqual(out[2], {'text': 'piena', 'color': 'black', 'label': 'breaking', 'label_text': '',
                                  'source': 'Ansa', 'link_text': ''})


if __name__ == '__main__':
    unittest.main()
