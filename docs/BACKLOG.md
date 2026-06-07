# Backlog — ckan-jerez

Pendientes del **cliente Jerez** (app suscrita a ODM). Lo que sea capacidad
genérica de motor va al backlog de
[OpenDataManager](https://github.com/PepeluiMoreno/OpenDataManager), no aquí.

Convención: `[ ]` pendiente · `[x]` hecho · `[-]` descartado (con motivo).

## Pendiente

- [ ] **CRÍTICO — Cliente-API de ODM (suscripción real)**: hoy
  `scripts/jerez_webtree.py` acopla con ODM por **import directo de `app.*` y
  escritura en su BD** (`SessionLocal`). La arquitectura es: ckan-jerez es una app
  **independiente suscrita a ODM por su API**, sin tocar su BD ni su red. Migrar:
  (a) registrar/actualizar el recurso Web Tree de Jerez (ROOT, EXTRAER, RECETAS,
  carve-outs) vía **mutaciones GraphQL** de ODM; (b) leer datasets/censo vía API.
  La imagen Docker ya está hecha para este modelo (independiente); falta el código.

- [ ] **Exportador CKAN** (`scripts/publicar_ckan_jerez.py`): mapear las
  candidatas/datasets de ODM → packages CKAN — título, resources (URLs),
  dimensiones→extras, sección→clasificación. Primero vía Action API; luego DCAT
  cosechable. El **censo** de ODM es el insumo del catálogo documental.

- [ ] **Validar contenido de los XLSX de morosidad** (24 ficheros) que el carve
  tabular de ODM rescata: ¿forman dataset coherente (mismo esquema entre años)? Si
  no, receta/parser a medida. (La morosidad en PDF —Anexos Ley 15/2010— es tabla
  densa multi-bloque; la vía buena es el XLSX gemelo.)

- [ ] **Cerrar el gate "no-prosa → datos abiertos"** antes de publicar el CKAN.
  Estado: tabular por formato ✓; recetas PMP/remanente/resultado ✓; morosidad vía
  XLSX (validar); >4 MB ✓. Residuo **dependiente de ODM**: cobertura completa de
  formatos del WebTree (zip/docx/ods).

## Hecho

- [x] **Recetas validadas en vivo**: PMP mensual, remanente de tesorería (total y
  gastos generales), resultado presupuestario ajustado (`posicion:"ultima"` =
  6.288.438,43).
- [x] **Familia Web Tree de Jerez extraída**: `EXTRAER` (5 tablas reales),
  `RECETAS` (PMP/remanente/resultado) y carve-outs operativos.
- [x] **Entorno dockerizado + despliegue** (GHCR + GitHub Actions) en el modelo
  **subscriptor**: imagen independiente, red propia, ODM solo por su API.
