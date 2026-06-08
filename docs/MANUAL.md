# Manual de la consola CKAN-Jerez

Consola de manejo de las suscripciones al servicio de datos abiertos para el portal CKAN-Jerez. Esta guía es para el operador: qué hace cada cosa y cómo se usa. No requiere conocer la fontanería interna.

## Qué es esto

CKAN-Jerez es un **suscriptor** de OpenDataManager (ODM). ODM cosecha portales públicos (entre ellos el de Transparencia de Jerez) y, cuando carga datos nuevos de un recurso, **avisa por webhook** a quienes están suscritos. CKAN-Jerez recibe ese aviso y homogeneiza el dato hacia un catálogo CKAN/DCAT uniforme.

La cadena completa es: Portal de Transparencia → **ODM** (cosecha y extrae) → **CKAN-Jerez** (se suscribe y homogeneiza) → consumidores del CKAN.

La consola habla con ODM **solo por su API pública**; nunca toca su base de datos ni su red interna.

## La pantalla

A la izquierda, una barra con dos vistas y, abajo, los estados del sistema. A la derecha, el contenido.

### Estados (pie de la barra lateral)

- **ODM** — `online` / `offline`: si la consola alcanza ODM.
- **CKAN** — `configurado` / `sin configurar`: si hay un CKAN de destino. Mientras esté sin configurar, las entregas se procesan en memoria (sirve para validar el flujo).
- **Registro en ODM** — `✓ registrada` / `✗ pendiente`: si CKAN-Jerez está dada de alta como aplicación cliente en ODM. **Es condición indispensable** para suscribirse y recibir webhooks. El tooltip muestra la URL de webhook registrada o, si está pendiente, qué falta.
- **Sincronización** — `✓ hace X min` / `reintentando` / `falta config`: estado de la última puesta al día con ODM.
- **RAM consumida** — uso de memoria del contenedor; el color avisa cuando queda poca libre.

No hay botón de sincronizar: la consola se pone al día **sola**, al arrancar y de forma periódica (y reintenta si ODM estaba caído). El alta como aplicación, el registro del webhook y las suscripciones declaradas ocurren en esa sincronización.

## Vista «Recursos»

Es la pantalla principal. Lista los orígenes de datos de los que se abastece CKAN-Jerez. Por defecto muestra **solo los suscritos**; desmarca «solo suscritos» para ver todo el catálogo de ODM y suscribirte a algo nuevo.

Cada fila:

- **Nombre** y **Publisher** (organismo; nombre completo).
- **Suscripción**: una píldora que es además el botón. `✓ suscrito` (púlsala para **desuscribir**) o `suscribir` (púlsala para **suscribir**). Suscribir requiere que el Registro en ODM esté hecho.
- **Última ejecución OK**: cuándo se cargaron datos por última vez con éxito (en verde si fue hace menos de una hora).
- **Acciones**:
  - **Refrescar** — pide a ODM una nueva ejecución del recurso. Para no abusar del proveedor, si el recurso se ejecutó con éxito hace menos de una hora, la consola lo rechaza con un aviso (y ODM lo rechazaría igualmente por su lado).
  - **Clonar** — crea una copia editable del recurso: abre el asistente pre-rellenado con sus valores (nombre con sufijo «(copia)»), para que cambies lo que quieras y lo crees. Es la salida natural cuando un cambio se bloquea por tener suscripciones activas: clona y modifica el clon.
  - **Borrar** — elimina el recurso en ODM. Si tiene suscripciones activas, ODM lo rechaza (guardia de integridad) y la consola muestra el motivo.

Arriba, los **pendientes de crear** (declarados para CKAN-Jerez pero aún no presentes en ODM) aparecen marcados como tales.

Filtros: búsqueda por nombre o publisher, selector de publisher y «solo suscritos».

### «+ Nuevo recurso» (asistente)

Crear un recurso es rellenar un formulario, no editar ningún fichero técnico:

1. Elige **Fetcher** y, si aplica, **Variante**; pulsa «Empezar».
2. Lo que la variante fija aparece bloqueado y a la vista (chips 🔒): no se toca.
3. Rellena lo variable: **Publisher** (del catálogo, uno ya existente en ODM, o nuevo), **Nombre**, **Parámetros** (los de la variante vienen precargados; puedes añadir) y, opcionalmente, un **Schedule** (cron).
4. **Crear en ODM** lo da de alta (si el nombre ya existe, se actualiza; no se duplica). **Previsualizar manifiesto** es opcional, para quien quiera ver el artefacto que se genera.

## Vista «Entregas»

Auditoría de los webhooks que ODM ha entregado a CKAN-Jerez con datos nuevos: cuándo, qué dataset, el código HTTP de la entrega y el error si lo hubo. Es lo que de verdad importa a un suscriptor; las ejecuciones internas de ODM son asunto del operador de ODM (su huella relevante para ti ya está en la columna «última ejecución OK» de Recursos).

## Preguntas frecuentes

**No puedo suscribirme / no llegan entregas.** Mira el estado «Registro en ODM». Si está pendiente, falta completar la configuración del despliegue (la URL pública y el secreto del webhook); en cuanto esté, la sincronización registra el alta y el webhook, y las suscripciones empiezan a entregar.

**Refrescar no hace nada y sale un aviso.** El recurso se actualizó hace menos de una hora; espera. Es una protección, no un error.

**Veo recursos con nombres que no declaré.** Son recursos que ya existían en ODM para el mismo organismo y que CKAN-Jerez **adopta** (se suscribe a ellos) sin redeclararlos. Conviven con los que defines tú.

**¿Por qué un recurso no se crea?** Algunos orígenes están sujetos a la política de ODM (clases de fuente admitidas). Si el alta se rechaza, el motivo aparece en pantalla.
