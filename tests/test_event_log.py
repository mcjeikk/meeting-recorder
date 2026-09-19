"""El rastro de una cola desatendida (spec 026).

Lo que se prueba es sobre todo lo que NO debe pasar: que no levante, que no
crezca sin límite y que una línea a medias no arrastre al resto.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.transcription.event_log import (
    EventLog,
    default_path,
    read_events,
    read_trail,
)


class TestAppend(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.log = EventLog(self.root / "events.jsonl")

    def test_one_line_per_entry_with_time_and_kind(self) -> None:
        self.log.append("run_start", file="uno", n=2)
        self.log.append("settle", file="uno", status="done")
        lineas = self.log.path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lineas), 2)
        primera = json.loads(lineas[0])
        self.assertEqual(primera["kind"], "run_start")
        self.assertEqual(primera["file"], "uno")
        self.assertEqual(primera["n"], 2)
        self.assertGreater(primera["t"], 0)
        self.assertRegex(primera["hora"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_creates_its_folder(self) -> None:
        log = EventLog(self.root / "nueva" / "carpeta" / "events.jsonl")
        log.append("ui", file="uno")
        self.assertTrue(log.path.is_file())

    def test_an_unserialisable_value_still_writes_a_line(self) -> None:
        self.log.append("raro", objeto=object(), ruta=Path("c:/x"))
        entradas = list(read_events(self.log.path))
        self.assertEqual(len(entradas), 1)
        self.assertIn("object", entradas[0]["objeto"])

    def test_an_unwritable_path_is_silent(self) -> None:
        # La ruta es una CARPETA: abrirla para escribir falla siempre.
        carpeta = self.root / "soy_carpeta"
        carpeta.mkdir()
        log = EventLog(carpeta)
        log.append("ui", file="uno")  # no debe levantar
        self.assertTrue(carpeta.is_dir())

    def test_snapshot_records_what_the_window_received(self) -> None:
        self.log.snapshot(
            {
                "id": "j1",
                "media_path": r"C:\videos\Reunión de equipo.mp4",
                "status": "running",
                "stage": "Identificando hablantes…",
                "progress": 61,
                "eta_epoch": 1_700_000_000.0,
                "batch_pos": 2,
                "batch_total": 5,
                "batch_eta_epoch": 1_700_003_000.0,
                "eta_paused": False,
                "note": "",
                "error": "",
            }
        )
        e = list(read_events(self.log.path))[0]
        self.assertEqual(e["kind"], "ui")
        self.assertEqual(e["file"], "Reunión de equipo")
        self.assertEqual((e["batch_pos"], e["batch_total"]), (2, 5))
        self.assertEqual(e["progress"], 61)
        self.assertEqual(e["stage"], "Identificando hablantes…")

    def test_snapshot_never_carries_transcribed_text(self) -> None:
        # Solo campos de estado: si alguien mete texto de la transcripción en el
        # snapshot, no debe viajar al rastro (FR-009).
        self.log.snapshot(
            {"id": "j1", "media_path": "a.mp4", "status": "done", "texto": "hola qué tal"}
        )
        crudo = self.log.path.read_text(encoding="utf-8")
        self.assertNotIn("hola qué tal", crudo)


class TestBounded(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_rotates_at_the_cap_and_keeps_the_newest(self) -> None:
        log = EventLog(self.root / "events.jsonl", max_bytes=2000)
        for i in range(200):
            log.append("ui", i=i, relleno="x" * 100)
        self.assertLess(log.path.stat().st_size, 2000 + 500)
        rotado = Path(str(log.path) + ".1")
        self.assertTrue(rotado.is_file())
        # Lo más reciente sobrevive y el rastro completo se lee en orden.
        todo = read_trail(log.path)
        self.assertEqual(todo[-1]["i"], 199)
        self.assertLess(todo[0]["i"], todo[-1]["i"])

    def test_only_one_spare_file_is_kept(self) -> None:
        log = EventLog(self.root / "events.jsonl", max_bytes=500)
        for i in range(400):
            log.append("ui", i=i, relleno="y" * 100)
        archivos = sorted(p.name for p in self.root.glob("events.jsonl*"))
        self.assertEqual(archivos, ["events.jsonl", "events.jsonl.1"])


class TestReading(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_a_truncated_last_line_does_not_lose_the_rest(self) -> None:
        destino = self.root / "events.jsonl"
        destino.write_text(
            '{"kind": "ui", "i": 1}\n{"kind": "ui", "i": 2}\n{"kind": "ui", "i"',
            encoding="utf-8",
        )
        entradas = list(read_events(destino))
        self.assertEqual([e["i"] for e in entradas], [1, 2])

    def test_a_missing_file_reads_as_empty(self) -> None:
        self.assertEqual(list(read_events(self.root / "no_existe.jsonl")), [])
        self.assertEqual(read_trail(self.root / "no_existe.jsonl"), [])

    def test_default_path_sits_next_to_the_queue(self) -> None:
        self.assertEqual(default_path(self.root).name, "events.jsonl")
        self.assertEqual(default_path(self.root).parent, self.root)


if __name__ == "__main__":
    unittest.main()
