#!/bin/bash
# Worker de ckan-jerez. App independiente, SUSCRITA a ODM por su API pública.
# No toca la BD ni la red interna de ODM.
set -e
CMD="${1:-help}"

smoke() {
  : "${ODM_API_URL:?falta ODM_API_URL}"
  echo "[smoke] comprobando que ODM responde en ${ODM_API_URL} (solo API, sin BD ni red interna)..."
  curl -fsS -m 10 "${ODM_API_URL%/}/health" >/dev/null \
    && echo "[smoke] OK — ODM alcanzable como proveedor vía API"
}

case "$CMD" in
  smoke) smoke ;;
  shell) exec /bin/bash ;;
  subscribe|crawl|publish)
    cat <<EOF
[pendiente] '$CMD' requiere el cliente-API de ODM.
ckan-jerez es una app SUSCRITA a ODM: registra el recurso Web Tree de Jerez y
consume sus datasets/censo vía la API de ODM (GraphQL/HTTP) — nunca su BD ni su
red. El crawler heredado (scripts/jerez_webtree.py) aún acopla por import directo
+ BD y NO corre en esta imagen subscriptora; su migración a la API de ODM es el
siguiente paso (ver docs/BACKLOG.md).
EOF
    ;;
  help|*)
    cat <<EOF
ckan-jerez — app suscrita a OpenDataManager para los datos de Jerez.
Uso:  docker compose run --rm ckan-jerez <comando>
  smoke      verifica que ODM responde por su API pública (ODM_API_URL)
  subscribe  (pendiente) registra el recurso Web Tree de Jerez en ODM vía API
  publish    (pendiente) publica/actualiza el CKAN a partir de los datasets de ODM
  shell      shell interactiva
EOF
    ;;
esac
