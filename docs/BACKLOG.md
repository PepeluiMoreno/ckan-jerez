# Backlog — ckan-jerez

Pendientes del **cliente Jerez**. Lo que sea capacidad genérica de motor va al
backlog de [OpenDataManager](https://github.com/PepeluiMoreno/OpenDataManager),
no aquí.

Convención: `[ ]` pendiente · `[x]` hecho · `[-]` descartado (con motivo).

## Pendiente

- [ ] **Exportador CKAN** (`scripts/publicar_ckan_jerez.py`): mapear las
  candidatas Web Tree → packages CKAN — `suggested_name`→título (vía `infer()`),
  `matched_urls`→resources, dimensiones→extras, sección→clasificación. Primero vía
  Action API; después, cosechable DCAT. El **censo** (modo censo del
  `web_tree_fetcher`, que emite sección/url/nombre/formato) es el insumo natural
  del catálogo documental.

- [ ] **Refactor a cliente-API limpio (patrón SIPI)**: hoy `jerez_webtree.py`
  acopla con ODM por import directo (`from app.*`) y escribe su BD
  (`SessionLocal`). Migrar la siembra/promoción a las **mutaciones GraphQL** de
  ODM, para que Jerez sea cliente de la API pública y no del esquema interno.

- [ ] **Validar contenido de los XLSX de morosidad** (24 ficheros) que
  `carve_tabular_series` rescata del bundle: ¿forman un dataset coherente (mismo
  esquema entre años)? Si no, receta/parser a medida. (La morosidad en PDF —
  Anexos Ley 15/2010 — es tabla densa multi-bloque que la gramática no expresa; la
  vía buena es el XLSX gemelo.)

- [ ] **Cerrar el gate "no-prosa → datos abiertos"** antes de publicar el CKAN.
  Estado: tabular por formato ✓ (`carve_tabular_series`); recetas PMP / remanente /
  resultado ✓; morosidad vía XLSX (pendiente validar); >4 MB ✓ (default 50 en
  ODM). Residuo **dependiente de ODM**: cobertura completa de formatos del WebTree
  (zip/docx/ods) — anotado en el backlog de ODM.

## Hecho

- [x] **Recetas validadas en vivo contra los PDF reales**: PMP mensual, remanente
  de tesorería (total y gastos generales), resultado presupuestario ajustado
  (`posicion:"ultima"` = 6.288.438,43).
- [x] **Extracción de la familia Web Tree de Jerez**: `EXTRAER` (5 tablas reales),
  `RECETAS` (PMP/remanente/resultado) y carve-outs (remanente, resultado, tabular
  genérico) operativos en `jerez_webtree.py`.
