"""Cuándo la cola olvida un trabajo terminado (spec 023).

La cola guardaba un JSON por trabajo para siempre, y `JobStore.all()` —que lee y
parsea TODOS— es el sustrato de casi toda pregunta (qué falta, qué corre, cuántos
van en el lote, qué mostrar en la lista): el costo de preguntar crecía con cada
reunión. Aquí solo vive la REGLA (pura, con reloj inyectado); borrar es cosa de
`JobStore.prune_history`.

Los terminados se podan; lo demás nunca: pendientes/en curso son trabajo vivo, y
fallidos/cancelados se ven en la lista y su log es la única explicación (los borra
el usuario con "Limpiar fallidas").
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Sequence, Set

from app.transcription.jobs import DONE, TranscriptionJob

# Los dos límites del producto, en un solo sitio (se aplican JUNTOS).
HISTORY_DAYS = 30
MAX_HISTORY = 200

# Borrados por pasada: la deuda histórica se paga en varios arranques, nunca en
# uno. En la cola real 80 borrados costaron 20 ms, pero sobre archivos recién
# escritos se midieron ~16 ms por unlink (el antivirus revisa cada borrado): el
# tope existe para ese peor caso, no para el normal.
MAX_DELETIONS_PER_PASS = 100

# Anterior a cualquier fecha real: un registro sin fecha legible es "viejo",
# nunca inmortal (y nunca revienta la poda).
_OLDEST = datetime.min


def job_age_key(job: TranscriptionJob) -> datetime:
    """Cuándo pasó a ser histórico: finished_at → created_at → lo más viejo."""
    for valor in (getattr(job, "finished_at", ""), getattr(job, "created_at", "")):
        texto = str(valor or "").strip()
        if not texto:
            continue
        try:
            return datetime.fromisoformat(texto)
        except ValueError:
            continue
    return _OLDEST


def prunable_job_ids(
    jobs: Iterable[TranscriptionJob],
    *,
    now: datetime,
    days: int = HISTORY_DAYS,
    max_history: int = MAX_HISTORY,
) -> Set[str]:
    """Ids de trabajos terminados que ya no hace falta conservar.

    Se poda por antigüedad O por exceso de cantidad: sobrevive el terminado que
    esté dentro de la ventana Y entre los `max_history` más recientes.
    """
    terminados = [j for j in jobs if getattr(j, "status", "") == DONE]
    if not terminados:
        return set()
    corte = now - timedelta(days=max(int(days), 0))
    recientes = sorted(terminados, key=job_age_key, reverse=True)
    dentro_del_tope = {j.id for j in recientes[: max(int(max_history), 0)]}
    return {
        j.id
        for j in terminados
        if j.id not in dentro_del_tope or job_age_key(j) < corte
    }


def oldest_first(
    jobs: Iterable[TranscriptionJob], ids: Set[str], *, budget: int = MAX_DELETIONS_PER_PASS
) -> List[str]:
    """Los ids a borrar en ESTA pasada: los más viejos primero, hasta el tope."""
    elegidos = sorted((j for j in jobs if j.id in ids), key=job_age_key)
    return [j.id for j in elegidos[: max(int(budget), 0)]]


def prunable_log_paths(
    log_dir: Path, surviving_jobs: Sequence[TranscriptionJob]
) -> List[Path]:
    """Logs que ya no reclama ningún trabajo (el suyo se podó, o nunca hubo).

    Se reconoce por `log_path` y, para registros antiguos que lo construían de
    otra forma, por el sufijo `_<id>.log`.
    """
    log_dir = Path(log_dir)
    if not log_dir.is_dir():
        return []
    reclamados = set()
    sufijos = []
    for job in surviving_jobs:
        ruta = str(getattr(job, "log_path", "") or "").strip()
        if ruta:
            reclamados.add(Path(ruta).name.casefold())
        if getattr(job, "id", ""):
            sufijos.append(f"_{job.id}.log".casefold())
    sobrantes = []
    for log in log_dir.glob("*.log"):
        nombre = log.name.casefold()
        if nombre in reclamados or any(nombre.endswith(s) for s in sufijos):
            continue
        sobrantes.append(log)
    return sobrantes
