#!/usr/bin/env bash
# Construye "Grabador de Reuniones.app" y su .dmg en un Mac Apple Silicon (spec 030).
#
#   packaging/macos/build.sh            # usa la versión de pyproject.toml
#   MR_VERSION=1.2.0 packaging/macos/build.sh
#
# Requiere Python 3.11 (python3.11 en el PATH o PYTHON=/ruta). Crea su propio
# entorno en build/macos-venv: no toca el .venv de desarrollo.
# Salida: dist/Grabador de Reuniones.app y dist/GrabadorDeReuniones-<versión>-macos-arm64.dmg
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

APP_NAME="Grabador de Reuniones"
PYTHON="${PYTHON:-python3.11}"
UV_VERSION="${UV_VERSION:-0.13.5}"
BUILD="$ROOT/build/macos"
VENV="$ROOT/build/macos-venv"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Este script es para macOS Apple Silicon (arm64)." >&2
  exit 1
fi

if [[ -z "${MR_VERSION:-}" ]]; then
  MR_VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n1)"
fi
export MR_VERSION
echo "==> Versión $MR_VERSION"

echo "==> Entorno de build ($PYTHON)"
"$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip wheel >/dev/null
"$VENV/bin/python" -m pip install -r requirements.txt "pyinstaller>=6.10" pillow "uv==$UV_VERSION"

echo "==> uv que viaja en la app"
MR_UV_BIN="$("$VENV/bin/python" -c 'import uv; print(uv.find_uv_bin())')"
export MR_UV_BIN
"$MR_UV_BIN" --version

echo "==> Ícono"
mkdir -p "$BUILD"
MR_ICNS="$BUILD/icon.icns"
"$VENV/bin/python" - "$ROOT/assets/icon.ico" "$MR_ICNS" <<'PY'
import sys
from PIL import Image
img = Image.open(sys.argv[1])
if hasattr(img, "ico"):
    img = img.ico.getimage(max(img.ico.sizes()))
img = img.convert("RGBA")
if img.size[0] < 512:
    img = img.resize((512, 512), Image.LANCZOS)
img.save(sys.argv[2], format="ICNS")
PY
export MR_ICNS

echo "==> PyInstaller"
rm -rf "dist/$APP_NAME" "dist/$APP_NAME.app"
"$VENV/bin/pyinstaller" --noconfirm --clean \
  --workpath "$BUILD/work" --distpath "$ROOT/dist" \
  packaging/macos/GrabadorReuniones.spec

APP="$ROOT/dist/$APP_NAME.app"

echo "==> Firma ad-hoc (sin cuenta de Apple Developer)"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

echo "==> Autocomprobación del paquete"
"$APP/Contents/MacOS/$APP_NAME" --self-check

echo "==> .dmg"
STAGE="$BUILD/dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Aplicaciones"
cp "packaging/macos/LEEME - Primera vez.txt" "$STAGE/"
DMG="$ROOT/dist/GrabadorDeReuniones-$MR_VERSION-macos-arm64.dmg"
rm -f "$DMG"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null

SIZE_MB=$(( $(stat -f%z "$DMG") / 1024 / 1024 ))
echo "==> Listo: $DMG (${SIZE_MB} MB)"
if (( SIZE_MB > 500 )); then
  echo "El .dmg pasa de 500 MB (spec 030, SC-006)." >&2
  exit 1
fi
