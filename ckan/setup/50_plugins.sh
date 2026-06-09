#!/bin/bash
# Configura las extensiones de ckan-jerez en el .ini en cada arranque.
# Idempotente. spatial se activa SOLO si la extensión importa, para que un fallo
# de la extensión no impida arrancar CKAN.
set -e

CKAN_INI="${CKAN_INI:-$APP_DIR/ckan.ini}"

PLUGINS="envvars image_view text_view datatables_view datastore dcat structured_data"

SPATIAL_OK=0
if python3 -c "import ckanext.spatial" 2>/dev/null; then
    PLUGINS="$PLUGINS spatial_metadata spatial_query"
    SPATIAL_OK=1
fi

ckan config-tool "$CKAN_INI" "ckan.plugins = $PLUGINS"

# DCAT: perfil europeo; el exportador de ckan-jerez ya emite metadatos DCAT.
ckan config-tool "$CKAN_INI" "ckanext.dcat.rdf.profiles = euro_dcat_ap_3"

# Spatial / GIS: solo si la extensión está disponible.
if [ "$SPATIAL_OK" = 1 ]; then
    ckan config-tool "$CKAN_INI" "ckanext.spatial.search_backend = solr-spatial-field"
    ckan config-tool "$CKAN_INI" "ckan.spatial.srid = 4326"
fi

echo "[ckan-jerez] plugins configurados (spatial=$SPATIAL_OK): $PLUGINS"
