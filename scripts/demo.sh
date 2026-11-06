#!/usr/bin/env bash
# Arranca la demo de ComParte en macOS/Linux:  ./scripts/demo.sh   (HORA=15:30 PUERTO=8080 para cambiarlos)
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${COMPARTE_VENV:-.venv}"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet -r requirements.txt
echo "Abre http://127.0.0.1:${PUERTO:-8000}  (Ctrl+C para detener)"
exec "$VENV/bin/python" -m comparte --puerto "${PUERTO:-8000}" --hora-demo "${HORA:-16:00}" --reiniciar
