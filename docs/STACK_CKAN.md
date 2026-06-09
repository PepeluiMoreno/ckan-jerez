# Stack CKAN de ckan-jerez (ckan.pepelui.es)

Instancia CKAN **2.11** (última estable) que recibe los datasets de ODM y los
publica como portal de datos abiertos. Es el destino del exportador
`services/ckan_publisher.py`. Corre en la **red propia** de ckan-jerez, detrás de
Traefik, igual que el panel `ckan-mgr.pepelui.es`.

## Componentes

| Servicio          | Imagen                              | Función                          |
|-------------------|-------------------------------------|----------------------------------|
| `ckan`            | `ckan-jerez/ckan:2.11` (build)      | Web CKAN + extensiones           |
| `ckan-db`         | `postgis/postgis:16-3.4`            | BD de CKAN + DataStore + PostGIS |
| `ckan-solr`       | `ckan/ckan-solr:2.11-solr9-spatial` | Índice de búsqueda (spatial)     |
| `ckan-redis`      | `redis:7`                           | Colas / caché                    |
| `ckan-datapusher` | `ckan/datapusher:0.0.20`            | Carga tabular al DataStore       |

La imagen `ckan` añade sobre la base oficial: **ckanext-dcat** (DCAT-AP),
**ckanext-spatial** (GIS), **ckanext-harvest** y **ckanext-scheming**.

## Requisitos en el host

- Red externa de Traefik (`traefik_public`) ya existente, con `websecure` y
  `letsencrypt` (lo mismo que usa el panel).
- DNS `ckan.pepelui.es` apuntando al host.
- `.env.production` con las variables de `.env.ckan.example` rellenadas.

## Levantar el stack

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ckan.yml \
  up -d --build
```

## Primer arranque (automático)

El contenedor `ckan` se **autoinicializa** en cada arranque mediante
`ckan/setup/60_bootstrap.sh` (idempotente): aplica migraciones, fija los permisos
del DataStore, crea el usuario sysadmin (`CKAN_SYSADMIN_*`) si no existe y
reconstruye el índice de búsqueda la primera vez. No hace falta ejecutar comandos
a mano: al levantar el stack, CKAN queda operativo.

> Si necesitas forzar una reindexación, borra la marca `/var/lib/ckan/.bootstrap_done`
> del volumen `ckan_storage` y reinicia el contenedor.

## Conectar el exportador

1. En CKAN (`https://ckan.pepelui.es`), entra como sysadmin y crea una **cuenta de
   servicio** y su **API token**.
2. En `.env.production` de la app, apunta el exportador a la instancia:
   ```
   CKAN_URL=https://ckan.pepelui.es
   CKAN_API_TOKEN=<token de la cuenta de servicio>
   ```
3. Crea la **organización** de Jerez (será el `owner_org` de los packages). El
   `ckan_publisher` mapea cada dataset de ODM a un package bajo esa organización.

A partir de aquí, cada notificación de ODM (webhook) que recibe ckan-jerez se
traduce en un `package_create`/`package_update` idempotente contra esta instancia.

## Nota sobre versiones

CKAN 2.11.5 (abr. 2026) es la última estable. La 2.12 (cierre de la serie 2.x,
antesala de 3.0) aún no tiene release; cuando salga, basta con cambiar el tag de
`ckan/ckan-base` y `ckan/ckan-solr` y reconstruir la imagen.
