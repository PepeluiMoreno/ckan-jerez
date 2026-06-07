# Datos Abiertos de Jerez

Portal de datos abiertos del municipio de Jerez de la Frontera. Transforma la
información económico-financiera que el Ayuntamiento publica en su Portal de
Transparencia en un catálogo **CKAN** normalizado: navegable, descargable,
consultable por API e interoperable mediante DCAT.

> Iniciativa ciudadana independiente. Reutiliza información de publicación
> obligatoria; no constituye una fuente oficial del Ayuntamiento.

## 1. Contexto y motivación

El Portal de Transparencia de Jerez está implementado sobre **TYPO3** como un
árbol de carpetas y documentos. En términos de reutilización, equivale a un gran
**panel de corcho con varios miles de documentos prendidos** —hojas de cálculo,
CSV e informes en PDF— organizados por su ubicación de publicación y no por su
contenido.

Esta forma de publicación satisface el requisito legal de *acceso*, pero no el de
*reutilización*: un documento puede leerse, pero el conjunto no puede consultarse,
compararse ni agregarse sin un trabajo manual de descarga y transcripción. El
presente portal resuelve esa carencia convirtiendo el árbol documental en datos
estructurados y estándar, en los que cada magnitud es un registro y cada serie
conserva su histórico anual.

## 2. Arquitectura

El sistema se organiza en tres capas con responsabilidades disjuntas:

```
   Portal de Transparencia de Jerez  (TYPO3 — árbol documental)
                    │
                    ▼
   OpenDataManager (ODM)        Capa de cosecha y extracción
                    │           (descubre, extrae, normaliza)
                    │  API GraphQL + webhook (HMAC-SHA256)
                    ▼
   ckan-jerez (este portal)     Capa de datos abiertos
                    │           (suscribe a ODM y publica el CKAN)
                    │  API CKAN + DCAT
                    ▼
   Consumidores                 Capa de explotación
   p. ej. CityDashboard         (cuadros de mando, análisis, terceros)
```

- **Capa de cosecha — [OpenDataManager](https://github.com/PepeluiMoreno/OpenDataManager).**
  Recorre el árbol del Portal de Transparencia, extrae los documentos tabulares a
  datos y cataloga los documentos de prosa, y expone el resultado por su API.
- **Capa de datos abiertos — `ckan-jerez`.** Es el **único suscriptor de ODM** en
  el dominio de Jerez. Habla con ODM por **GraphQL**: define en él los recursos a
  cosechar y consume los datasets resultantes. Para el Portal de Transparencia de
  Jerez —un árbol documental TYPO3— selecciona el **Web Tree fetcher** y configura
  sus variantes (*censo documental*, *extracción de datos* y *extracción con
  receta*) según el tipo de documento. Publica el resultado como catálogo CKAN y lo
  mantiene actualizado; constituye la fuente de verdad de datos abiertos del
  municipio.
- **Capa de explotación — consumidores.** Aplicaciones que leen el catálogo por
  los protocolos estándar de CKAN/DCAT. Entre ellas,
  [**CityDashboard**](https://github.com/PepeluiMoreno/cityDashboard), un panel de
  control municipal con semáforos de cumplimiento legal (LOEPSF, Ley 15/2010), que
  consume **este portal**.

## 3. Componentes

| Componente | Responsabilidad |
|---|---|
| `data/odm_resources/jerez.json` | Declara los recursos que ODM debe cosechar del portal de Jerez (recurso Web Tree y recetas de extracción). |
| `api/webhooks.py` (`POST /webhooks/odmgr`) | Recibe las notificaciones de ODM. Verifica la firma **HMAC-SHA256** de la cabecera `X-ODM-Signature`. |
| `services/odmgr_sync.py` | Procesa el payload del webhook e ingiere el dataset en la base de datos del portal. |
| `services/odm_client.py` | Cliente **GraphQL** de ODM: define los recursos (mutaciones) y consulta datasets y censo (*queries*). |
| `services/ckan_publisher.py` | Publica y actualiza los conjuntos como *packages* CKAN. |
| Base de datos propia (PostgreSQL) | Estado del portal y del catálogo. Independiente de la de ODM. |

`ckan-jerez` se relaciona con ODM exclusivamente por su **frontera pública** (API
y webhook); no comparte con él base de datos ni red.

## 4. Ciclo de vida del dato

1. **Definición de recursos.** `ckan-jerez` define en ODM, mediante **mutaciones
   GraphQL**, los recursos del Portal de Transparencia de Jerez: selecciona el
   **Web Tree fetcher** y configura sus variantes (*censo*, *datos*, *receta*)
   según cada documento. La declaración local de qué definir reside en
   `data/odm_resources/jerez.json`. Los recursos **no se crean tocando la base de
   datos de ODM, sino por su API GraphQL** — ver la
   [referencia de la API GraphQL de ODM](https://github.com/PepeluiMoreno/OpenDataManager/blob/main/docs/API_GRAPHQL.md)
   y su [esquema (SDL)](https://github.com/PepeluiMoreno/OpenDataManager/blob/main/docs/schema.graphql).
2. **Cosecha.** ODM ejecuta la cosecha del Portal de Transparencia y normaliza el
   resultado.
3. **Notificación.** Al completar una carga, ODM emite un webhook firmado hacia
   `POST /webhooks/odmgr`.
4. **Ingesta.** `services/odmgr_sync.py` valida la firma e incorpora el dataset.
5. **Publicación.** `services/ckan_publisher.py` crea o actualiza el *package*
   CKAN correspondiente.
6. **Refresco.** El ciclo se repite de forma periódica; los históricos se
   conservan por año, permitiendo el seguimiento temporal de cada indicador.

Adicionalmente, `services/odm_client.py` permite la consulta directa por GraphQL
cuando se requiere un *pull* explícito en lugar de esperar la notificación.

## 5. Acceso y reutilización

El catálogo se expone por los mecanismos estándar de CKAN:

- **Web del portal**: navegación y descarga de recursos (CSV, XLSX).
- **API CKAN**: consulta programática de conjuntos y recursos.
- **DCAT**: cosecha del catálogo completo, interoperable con datos.gob.es y el
  portal europeo de datos.

Casos de uso: transparencia y rendición de cuentas, periodismo de datos, análisis
ciudadano y reutilización por aplicaciones de terceros.

## 6. Despliegue

El portal se distribuye como imagen de contenedor en **GHCR**
(`ghcr.io/pepeluimoreno/ckan-jerez`) y se despliega mediante **GitHub Actions**:
cada publicación en `main` construye la imagen, la sube al registro y la despliega
en el servidor, validando su salud (`/health`) antes de dar por bueno el
despliegue.

## 7. Documentación técnica

El detalle de la cosecha —el *Web Tree fetcher* de ODM y sus variantes de
extracción (censo documental, extracción de datos y extracción con receta), la
gramática de recetas y el protocolo de webhook— se documenta en
[`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## Licencia

Datos bajo licencia abierta con atribución. Código bajo licencia libre.
