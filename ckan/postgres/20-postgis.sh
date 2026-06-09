#!/bin/bash
# Habilita PostGIS (ckanext-spatial guarda las geometrías en la BD de CKAN).
set -e

for DBNAME in "$POSTGRES_DB" datastore; do
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DBNAME" <<-EOSQL
        CREATE EXTENSION IF NOT EXISTS postgis;
EOSQL
    echo "[postgres-init] PostGIS habilitado en '$DBNAME'."
done
