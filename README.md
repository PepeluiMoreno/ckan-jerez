# ckan-jerez

> **Datos abiertos del Portal de Transparencia de Jerez de la Frontera**,
> cosechados por [OpenDataManager (ODM)](https://github.com/PepeluiMoreno/OpenDataManager)
> y servidos —a futuro— como un CKAN.

`ckan-jerez` es una **app independiente suscrita a ODM**. No es parte de ODM, no
comparte su base de datos ni su red: se relaciona con él **solo a través de su
API pública**. ODM hace el trabajo pesado (descubrir, inferir, extraer); este
repositorio aporta el **conocimiento del portal de Jerez** y, con los datasets que
ODM produce, construye y mantiene el CKAN.

---

## La idea en una frase

> **ODM es el motor. ckan-jerez es un suscriptor.**
> El cliente le dice a ODM *qué* portal mirar y *cómo* leer cada documento, y
> luego *consume* el resultado. Nada más.

---

## Arquitectura

```
        Portal de Transparencia de Jerez  (TYPO3, /fileadmin/…)
                          │
                          │  (1) ckan-jerez registra el recurso Web Tree
                          │      de Jerez en ODM  ──vía API──►
                          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                     OpenDataManager (motor)                   │
   │                                                               │
   │   Web Tree fetcher ─► inferer ─► variantes por recurso        │
   │        (crawl)        (agrupa)   Censo · Datos · Receta        │
   │                                        │                      │
   │                                  datasets + censo             │
   └─────────────────────────────────────────────────────────────┘
                          │
                          │  (2) ckan-jerez consume datasets/censo ◄──vía API──
                          ▼
                   ckan-jerez  (red y BD PROPIAS)
                          │
                          ▼
                   CKAN de Jerez  (futuro)
```

La frontera es **la API de ODM**. ckan-jerez nunca abre la BD de ODM ni entra en
su red interna: la BD que algún día aparezca aquí será la del **CKAN propio**.

---

## El Web Tree fetcher y sus variantes

El corazón de todo. El **Web Tree fetcher** de ODM recorre el árbol de carpetas
de un portal (no una API: el propio sistema de ficheros publicado), descubre las
**hojas** (documentos) y deja que el **inferer** las agrupe en *propuestas*:

- **serie** — ficheros con un patrón regular (`…/{año}/{mes}/informe.xlsx`), que
  se tratan como una sola colección con dimensiones (año, mes…).
- **bundle** — un montón de ficheros heterogéneos y de nombres irregulares que no
  forman serie limpia; se agrupan *lógicamente* (no es un ZIP: son N ficheros).

Cada recurso promovido lleva una **variante** (preset) que decide *cómo* se lee:

| Variante | `extract_mode` | Qué hace | Cuándo se usa | Ejemplo en Jerez |
|---|---|---|---|---|
| **Censo documental** | `censo` | Registra cada hoja (sección, URL, nombre, formato). **No extrae**: cataloga. | Prosa y ficheros opacos | Resoluciones, decretos, certificados |
| **Extracción de datos** | `datos` | Descarga y **parsea a filas** (xlsx/xls/csv/tsv y tablas PDF). | Ficheros tabulares | Ejecución de gastos, contratos menores |
| **Extracción con receta** | `receta` | Aplica una **receta**: captura *valores concretos* de un documento semiestructurado. | Informes-formulario (el dato son celdas, no una tabla entera) | PMP, remanente de tesorería, resultado presupuestario |

La doctrina que las gobierna: **todo lo que no sea prosa debe acabar como dato.**
La prosa (un PDF narrativo) cae sola al *Censo* porque, al intentar extraerlo,
devuelve 0 filas (guarda anti-prosa). Lo tabular —por formato o por receta— debe
ser *dataset*.

### Recetas: capturar el dato exacto

Una receta busca un rótulo y toma el valor por **posición** dentro de la rejilla:

| `posicion` | Toma… |
|---|---|
| `celda` | el resto de la propia celda del rótulo |
| `derecha` | el **primer** número a la derecha |
| `debajo` | el primer número de la fila siguiente |
| `ultima` | el **último** número de la fila (la última columna) |

Ejemplo real (resultado presupuestario): el valor ajustado vive en la **última
columna** de una megacelda, tras derechos y obligaciones. `derecha` pescaría el
primero (232.468.641,11); `ultima` da el correcto: **6.288.438,43**.

### Carve-outs: rescatar lo que el inferer entierra

A veces el dato queda sepultado dentro de un *bundle* mixto. Dos rescates:

- **Tabular (capacidad genérica de ODM):** las hojas xlsx/csv/tsv enterradas en un
  bundle de prosa se re-agrupan en series propias y se promueven como **datos**.
- **PDF-receta (config de Jerez):** estados como *remanente* o *resultado* van
  dentro del bundle de liquidación; se les da serie propia para que su receta
  enganche.

---

## Cómo se relaciona con ODM (suscripción)

ckan-jerez habla con ODM **solo por su API**:

1. **Registra** el recurso Web Tree de Jerez (su `ROOT`, las carpetas a extraer,
   el catálogo de recetas y los carve-outs) mediante las mutaciones de ODM.
2. **Consume** los datasets y el censo resultantes para construir el CKAN.

> **Estado actual (honesto):** el crawler heredado `scripts/jerez_webtree.py` aún
> hace esto por **import directo de `app.*` + escritura en la BD de ODM** — el
> acoplamiento que esta arquitectura elimina. Su migración a cliente-API es el
> **siguiente paso** y está en lo alto del backlog. La imagen Docker de este repo
> ya está construida para el modelo suscriptor (independiente, sin BD/red de ODM).

---

## Doctrina motor / cliente

> ¿**Verdad universal sobre árboles de documentos web**? → ODM (motor).
> ¿**Hecho del portal de Jerez**? → este repo (cliente).

- **Motor (ODM):** Web Tree fetcher, inferer, anti-prosa, motor de recetas,
  `carve_tabular_series`, lectores de formato.
- **Cliente (aquí):** `ROOT`/`EXTRAER`/`RECETAS`, carve-outs por nombre de
  fichero, y el mapeo a CKAN.

---

## El gate: nada de CKAN antes de tiempo

El CKAN **no nace** hasta que todo lo que no sea prosa se consiga presentar como
datos abiertos. El catálogo del CKAN serán los PDF de prosa no extraíbles; todo lo
tabular (por formato o por receta) debe ser dataset antes.

| Pieza del gate | Estado |
|---|---|
| Tabular por formato (xlsx/csv/tsv) | ✅ (carve genérico) |
| Recetas (PMP / remanente / resultado) | ✅ validadas en vivo |
| Series-receta resilientes a ficheros malos | ✅ |
| Ficheros > 4 MB | ✅ (límite por defecto 50 MB) |
| Morosidad vía XLSX gemelo | ⏳ validar contenido |
| Cobertura de formatos del WebTree (zip/docx/ods) | ⏳ en ODM |

---

## Entorno dockerizado

App **independiente**: imagen propia (no construida sobre ODM), red propia, sin
BD de ODM. Es un **worker** (no un servicio web), invocable bajo demanda o por
cron del host:

```bash
docker compose run --rm ckan-jerez smoke       # ¿responde ODM por su API?
docker compose run --rm ckan-jerez subscribe   # (pendiente) registra el recurso en ODM
docker compose run --rm ckan-jerez publish      # (pendiente) actualiza el CKAN
docker compose run --rm ckan-jerez shell
```

Configuración (`.env.production`, ver `.env.production.example`): `ODM_API_URL`,
`ODM_API_TOKEN`, y —a futuro— `CKAN_URL`/`CKAN_API_TOKEN`.

---

## Despliegue (GitHub Actions + GHCR)

Como el resto de las apps: `push` a `main` → **build** y push de la imagen a
`ghcr.io/pepeluimoreno/ckan-jerez` → **deploy** por SSH (`pull` + smoke). No hay
healthcheck web porque no es un servicio: el *health* es el **smoke** —que ODM
responde por su API—, coherente con un worker suscriptor.

Secretos: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY`, `CKANJEREZ_ENV_PRODUCTION`.

---

## Estructura

```
ckan-jerez/
├── Dockerfile                 # imagen independiente (FROM python:3.11-slim)
├── docker-compose.yml         # worker; red propia; ODM por API
├── docker-compose.prod.yml    # imagen de GHCR
├── docker/entrypoint.sh       # smoke (API de ODM) + comandos del worker
├── .github/workflows/deploy.yml
├── .env.production.example
├── scripts/                   # cliente Jerez (crawler heredado, auditoría, retirada)
└── docs/                      # AUDITORIA + BACKLOG
```

## Backlog

Ver [`docs/BACKLOG.md`](docs/BACKLOG.md): migración a cliente-API de ODM
(crítico), exportador CKAN, validación de los XLSX de morosidad, cierre del gate.
