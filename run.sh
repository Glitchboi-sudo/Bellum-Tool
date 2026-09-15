#!/usr/bin/env bash
# Lanza el PAX TPV Toolkit desde la raíz del repo.
# Usa el venv local (.venv) si existe; si no, cae a python3 del sistema.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x ".venv/bin/python" ]]; then
    PY=".venv/bin/python"
else
    PY="python3"
fi

# Permite sobreescribir la ruta del binario pax_adb:  PAX_ADB=/ruta ./run.sh
exec "$PY" main.py "$@"
