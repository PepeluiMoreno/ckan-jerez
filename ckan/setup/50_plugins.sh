#!/bin/bash
# Configura las extensiones de ckan-jerez. Se ejecuta con `source` desde
# start_ckan.sh, en el mismo shell que luego hace `exec` del servidor; por eso NO
# usa `set -e` ni `exit`, y exporta CKAN__PLUGINS para que persista tras el exec.
#
# Los plugins se fijan EXPORTANDO CKAN__PLUGINS (no por el .ini): el plugin envvars
# reaplica esa variable en runtime y pisaría cualquier valor del .ini. La imagen
# base exporta una lista mínima; aquí la ampliamos con dcat y (si está) spatial.

CKAN_INI="${CKAN_INI:-$APP_DIR/ckan.ini}"

export CKAN__PLUGINS="envvars image_view text_view datatables_view datastore dcat structured_data"

SPATIAL_OK=0
if python3 -c "import ckanext.spatial" 2>/dev/null; then
    export CKAN__PLUGINS="$CKAN__PLUGINS spatial_metadata spatial_query"
    SPATIAL_OK=1
fi

# Ajustes que el .ini conserva (no hay variable de entorno que los pise):
ckan config-tool "$CKAN_INI" "ckanext.dcat.rdf.profiles = euro_dcat_ap_3" || true
if [ "$SPATIAL_OK" = 1 ]; then
    ckan config-tool "$CKAN_INI" "ckanext.spatial.search_backend = solr-spatial-field" || true
    ckan config-tool "$CKAN_INI" "ckan.spatial.srid = 4326" || true
fi

echo "[ckan-jerez] CKAN__PLUGINS exportado (spatial=$SPATIAL_OK): $CKAN__PLUGINS"
