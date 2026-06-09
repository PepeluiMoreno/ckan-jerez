#!/bin/bash
# Inicialización de ckan-jerez: organización titular y marca del portal.
# Idempotente. source-safe: se ejecuta con `source` desde start_ckan.sh (mismo
# shell que hace `exec` del servidor), así que NO usa `set -e` ni `exit`.
# Usa ckanapi en modo local (-c): no requiere el servidor HTTP levantado.

CKAN_INI="${CKAN_INI:-$APP_DIR/ckan.ini}"
BRANDING="${BRANDING_DIR:-/srv/app/branding}"
ORG_SLUG="ayuntamiento-jerez"

# 1) Organización titular de los datos (si no existe ya).
if ckanapi action organization_show "id=$ORG_SLUG" -c "$CKAN_INI" >/dev/null 2>&1; then
    echo "[init-jerez] organización '$ORG_SLUG' ya existe."
else
    if ckanapi action organization_create -c "$CKAN_INI" \
            "name=$ORG_SLUG" \
            "title=Ayuntamiento de Jerez de la Frontera" \
            "description=Organismo titular de los conjuntos de datos publicados en el portal." \
            >/dev/null 2>&1; then
        echo "[init-jerez] organización '$ORG_SLUG' creada."
    else
        echo "[init-jerez] AVISO: no se pudo crear la organización (¿BD aún no lista?)."
    fi
fi

# 2) Marca del portal (config_option_update, persistido en system_info). Se usa la
#    forma key=value de ckanapi (la de stdin no la consume). Llamadas separadas para
#    que un fallo en una opción no impida las demás.
ckanapi action config_option_update -c "$CKAN_INI" \
        "ckan.site_title=Datos Abiertos de Jerez" \
        "ckan.site_description=Portal de datos abiertos del Ayuntamiento de Jerez de la Frontera" \
        >/dev/null 2>&1 \
    && echo "[init-jerez] título y descripción aplicados." \
    || echo "[init-jerez] AVISO: título/descripción no aplicados."

ckanapi action config_option_update -c "$CKAN_INI" \
        "ckan.site_logo=/base/images/jerez-logo.svg" \
        >/dev/null 2>&1 \
    && echo "[init-jerez] logo aplicado." \
    || echo "[init-jerez] AVISO: logo no aplicado."

CSS="$(cat "$BRANDING/custom.css" 2>/dev/null)"
if [ -n "$CSS" ]; then
    ckanapi action config_option_update -c "$CKAN_INI" \
            "ckan.site_custom_css=$CSS" \
            >/dev/null 2>&1 \
        && echo "[init-jerez] CSS de tema aplicado." \
        || echo "[init-jerez] AVISO: CSS no aplicado."
fi
