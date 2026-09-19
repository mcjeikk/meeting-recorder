"""Guardar un registro de la cola no debe perderse por un bloqueo momentáneo.

Encontrado en el rastro de un lote real (spec 026 → 027): el hilo de la UI y el
del worker guardaban el mismo job con el mismo temporal y `os.replace` falló con
`PermissionError`; el job quedó marcado como fallido y se reintentó.
"""
from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.transcription.jobs import JobStore


class TestAtomicSave(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = JobStore(base=self.root / "tx")
        media = self.root / "reunion.mp4"
        media.write_bytes(b"fake")
        job = self.store.enqueue(str(media))
        assert job is not None
        self.job = job

    def _tmps(self) -> list:
        return sorted(p.name for p in self.store.queue_dir.glob("*.tmp"))

    def test_many_threads_saving_the_same_job_all_succeed(self) -> None:
        # Estrés a propósito muy por encima de la app (que guarda unas pocas
        # veces por segundo): en Windows un lector abierto impide reemplazar el
        # archivo, y así se reproduce el PermissionError que vio el rastro.
        errores: list = []

        def guardar(n: int) -> None:
            try:
                for _ in range(40):
                    copia = self.store._load(self.store._path(self.job.id))
                    self.assertIsNotNone(copia, "un registro ocupado no es un registro ausente")
                    copia.attempts = n
                    self.store.save(copia)
                    self.store.all()  # leer todo a la vez que otros escriben
            except Exception as e:  # noqa: BLE001
                errores.append(e)

        hilos = [threading.Thread(target=guardar, args=(i,)) for i in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(30)

        self.assertEqual(errores, [], f"guardar concurrente falló: {errores}")
        self.assertIsNotNone(self.store._load(self.store._path(self.job.id)))
        self.assertEqual(self._tmps(), [], "no debe quedar ningún temporal")

    def test_a_momentary_lock_is_retried(self) -> None:
        real = os.replace
        llamadas = {"n": 0}

        def falla_dos_veces(src, dst):
            llamadas["n"] += 1
            if llamadas["n"] <= 2:
                raise PermissionError(5, "Acceso denegado")
            return real(src, dst)

        self.job.attempts = 7
        with patch("app.transcription.jobs.os.replace", side_effect=falla_dos_veces):
            self.store.save(self.job)

        self.assertEqual(llamadas["n"], 3)
        self.assertEqual(self.store._load(self.store._path(self.job.id)).attempts, 7)
        self.assertEqual(self._tmps(), [])

    def test_a_permanent_failure_still_raises_and_leaves_no_temp(self) -> None:
        # Si de verdad no se puede escribir, el llamador debe enterarse: un job
        # que cambia de estado en silencio es peor que un error visible.
        with patch(
            "app.transcription.jobs.os.replace",
            side_effect=PermissionError(5, "Acceso denegado"),
        ):
            with self.assertRaises(PermissionError):
                self.store.save(self.job)
        self.assertEqual(self._tmps(), [])

    def test_two_threads_never_share_a_temp_file(self) -> None:
        # Un mismo hilo puede reescribir su temporal (reintento); lo que no puede
        # pasar es que dos hilos escriban el mismo: ahí estaba la carrera.
        duenos: dict = {}
        real_write = Path.write_text

        def espia(self_path, *a, **kw):
            nombre = Path(self_path).name
            if nombre.endswith(".tmp"):
                duenos.setdefault(nombre, set()).add(threading.get_ident())
            return real_write(self_path, *a, **kw)

        with patch.object(Path, "write_text", espia):
            hilos = [
                threading.Thread(target=lambda: self.store.save(self.job))
                for _ in range(4)
            ]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join(30)

        compartidos = {n: h for n, h in duenos.items() if len(h) > 1}
        self.assertEqual(compartidos, {}, f"temporal compartido entre hilos: {compartidos}")
        self.assertEqual(len(duenos), 4, f"un temporal por hilo: {sorted(duenos)}")
        self.assertTrue(all(str(os.getpid()) in n for n in duenos))

    def test_a_stray_temp_is_not_read_as_a_job(self) -> None:
        (self.store.queue_dir / "basura.12.34.tmp").write_text("{}", encoding="utf-8")
        self.assertEqual(len(self.store.all()), 1)


if __name__ == "__main__":
    unittest.main()
