# Arquitectura técnica

Documento de referencia del portal **Datos Abiertos de Jerez** (`ckan-jerez`):
cómo se cosecha el Portal de Transparencia, cómo se integra con
OpenDataManager (ODM) y cómo se publica el catálogo CKAN.

## 1. Principio rector

> Todo lo que no sea prosa se presenta como datos abiertos.

La información del portal municipal se clasifica en dos clases. Los **documentos
de datos** (hojas de cálculo, tablas, magnitudes contenidas en informes) se
extraen a registros reutilizables. Los **documentos de prosa** (resoluciones,
memorias) se catalogan como recurso documental, con sus metadatos y su enlace de
origen. El catálogo CKAN es, por tanto, mayoritariamente datos, y solo
residualmente catálogo documental.

## 2. Separación motor / cliente

El sistema distingue de forma estricta dos ámbitos:

- **Motor (ODM):** toda verdad universal sobre árboles de documentos web —el
  rastreo, la inferencia de estructura, los lectores de formato, el motor de
  recetas y la separación tabular/prosa.
- **Cliente (`ckan-jerez`):** todo hecho propio del portal de Jerez —qué carpetas
  cosechar, qué recetas aplicar y cómo mapear el resultado a CKAN.

`ckan-jerez` no contiene lógica genérica de extracción: la delega en ODM y se
limita a configurarla y a consumir su salida.

## 3. La cosecha: el Web Tree fetcher

ODM cosecha el portal con su **Web Tree fetcher**, que recorre el árbol de
carpetas del sitio (no una API: el propio sistema de ficheros publicado),
descubre las hojas (documentos) y delega en el *inferer* su agrupación en
propuestas:

- **serie**: documentos con patrón regular (`…/{año}/{mes}/informe.xlsx`),
  tratados como una colección con dimensiones (año, mes…);
- **bundle**: documentos heterogéneos de nombres irregulares, agrupados
  lógicamente.

Cada recurso resultante se procesa según una **variante**:

| Variante | `extract_mode` | Función | Aplicación |
|---|---|---|---|
| **Censo documental** | `censo` | Registra cada hoja (sección, URL, nombre, formato) sin extraer. | Prosa y ficheros opacos. |
| **Extracción de datos** | `datos` | Descarga y parsea a registros (XLSX/XLS/CSV/TSV y tablas en PDF). | Documentos tabulares. |
| **Extracción con receta** | `receta` | Captura magnitudes concretas de un documento semiestructurado. | Informes-formulario, donde el dato son celdas y no una tabla completa. |

### 3.1. Recetas

Una receta localiza un rótulo en la rejilla del documento y toma el valor por
**posición**:

| `posicion` | Valor tomado |
|---|---|
| `celda` | el resto de la propia celda del rótulo |
| `derecha` | el primer número a la derecha |
| `debajo` | el primer número de la fila inferior |
| `ultima` | el último número de la fila (última columna) |

La posición `ultima` resuelve los estados contables en los que la magnitud se
sitúa en la última columna tras cifras intermedias (p. ej. el resultado
presupuestario ajustado, posterior a derechos y obligaciones).

### 3.2. Recuperación de datos en agrupaciones mixtas

Cuando un documento de datos queda agrupado dentro de un *bundle* de prosa, se
rescata para no perderlo:

- **Por formato (genérico):** las hojas tabulares (XLSX/CSV/TSV) contenidas en un
  *bundle* mixto se reagrupan en series propias y se publican como datos.
- **Por receta (específico de Jerez):** estados como el remanente de tesorería o
  el resultado presupuestario, contenidos en agrupaciones de liquidación, reciben
  serie propia para que su receta se aplique.

## 4. Integración con ODM

`ckan-jerez` es el único suscriptor de ODM en el dominio de Jerez, y se relaciona
con él por su frontera pública: **GraphQL** para definir recursos y consultar
datos, y **webhook** para recibir las notificaciones de carga.

**Autenticación.** El cliente opera con una **cuenta de servicio** de ODM dotada
de un rol de mínimo privilegio (`recursos.crear`, `recursos.editar` y lectura).
Se autentica en `/api/auth/login` y reutiliza la cookie de sesión, re-autenticando
ante un error de permiso. (`services/odm_client.py`.)

### 4.1. Declaración de recursos

`data/odm_resources/jerez.json` declara lo que ODM debe cosechar; `ckan-jerez`
aplica esa declaración a ODM mediante **mutaciones GraphQL**
(`services/odm_client.py`), seleccionando el **Web Tree fetcher** —el adecuado
para el árbol documental del portal— y configurando sus variantes (*censo*,
*datos*, *receta*). Cada recurso sigue el esquema:

```json
{
  "name": "Nombre del recurso en ODM",
  "fetcher_name": "WEB_TREE",
  "publisher_acronimo": "AYTO-JEREZ",
  "target_table": "nombre_tabla",
  "load_mode": "replace",
  "description": "Descripción del recurso",
  "params": { "root_url": "…", "extract_mode": "…", "recetas": [] }
}
```

La definición es idempotente: crea, actualiza o deja intacto cada recurso según
difiera o no de lo ya definido en ODM.

> **Los recursos se crean en ODM por su API GraphQL, nunca tocando su base de
> datos.** El contrato y las operaciones (incluido el flujo de discovery) están
> documentados en la API de ODM:
> [`docs/API_GRAPHQL.md`](https://github.com/PepeluiMoreno/OpenDataManager/blob/main/docs/API_GRAPHQL.md)
> y el esquema [`docs/schema.graphql`](https://github.com/PepeluiMoreno/OpenDataManager/blob/main/docs/schema.graphql).

### 4.2. Notificación por webhook (push)

Al completar una carga, ODM emite `POST /webhooks/odmgr` con el dataset publicado.
El cuerpo se firma con **HMAC-SHA256** y la firma viaja en la cabecera
`X-ODM-Signature`. `services/odmgr_sync.py` recalcula la firma con el secreto
compartido y, solo si coincide, procesa el payload e ingiere el dataset.

Esquema del payload:

```json
{
  "dataset": { "id": "…", "resource_name": "…", "version": "…" },
  "download_urls": { "data": "…", "metadata": "…" }
}
```

### 4.3. Consulta por GraphQL (pull)

`services/odm_client.py` consulta la API GraphQL de ODM cuando se requiere obtener
datasets o el censo bajo demanda, sin esperar a la notificación.

## 5. Publicación CKAN

`services/ckan_publisher.py` proyecta cada dataset de ODM sobre un *package* CKAN:
el nombre del recurso como título, sus ficheros como *resources*, las dimensiones
como *extras* y la sección de origen como clasificación. El catálogo queda
disponible por la API de CKAN y es cosechable vía DCAT.

## 6. Despliegue

El portal es una aplicación web (FastAPI) con base de datos PostgreSQL propia. Se
publica como imagen en GHCR y se despliega con GitHub Actions, que valida el
endpoint `/health` antes de confirmar el despliegue. La configuración (URL y
secreto de webhook de ODM, credenciales de CKAN) se inyecta por entorno.
