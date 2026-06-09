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

# 2) Marca del portal: título, descripción, logo y CSS propio (config_option_update,
#    persistido en system_info). El CSS se lee del fichero empaquetado.
PAYLOAD=$(python3 - "$BRANDING/custom.css" <<'PY' 2>/dev/null
import json, sys
css = ""
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        css = f.read()
except Exception:
    pass
print(json.dumps({
    "ckan.site_title": "Datos Abiertos de Jerez",
    "ckan.site_description": "Portal de datos abiertos del Ayuntamiento de Jerez de la Frontera",
    "ckan.site_logo": "/base/images/jerez-logo.svg",
    "ckan.site_custom_css": css,
}))
PY
)

if [ -n "$PAYLOAD" ] && printf '%s' "$PAYLOAD" | ckanapi action config_option_update -c "$CKAN_INI" >/dev/null 2>&1; then
    echo "[init-jerez] branding aplicado (título, logo y CSS)."
else
    echo "[init-jerez] AVISO: no se pudo aplicar el branding."
fi
