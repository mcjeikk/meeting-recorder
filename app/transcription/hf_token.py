"""Token de Hugging Face para identificar hablantes (spec 030).

pyannote descarga su modelo de Hugging Face y exige (1) un token y (2) haber
aceptado los términos del modelo con esa cuenta. Sin token el Transcriptor
transcribe igual pero SIN hablantes, en silencio: por eso la app lo valida
antes de guardarlo y dice exactamente cuál de las dos cosas falta.

El token vive SOLO en `<motor>/.env` (permisos 600), que es donde el CLI ya lo
lee (`load_dotenv(RAIZ / ".env")`). Nunca en config.json, en logs ni completo
en pantalla.
"""
from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

ENV_KEY = "HUGGINGFACE_TOKEN"
MODEL_ID = "pyannote/speaker-diarization-community-1"
TOKENS_URL = "https://huggingface.co/settings/tokens"
MODEL_URL = f"https://huggingface.co/{MODEL_ID}"
_WHOAMI = "https://huggingface.co/api/whoami-v2"
_GATED_FILE = f"https://huggingface.co/{MODEL_ID}/resolve/main/config.yaml"

OK = "ok"
INVALID = "invalid"          # token mal escrito, revocado o de otra cosa
TERMS = "terms"              # token válido, pero faltan los términos del modelo
NETWORK = "network"          # sin conexión: no se puede saber

_LINE = re.compile(rf"^\s*{ENV_KEY}\s*=\s*(.*?)\s*$")


@dataclass(frozen=True)
class Check:
    result: str
    message: str
    user: str = ""


def looks_like_token(token: str) -> bool:
    return bool(re.fullmatch(r"hf_[A-Za-z0-9]{20,}", (token or "").strip()))


def mask(token: Optional[str]) -> str:
    t = (token or "").strip()
    if not t:
        return ""
    return f"{t[:3]}…{t[-4:]}" if len(t) > 8 else "…"


# --- validación en línea ----------------------------------------------------------
Fetch = Callable[[str, str], int]


def _http_status(url: str, token: str) -> int:
    req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as e:
        return int(e.code)


def _whoami_name(token: str) -> str:
    import json

    req = urllib.request.Request(_WHOAMI, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return str(json.loads(resp.read().decode("utf-8")).get("name", ""))
    except Exception:
        return ""


def validate(token: str, fetch: Optional[Fetch] = None) -> Check:
    token = (token or "").strip()
    if not looks_like_token(token):
        return Check(INVALID, "Eso no parece un token de Hugging Face (empiezan por «hf_»).")
    fetch = fetch or _http_status
    try:
        quien = fetch(_WHOAMI, token)
        if quien in (401, 403):
            return Check(INVALID, "Hugging Face rechazó el token (¿revocado o mal copiado?).")
        if quien >= 400:
            return Check(NETWORK, f"Hugging Face respondió {quien}; prueba en un rato.")
        modelo = fetch(_GATED_FILE, token)
    except (urllib.error.URLError, OSError, TimeoutError):
        return Check(NETWORK, "Sin conexión con Hugging Face: no se pudo comprobar el token.")
    if modelo in (401, 403):
        return Check(
            TERMS,
            "El token es válido, pero esa cuenta aún no aceptó los términos del modelo "
            f"de hablantes. Ábrelo ({MODEL_URL}), pulsa «Agree and access» y vuelve a probar.",
        )
    if modelo >= 400:
        return Check(NETWORK, f"No se pudo comprobar el modelo (HTTP {modelo}).")
    nombre = _whoami_name(token) if fetch is _http_status else ""
    return Check(OK, "Token listo: se identificarán los hablantes.", nombre)


# --- almacenamiento ------------------------------------------------------------------
def read_token(env_file: Path) -> Optional[str]:
    try:
        lineas = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for linea in lineas:
        m = _LINE.match(linea)
        if m:
            valor = m.group(1).strip().strip('"').strip("'")
            if valor and not valor.startswith("hf_xxx"):
                return valor
    return None


def write_token(env_file: Path, token: Optional[str]) -> None:
    """Guarda (o borra, con None) el token conservando el resto del `.env`."""
    try:
        lineas = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        lineas = []
    lineas = [l for l in lineas if not _LINE.match(l)]
    if token:
        lineas.append(f"{ENV_KEY}={token.strip()}")
    env_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = env_file.with_name(env_file.name + ".tmp")
    tmp.write_text("\n".join(lineas) + ("\n" if lineas else ""), encoding="utf-8")
    if os.name == "posix":
        os.chmod(tmp, 0o600)
    os.replace(tmp, env_file)
