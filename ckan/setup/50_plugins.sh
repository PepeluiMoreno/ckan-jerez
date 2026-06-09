#!/bin/bash
# Configura las extensiones de ckan-jerez en el .ini en cada arranque.
# Idempotente: ckan config-tool sobrescribe la clave si ya existe.


CKAN_INI="${CKAN_INI:-$APP_DIR/ckan.ini}"

# Plugins activos. Orden recomendado: vistas y datastore primero, luego las
# extensiones. envvars permite seguir configurando por variables CKAN__*.
# NOTA: spatial_metadata/spatial_query NO se activan aún — requieren inicializar
# la tabla PostGIS (ckan spatial initdb) y un Solr con campo espacial; se añadirán
# en una segunda fase. ckanext-spatial está instalado, solo no activado.
PLUGINS="envvars image_view text_view datatables_view datastore \
dcat structured_data"

ckan config-tool "$CKAN_INI" "ckan.plugins = $PLUGINS"

# ── DCAT ──────────────────────────────────────────────────────────────────
# Perfil europeo; el exportador de ckan-jerez ya emite metadatos DCAT.
ckan config-tool "$CKAN_INI" "ckanext.dcat.rdf.profiles = euro_dcat_ap_3"

echo "[ckan-jerez] plugins y extensiones configurados: $PLUGINS"
exit 0
