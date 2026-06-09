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
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Extensiones. ckanext-dcat está en PyPI (arrastra sus dependencias).
# ckanext-spatial (GIS) NO está en PyPI: se instala desde git con sus requisitos
# (GEOS ya disponible vía libgeos-dev). harvest y scheming se añadirán más adelante
# (harvest necesita worker; scheming, un esquema propio).
RUN pip install --no-cache-dir ckanext-dcat
RUN pip install --no-cache-dir "git+https://github.com/ckan/ckanext-spatial.git@master" \
    && pip install --no-cache-dir -r "https://raw.githubusercontent.com/ckan/ckanext-spatial/master/requirements.txt"

# Hooks de arranque (la imagen base ejecuta /docker-entrypoint.d en orden):
#   50_plugins   → activa plugins y ajustes de extensiones en el .ini
#   60_bootstrap → migraciones, permisos DataStore, sysadmin e índice (idempotente)
COPY setup/50_plugins.sh   /docker-entrypoint.d/50_ckan_jerez_plugins.sh
COPY setup/60_bootstrap.sh /docker-entrypoint.d/60_ckan_jerez_bootstrap.sh
RUN chmod +x /docker-entrypoint.d/50_ckan_jerez_plugins.sh \
             /docker-entrypoint.d/60_ckan_jerez_bootstrap.sh

USER ckan
