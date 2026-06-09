#!/bin/bash
# Crea el usuario de solo lectura y la base de datos del DataStore de CKAN.
# Se ejecuta una sola vez, al inicializar el volumen de datos de PostgreSQL.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE datastore_ro NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN PASSWORD '${DATASTORE_RO_PASSWORD}';
    CREATE DATABASE datastore OWNER "$POSTGRES_USER" ENCODING 'utf-8';
EOSQL

echo "[postgres-init] base de datos 'datastore' y rol 'datastore_ro' creados."
