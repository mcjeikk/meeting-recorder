"""Motor de transcripción instalado AL PRIMER USO (macOS, spec 030).

El `.dmg` solo trae la app y el código del Transcriptor; su entorno (torch,
pyannote, faster-whisper: ~1,5 GB) se instala aquí la primera vez, con permiso
del usuario, en `engine_dir()`:

    engine/
      state.json          absent | installing | ready | failed (+ hash del lock)
      setup.log           salida de cada paso (diagnóstico)
      python/             Python 3.11 gestionado por uv
      transcriptor/       copia del código + .venv + .env (token HF)

Igual que en Windows, la app NUNCA importa el motor: solo lanza su `bin/python`
(constitución III). El `.venv` nuevo se arma en `.venv.partial` y solo se
renombra al final: una instalación a medias jamás pasa por buena.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import psutil

from app.core.platform_paths import cache_dir, engine_dir, venv_python

ABSENT = "absent"
INSTALLING = "installing"
READY = "ready"
FAILED = "failed"

PYTHON_VERSION = "3.11"
LOCK_MACOS = "requirements.lock.macos.txt"
LOCK_MACOS13 = "requirements.lock.macos13.txt"
VERIFY_IMPORTS = "import ctranslate2, faster_whisper, torch, pyannote.audio; print('motor ok')"

_COPY_IGNORE = shutil.ignore_patterns(
    ".venv", ".venv.*", ".env", "__pycache__", "*.pyc", "tests", "salida", "output*"
)


# --- ubicaciones ---------------------------------------------------------------------
def engine_root() -> Path:
    return engine_dir() / "transcriptor"


def state_path() -> Path:
    return engine_dir() / "state.json"


def setup_log_path() -> Path:
    return engine_dir() / "setup.log"


def bundled_source_dir() -> Path:
    """Código del Transcriptor que viaja con la app (o el del repo, en desarrollo)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "transcriptor"
    return Path(__file__).resolve().parents[2] / "transcriptor"


def uv_executable() -> Optional[str]:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidato = Path(base) / "bin" / "uv"
        if candidato.exists():
            return str(candidato)
    propio = os.environ.get("MR_UV")
    if propio and Path(propio).exists():
        return propio
    return shutil.which("uv")


def macos_major(version: Optional[str] = None) -> int:
    texto = version if version is not None else platform.mac_ver()[0]
    try:
        return int((texto or "0").split(".")[0])
    except ValueError:
        return 0


def lock_name_for(major: int) -> str:
    """14+ usa los pins validados; 13 tiene su propio lock (onnxruntime 1.26 no
    publica rueda para 13)."""
    return LOCK_MACOS13 if 0 < major < 14 else LOCK_MACOS


def lock_file(source: Optional[Path] = None, major: Optional[int] = None) -> Path:
    src = source or bundled_source_dir()
    return src / lock_name_for(macos_major() if major is None else major)


def file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


# --- estado persistido ----------------------------------------------------------------
@dataclass
class EngineState:
    state: str = ABSENT
    lock_hash: str = ""
    error: str = ""
    consented: bool = False
    pid: int = 0
    updated: float = 0.0

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "EngineState":
        p = path or state_path()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        campos = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        estado = cls(**campos)
        if estado.state not in (ABSENT, INSTALLING, READY, FAILED):
            estado.state = ABSENT
        return estado

    def save(self, path: Optional[Path] = None) -> None:
        p = path or state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        self.updated = time.time()
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)


@dataclass(frozen=True)
class EngineStatus:
    state: str
    ready: bool          # se puede transcribir YA (aunque haya actualización pendiente)
    outdated: bool       # hay un lock nuevo: reinstalar en segundo plano
    consented: bool
    error: str = ""


def evaluate(
    state: EngineState,
    venv_exists: bool,
    current_lock_hash: str,
    installer_alive: bool,
) -> EngineStatus:
    """Decisión pura: qué significa lo que hay en disco.

    "Listo" = hay un `.venv` que alguna vez terminó bien (`lock_hash`): una
    reinstalación fallida o en curso no quita el motor que ya funcionaba.
    """
    estado, error = state.state, state.error
    if estado == INSTALLING and not installer_alive:
        estado, error = FAILED, error or "La instalación se interrumpió (se cerró la app)"
    listo = venv_exists and bool(state.lock_hash)
    desactualizado = listo and bool(current_lock_hash) and state.lock_hash != current_lock_hash
    return EngineStatus(estado, listo, desactualizado, state.consented, error if estado == FAILED else "")


def status() -> EngineStatus:
    st = EngineState.load()
    # Instancia única: una instalación solo puede estar viva en ESTE proceso.
    vivo = st.pid == os.getpid()
    venv_ok = venv_python(engine_root() / ".venv").exists() and (engine_root() / "transcribe.py").exists()
    return evaluate(st, venv_ok, file_hash(lock_file()), installer_alive=vivo)


def is_ready() -> bool:
    try:
        return status().ready
    except Exception:
        return False


def sync_sources(source: Optional[Path] = None, dest: Optional[Path] = None) -> bool:
    """Actualiza el código del motor (sin tocar `.venv` ni `.env`). Barato: se
    hace en cada arranque, antes de que la cola lance nada."""
    src = source or bundled_source_dir()
    dst = dest or engine_root()
    if not (src / "transcribe.py").exists():
        return False
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=_COPY_IGNORE, dirs_exist_ok=True)
    return True


# --- instalación ----------------------------------------------------------------------
@dataclass(frozen=True)
class Step:
    key: str
    label: str


