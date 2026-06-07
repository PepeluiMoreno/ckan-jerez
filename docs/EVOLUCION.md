# Evolución y estado del proyecto (interno)

Cuaderno de desarrollo de ckan-jerez. **No es la cara pública** del repositorio
(eso es el `README.md`): aquí va el estado real, las decisiones y lo pendiente.

## Origen

Extraído de [OpenDataManager](https://github.com/PepeluiMoreno/OpenDataManager)
en la separación motor/cliente. ODM = motor genérico; ckan-jerez = cliente/
suscriptor de Jerez. El crawler, recetas y carve-outs de Jerez vivían en ODM
(`scripts/jerez_webtree.py`, `retire_jerez_legacy.py`, `auditoria_contenido_webtree.py`,
`docs/AUDITORIA_jerez_hijos.md`) y se sacaron a este repo. Doctrina: verdad
universal sobre árboles web → ODM; hecho del portal de Jerez → aquí.

## Arquitectura objetivo

App **independiente suscrita a ODM por su API pública**. BD propia (la del CKAN),
red propia. **Nunca** la BD ni la red de ODM.

## Estado actual (honesto)

- La imagen Docker y el compose ya están en el **modelo subscriptor**
  (independiente, red propia, ODM vía `ODM_API_URL`).
- **Pero** `scripts/jerez_webtree.py` todavía acopla con ODM por **import directo
  de `app.*` + escritura en su BD** (`SessionLocal`). No corre en la imagen
  subscriptora. Por eso los comandos `subscribe`/`publish` del worker figuran como
  *pendiente*.

## Migración pendiente (crítica)

Reescribir el cliente para que: (a) **registre/actualice** el recurso Web Tree de
Jerez (`ROOT`/`EXTRAER`/`RECETAS`/carve-outs) vía **mutaciones GraphQL** de ODM;
(b) **lea** datasets/censo vía API. Sin importar `app.*`, sin tocar la BD de ODM.

## El gate "no-prosa → datos abiertos"

| Pieza | Estado |
|---|---|
| Tabular por formato (xlsx/csv/tsv) | ✅ carve genérico en ODM |
| Recetas (PMP / remanente / resultado) | ✅ validadas en vivo |
| Series-receta resilientes a ficheros malos | ✅ |
| Ficheros > 4 MB | ✅ (default 50 MB en ODM) |
| Morosidad vía XLSX gemelo | ⏳ validar contenido |
| Cobertura de formatos WebTree (zip/docx/ods) | ⏳ en ODM |

## Recetas validadas en vivo (contra PDF reales)

- PMP mensual.
- Remanente de tesorería: total = 222.081.219,48 ; gastos generales = 39.677.571,37.
- Resultado presupuestario ajustado (`posicion:"ultima"`) = 6.288.438,43.

## Decisiones / correcciones

- **No compartir BD ni red de ODM.** ckan-jerez es subscriptor por API. La
  dockerización inicial lo había montado mal (compartía BD/red de ODM); corregido
  a imagen independiente, red propia y ODM solo por su API pública.
