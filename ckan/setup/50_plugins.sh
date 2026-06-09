#!/bin/bash
# Configura las extensiones de ckan-jerez en el .ini en cada arranque.
# IMPORTANTE: este script se ejecuta con `source` desde start_ckan.sh, en el mismo
# shell que luego hace `exec` del servidor. Por eso NO usa `set -e` ni `exit`:
# alterar las opciones del shell o salir abortaría el arranque de CKAN (bucle).

CKAN_INI="${CKAN_INI:-$APP_DIR/ckan.ini}"

PLUGINS="envvars image_view text_view datatables_view datastore dcat structured_data"

SPATIAL_OK=0
if python3 -c "import ckanext.spatial" 2>/dev/null; then
    PLUGINS="$PLUGINS spatial_metadata spatial_query"
    SPATIAL_OK=1
fi

ckan config-tool "$CKAN_INI" "ckan.plugins = $PLUGINS" || echo "[ckan-jerez] AVISO: no se pudieron fijar plugins"
ckan config-tool "$CKAN_INI" "ckanext.dcat.rdf.profiles = euro_dcat_ap_3" || true

if [ "$SPATIAL_OK" = 1 ]; then
    ckan config-tool "$CKAN_INI" "ckanext.spatial.search_backend = solr-spatial-field" || true
    ckan config-tool "$CKAN_INI" "ckan.spatial.srid = 4326" || true
fi

echo "[ckan-jerez] plugins configurados (spatial=$SPATIAL_OK): $PLUGINS"
