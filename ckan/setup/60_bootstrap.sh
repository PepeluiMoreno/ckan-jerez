#!/bin/bash
# Bootstrap idempotente de CKAN en cada arranque del contenedor. Deja la
# instancia operativa sin intervención manual: esquema, permisos del DataStore,
# usuario sysadmin e índice de búsqueda. Seguro de re-ejecutar.
# NO usa 'set -e': un fallo de cualquier paso NO debe impedir que CKAN arranque.

CKAN_INI="${CKAN_INI:-$APP_DIR/ckan.ini}"
MARKER="/var/lib/ckan/.bootstrap_done"

echo "[bootstrap] aplicando migraciones…"
ckan -c "$CKAN_INI" db upgrade || echo "[bootstrap] AVISO: db upgrade falló (se reintentará en el próximo arranque)"

# DataStore: el usuario de solo lectura solo puede SELECT. Idempotente.
if [ -n "$CKAN_DATASTORE_WRITE_URL" ]; then
    echo "[bootstrap] permisos del DataStore…"
    ckan -c "$CKAN_INI" datastore set-permissions \
        | psql "$CKAN_DATASTORE_WRITE_URL" -v ON_ERROR_STOP=0 || \
        echo "[bootstrap] AVISO: no se pudieron fijar permisos del DataStore (¿BD aún no lista?)"
fi

# Usuario sysadmin: crear solo si no existe.
if [ -n "$CKAN_SYSADMIN_NAME" ] && [ -n "$CKAN_SYSADMIN_PASSWORD" ]; then
    if ckan -c "$CKAN_INI" user show "$CKAN_SYSADMIN_NAME" >/dev/null 2>&1; then
        echo "[bootstrap] sysadmin '$CKAN_SYSADMIN_NAME' ya existe."
    else
        echo "[bootstrap] creando sysadmin '$CKAN_SYSADMIN_NAME'…"
        ckan -c "$CKAN_INI" sysadmin add "$CKAN_SYSADMIN_NAME" \
            email="${CKAN_SYSADMIN_EMAIL:-admin@pepelui.es}" \
            password="$CKAN_SYSADMIN_PASSWORD" || \
            echo "[bootstrap] AVISO: no se pudo crear el sysadmin."
    fi
fi

# Índice de búsqueda: reconstruir una sola vez (marca en el volumen) para no
# pagar el coste en cada arranque.
if [ ! -f "$MARKER" ]; then
    echo "[bootstrap] reconstruyendo índice de búsqueda (primer arranque)…"
    if ckan -c "$CKAN_INI" search-index rebuild; then
        touch "$MARKER"
    else
        echo "[bootstrap] AVISO: el índice no se pudo reconstruir; se reintentará en el próximo arranque."
    fi
fi

echo "[bootstrap] completado."
exit 0
