# ckan-jerez

Cliente de explotación del **Portal de Transparencia de Jerez de la Frontera**
sobre [OpenDataManager (ODM)](https://github.com/PepeluiMoreno/OpenDataManager).

ODM es el **motor genérico** (crawler Web Tree, inferer, recetas, fetchers,
parsers). Este repositorio es el **cliente Jerez**: la configuración y los
scripts específicos del portal de Jerez y —a futuro— la construcción y el
mantenimiento de su CKAN.

## Qué hay aquí

- `scripts/jerez_webtree.py` — siembra y descubre el portal de Jerez como recurso
  Web Tree de ODM: `ROOT`, `PATH_PREFIX`, `INCLUDE`, lista `EXTRAER`, catálogo
  `RECETAS` y los carve-outs (remanente, resultado, y el tabular genérico del
  motor).
- `scripts/retire_jerez_legacy.py` — retira recursos Jerez heredados (soft-delete
  idempotente, `--dry-run` / `--apply`).
- `scripts/auditoria_contenido_webtree.py` — auditoría del contenido del árbol.
- `docs/AUDITORIA_jerez_hijos.md` — auditoría de los hijos del crawler.
- `docs/BACKLOG.md` — pendientes del cliente (exportador CKAN, refactor a
  cliente-API, validaciones).

## Dependencia de ODM

Estos scripts **importan `app.*` de ODM** y escriben directamente en su base de
datos (acoplamiento por import directo, heredado). Para ejecutarlos, ODM debe ser
importable — instálalo en modo editable o añádelo al `PYTHONPATH`:

```bash
pip install -e ../OpenDataManager
# o bien:
export PYTHONPATH=../OpenDataManager
python scripts/jerez_webtree.py
```

Requiere una versión de ODM que incluya las capacidades de motor que el cliente
usa: `carve_tabular_series` (grouping) y `posicion:"ultima"` (recetas).

## Doctrina: separación motor / cliente

El criterio para decidir dónde vive cada cosa:

> ¿Es una **verdad universal sobre árboles de documentos web**? → ODM (motor).
> ¿Es un **hecho del portal de Jerez**? → este repo (cliente).

- **Motor (ODM):** anti-prosa, motor de recetas, inferer, `web_tree_fetcher`,
  `carve_tabular_series`, expansión de archivos, lectores de formato.
- **Cliente (aquí):** `ROOT`/`EXTRAER`/`RECETAS`, carve-outs por nombre de
  fichero, mapeo a CKAN.

## CKAN (futuro)

El CKAN **no nace** hasta que todo lo que no sea prosa se consiga presentar como
datos abiertos. La porción de catálogo serán los PDF de prosa no extraíbles; todo
lo tabular (por formato o por receta) debe ser dataset antes. Plan en
`docs/BACKLOG.md`.
