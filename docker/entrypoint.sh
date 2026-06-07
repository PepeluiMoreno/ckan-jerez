#!/bin/bash
# ckan-jerez: app INDEPENDIENTE suscrita a ODM por su API pública.
# Homogeneizador/REST-apificador: recibe el webhook de ODM y publica el CKAN.
# No toca la BD ni la red interna de ODM.
set -e
CMD="${1:-serve}"

smoke() {
  : "${ODM_API_URL:?falta ODM_API_URL}"
  echo "[smoke] comprobando que ODM responde en ${ODM_API_URL} (solo API)..."
  curl -fsS -m 10 "${ODM_API_URL%/}/health" >/dev/null \
    && echo "[smoke] OK — ODM alcanzable como proveedor vía API"
}

case "$CMD" in
  serve)
    echo "[serve] ckan-jerez en :${PORT:-8000} — webhook POST /webhooks/odmgr, /health"
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  smoke) smoke ;;
  shell) exec /bin/bash ;;
  help|*)
    cat <<EOF
ckan-jerez — homogeneizador/REST-apificador suscrito a OpenDataManager (Jerez).
Uso:  docker compose run --rm ckan-jerez <comando>
  serve   (defecto) sirve el webhook de ODM y /health (uvicorn)
  smoke   verifica que ODM responde por su API pública (ODM_API_URL)
  shell   shell interactiva
EOF
    ;;
esac
