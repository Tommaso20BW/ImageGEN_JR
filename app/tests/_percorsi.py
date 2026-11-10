"""Rende importabili il servizio (app/) e il motore grafico LiveScore JR senza impostare PYTHONPATH.

Il motore si cerca dove lo mette il workflow (_graphics_core) o accanto a questo repository
(LiveScore_JR). Se PYTHONPATH è già impostato non cambia nulla.
"""
import importlib.util
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]

if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

if importlib.util.find_spec('livescore') is None:
    for engine in (APP.parent / '_graphics_core', APP.parent.parent / 'LiveScore_JR'):
        if (engine / 'livescore').is_dir():
            sys.path.insert(0, str(engine))
            break
