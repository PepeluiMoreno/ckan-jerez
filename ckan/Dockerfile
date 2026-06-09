# Imagen CKAN de ckan-jerez: CKAN 2.11 (última estable, 2.11.5 — abr. 2026) con
# las extensiones más comunes para un portal de datos abiertos español:
#   - ckanext-dcat      → interoperabilidad DCAT/DCAT-AP-ES (lo que publica el exportador)
#   - ckanext-spatial   → capacidades GIS (campos espaciales, búsqueda por bbox)
# (harvest y scheming se añadirán más adelante: harvest necesita worker; scheming, esquema propio)
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
RUN pip install --no-cache-dir ckanext-dcat ckanapi
RUN pip install --no-cache-dir "git+https://github.com/ckan/ckanext-spatial.git@master" \
    && pip install --no-cache-dir -r "https://raw.githubusercontent.com/ckan/ckanext-spatial/master/requirements.txt"

# Hooks de arranque (la imagen base ejecuta /docker-entrypoint.d en orden):
#   50_plugins   → activa plugins y ajustes de extensiones en el .ini
#   60_bootstrap → migraciones, permisos DataStore, sysadmin e índice (idempotente)
# Marca del portal: CSS de tema (lo lee el script de init) y logo servido como
# estático en /base/images/. Sustituir jerez-logo.svg por el logotipo oficial
# manteniendo el nombre reemplaza la marca sin tocar nada más.
COPY branding/ /srv/app/branding/
COPY branding/jerez-logo.svg /srv/app/src/ckan/ckan/public/base/images/jerez-logo.svg

# Hooks de arranque (la imagen base ejecuta /docker-entrypoint.d en orden):
#   50_plugins   → activa plugins y ajustes de extensiones
#   60_bootstrap → migraciones, permisos DataStore, sysadmin e índice (idempotente)
#   70_init      → organización titular y marca del portal (idempotente)
COPY setup/50_plugins.sh   /docker-entrypoint.d/50_ckan_jerez_plugins.sh
COPY setup/60_bootstrap.sh /docker-entrypoint.d/60_ckan_jerez_bootstrap.sh
COPY setup/70_init_jerez.sh /docker-entrypoint.d/70_ckan_jerez_init.sh
RUN chmod +x /docker-entrypoint.d/50_ckan_jerez_plugins.sh \
             /docker-entrypoint.d/60_ckan_jerez_bootstrap.sh \
             /docker-entrypoint.d/70_ckan_jerez_init.sh

USER ckan
