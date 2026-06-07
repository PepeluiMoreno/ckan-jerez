# Backlog — ckan-jerez

Pendientes del cliente Jerez (app suscrita a ODM). Lo que sea capacidad genérica
de motor va al backlog de
[OpenDataManager](https://github.com/PepeluiMoreno/OpenDataManager).

Convención: `[ ]` pendiente · `[x]` hecho · `[-]` descartado.

## Pendiente

- [ ] **Páginas de operador** (HTML sobre el FastAPI): Fuentes (asistente nueva-fuente), Suscripciones, Datos/Refresco, Entregas.
- [ ] Retirar el crawler heredado (`scripts/jerez_webtree.py`) ahora que la definición va por manifiesto y la ingesta por webhook.
- [ ] **Orquestar el ciclo completo desde ckan-jerez**: crear el crawler →
  `discover` → revisar candidatos → `promote_candidate` aplicando la *política de
  variantes* de Jerez (prosa→censo, tabular→datos, informe-formulario→receta) →
  datasets. Y **retirar los recursos Jerez heredados de ODM** con `deleteResource`.
  CAUTELA de secuencia: CityDashboard aún consume algunos recursos Jerez
  directamente de ODM; no borrarlos hasta que CityDashboard consuma el CKAN de
  ckan-jerez. Orden: (1) ckan-jerez asume definir+descubrir+promover, (2) migrar
  CityDashboard al CKAN, (3) borrar lo heredado en ODM.

- [ ] **Aprovisionador idempotente**: aplicar `data/odm_resources/jerez.json` a
  ODM con `odm_client` (crear/actualizar/dejar intacto cada recurso Web Tree según
  difiera o no de lo ya definido).
- [ ] **Servicios de webhook**: `api/webhooks.py` (`POST /webhooks/odmgr`) +
  `services/odmgr_sync.py` (verificación HMAC + ingesta del dataset notificado).
- [ ] **Exportador CKAN** (`services/ckan_publisher.py`): proyectar los datasets
  de ODM como *packages* CKAN.
- [ ] **App web + BD propia**: FastAPI con `/health` y PostgreSQL propio
  (para alojar el webhook y el catálogo).
- [ ] **(B, al FINAL de la tanda) migrar la auth a token de servicio (Bearer)**
  cuando ODM lo soporte: hoy se usa la opción A (cuenta de servicio + login por
  cookie); B es lo más seguro/ortodoxo. Depende del item correspondiente en el
  backlog de ODM.

## Hecho

- [x] **Bootstrap del suscriptor** (`services/bootstrap.py` + `app/bootstrap_cli.py`): cierra el lazo entrada↔salida — aprovisiona el catálogo, asegura la Application (find-or-create) y su webhook (`set_application_webhook`), resuelve IDs por (publisher, name) y suscribe los recursos que falten (`subscribe_resource`), todo idempotente. Comando `bootstrap [--apply]` (dry-run por defecto). Cliente ampliado con `applications`/`resources`/`dataset_subscriptions`. 28 tests verdes.
- [x] **Salida homogénea (REST-apificador)**: `services/ckan_publisher.py` mapea
  cualquier dataset de ODM a un *package* CKAN con metadatos DCAT (distribuciones
  con formato/mimetype, publisher como owner_org, extras de versión/origen) y lo
  hace upsert idempotente (sinks `HttpCkanSink` vía Action API y `MemorySink`).
  `services/odmgr_sync.py`: `verify_hmac` (HMAC-SHA256) + `handle_notification`
  genérico. `api/webhooks.py` (POST /webhooks/odmgr) y `app/main.py` (FastAPI con
  /health). Imagen pasada de worker a servidor web (uvicorn). 23 tests verdes.
- [x] **`odm_client` extendido**: manifiestos (`manifest_template`, `import_manifest`),
  identidad/suscripción (`create_application`, `set_application_webhook`,
  `subscribe_resource`) y observabilidad (`resource_executions`,
  `application_notifications`). Documentos validados contra el SDL real.
- [x] **Aprovisionamiento por manifiesto** (`services/provisioning.py`): catálogo
  HETEROGÉNEO (multi-publisher, multi-fetcher) → un manifiesto por publisher
  (`build_manifests`) e import idempotente (`provision_catalog`); asistente
  'nueva fuente' sobre `manifestTemplate` (`build_source_manifest`/`provision_source`).
  `jerez.json` reestructurado como catálogo. 17 tests verdes.
- [x] **Orquestación discover → política → promote** (`services/pilot.py`):
  política de variantes de Jerez (token de receta→receta, tabular puro→datos,
  prosa/mixto→censo) y `discover_and_promote` (dry-run por defecto). Tests verdes.
- [x] **Pilotaje del discovery por GraphQL** (`services/odm_client.py`):
  `execute_resource` (dispara el discovery del crawler), `resource_candidates`
  (lista candidatos), `promote_candidate` (con `variant`: censo/datos/receta) y
  `discard_candidate_resource` (borrar recursos). Documentos validados contra el
  esquema real de ODM.

- [x] **Cliente GraphQL de ODM** (`services/odm_client.py`): login de cuenta de
  servicio (A, con re-login ante error de permiso), `resolve_webtree` y
  `create_webtree_resource`. Documentos y variables **validados contra el esquema
  real de ODM** (`tests/test_odm_client.py`).
- [x] **Declaración de recursos** (`data/odm_resources/jerez.json`): Web Tree de
  Jerez en sus tres variantes (censo / datos / receta).
