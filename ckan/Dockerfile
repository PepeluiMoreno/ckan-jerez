# Imagen CKAN de ckan-jerez: CKAN 2.11 (última estable, 2.11.5 — abr. 2026) con
# las extensiones más comunes para un portal de datos abiertos español:
#   - ckanext-dcat      → interoperabilidad DCAT/DCAT-AP-ES (lo que publica el exportador)
#   - ckanext-spatial   → capacidades GIS (campos espaciales, búsqueda por bbox)
#   - ckanext-harvest   → recolección de catálogos externos
#   - ckanext-scheming  → esquemas de metadatos a medida (base para DCAT-AP-ES)
#
# Parte de la imagen base oficial, que ya trae Filestore + DataStore preconfigurados.
FROM ckan/ckan-base:2.11

# Dependencias de sistema para ckanext-spatial (GEOS) y compilación.
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-dev \
        python3-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Extensiones (se instalan en el venv de CKAN, $APP_DIR/../venv vía pip de la imagen base).
# Se fijan a las ramas compatibles con CKAN 2.11.
RUN pip install --no-cache-dir \
        ckanext-dcat \
        ckanext-scheming \
        ckanext-harvest \
        ckanext-spatial

# Requisitos extra de las extensiones (parsers DCAT, geo, etc.).
RUN pip install --no-cache-dir \
        -r https://raw.githubusercontent.com/ckan/ckanext-dcat/master/requirements.txt \
        -r https://raw.githubusercontent.com/ckan/ckanext-spatial/master/requirements.txt \
    || echo "AVISO: revisa los requirements de las extensiones para la versión fijada"

# Hook de arranque: configura los plugins y ajustes de las extensiones en el .ini
# antes de levantar CKAN. La imagen base ejecuta los scripts de /docker-entrypoint.d.
COPY setup/ckan_jerez_setup.sh /docker-entrypoint.d/99_ckan_jerez_setup.sh
RUN chmod +x /docker-entrypoint.d/99_ckan_jerez_setup.sh

USER ckan