STEPS: List[Step] = [
    Step("copy", "Copiando el motor"),
    Step("python", "Descargando Python 3.11"),
    Step("venv", "Creando el entorno"),
    Step("packages", "Descargando e instalando librerías (~1,5 GB; tarda varios minutos)"),
    Step("verify", "Comprobando la instalación"),
    Step("finish", "Terminando"),
]

ProgressCb = Callable[[int, int, str], None]


class EngineInstaller:
    """Corre la instalación en un hilo. `pause()`/`resume()` suspenden el paso en
    curso (la grabación siempre manda); `cancel()` lo corta."""

    def __init__(
        self,
        on_progress: ProgressCb,
        on_done: Callable[[bool, str], None],
        source: Optional[Path] = None,
        major: Optional[int] = None,
    ) -> None:
        self._on_progress = on_progress
        self._on_done = on_done
        self._source = source or bundled_source_dir()
        self._major = macos_major() if major is None else major
        self._proc: Optional[subprocess.Popen] = None
        self._paused = False
        self._cancelled = False
        self._thread: Optional[threading.Thread] = None

    # --- control -----------------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="engine-setup")
        self._thread.start()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def pause(self) -> None:
        self._paused = True
        self._signal(suspend=True)

    def resume(self) -> None:
        self._paused = False
        self._signal(suspend=False)

    def cancel(self) -> None:
        self._cancelled = True
        self._paused = False
        proc = self._proc
        if proc and proc.poll() is None:
            self._signal(suspend=False)
            proc.terminate()

    def _signal(self, suspend: bool) -> None:
        proc = self._proc
        if not proc or proc.poll() is not None:
            return
        try:
            padre = psutil.Process(proc.pid)
            for p in [padre, *padre.children(recursive=True)]:
                (p.suspend if suspend else p.resume)()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # --- pasos ---------------------------------------------------------------------
    def _env(self) -> dict:
        env = dict(os.environ)
        env["UV_PYTHON_INSTALL_DIR"] = str(engine_dir() / "python")
        env["UV_CACHE_DIR"] = str(cache_dir() / "uv")
        env["UV_NO_CONFIG"] = "1"
        env["UV_PYTHON_PREFERENCE"] = "only-managed"
        env.pop("VIRTUAL_ENV", None)
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        return env

    def _cmd(self, args: List[str], log) -> None:
        log.write(f"\n$ {' '.join(args)}\n")
        log.flush()
        self._proc = subprocess.Popen(
            args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=self._env(), cwd=str(engine_dir()),
        )
        if self._paused:
            self._signal(suspend=True)
        code = self._proc.wait()
        self._proc = None
        if self._cancelled:
            raise RuntimeError("Instalación cancelada")
        if code != 0:
            raise RuntimeError(f"Falló «{Path(args[0]).name} {args[1] if len(args) > 1 else ''}» (código {code}); detalles en setup.log")

    def _run(self) -> None:
        raiz = engine_root()
        engine_dir().mkdir(parents=True, exist_ok=True)
        lock = lock_file(self._source, self._major)
        st = EngineState.load()
        st.state, st.error, st.pid, st.consented = INSTALLING, "", os.getpid(), True
        st.save()
        ok, error = False, ""
        try:
            uv = uv_executable()
            if not uv:
                raise RuntimeError("No se encontró 'uv' (debería venir dentro de la app)")
            if not lock.exists():
                raise RuntimeError(f"Falta {lock.name} en el motor empaquetado")
            parcial = raiz / ".venv.partial"
            with open(setup_log_path(), "a", encoding="utf-8") as log:
                log.write(f"\n==== instalación {time.strftime('%Y-%m-%d %H:%M:%S')} · macOS {self._major} · {lock.name}\n")
                total = len(STEPS)
                for i, step in enumerate(STEPS, start=1):
                    if self._cancelled:
                        raise RuntimeError("Instalación cancelada")
                    self._on_progress(i, total, step.label)
                    while self._paused and not self._cancelled:
                        time.sleep(0.5)
                    if step.key == "copy":
                        if not sync_sources(self._source, raiz):
                            raise RuntimeError("No se encontró el código del Transcriptor en la app")
                    elif step.key == "python":
                        self._cmd([uv, "python", "install", PYTHON_VERSION], log)
                    elif step.key == "venv":
                        shutil.rmtree(parcial, ignore_errors=True)
                        self._cmd([uv, "venv", "--relocatable", "--python", PYTHON_VERSION, str(parcial)], log)
                    elif step.key == "packages":
                        self._cmd(
                            [uv, "pip", "install", "--python", str(venv_python(parcial)),
                             "-r", str(raiz / lock.name)],
                            log,
                        )
                    elif step.key == "verify":
                        self._cmd([str(venv_python(parcial)), "-c", VERIFY_IMPORTS], log)
                    elif step.key == "finish":
                        _swap_venv(raiz, parcial)
                        try:
                            subprocess.run([uv, "cache", "clean"], env=self._env(),
                                           stdout=log, stderr=subprocess.STDOUT, timeout=300)
                        except Exception:
                            pass
            ok = True
        except Exception as e:  # noqa: BLE001 — se informa en la UI, nunca se cae la app
            error = str(e) or type(e).__name__
        st = EngineState.load()
        st.pid = 0
        if ok:
            st.state, st.error, st.lock_hash = READY, "", file_hash(lock)
        else:
            st.state, st.error = FAILED, error
        st.save()
        self._on_done(ok, error)


def _swap_venv(raiz: Path, parcial: Path) -> None:
    """`.venv.partial` → `.venv` sin dejar nunca un hueco a medias."""
    final = raiz / ".venv"
    viejo = raiz / ".venv.old"
    shutil.rmtree(viejo, ignore_errors=True)
    if final.exists():
        final.rename(viejo)
    parcial.rename(final)
    shutil.rmtree(viejo, ignore_errors=True)
