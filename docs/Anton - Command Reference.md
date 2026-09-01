---
title: Anton - Command Reference
aliases:
  - Anton Commands
  - Comandos de Anton
tags:
  - motifcue
  - anton
  - operaciones
  - referencia
status: active
updated: 2026-09-01
---

# Anton — referencia de comandos

Esta nota documenta los comandos disponibles en el worker local de MotifCue.

> [!important] Entornos
> Sin `--prod`, Anton utiliza `.env`. Con `--prod`, utiliza `.env.prod`. El flag funciona con
> todos los comandos.

## Inicio rápido

```bash
source .venv/bin/activate
anton --help
```

| Objetivo | Comando |
|---|---|
| Ejecutar Anton continuamente | `anton run` |
| Procesar como máximo una orden | `anton once` |
| Ver trabajos locales | `anton status` |
| Seguir los logs | `anton logs` |
| Regenerar un PDF localmente | `anton regenerate ORDER_ID` |
| Repetir el análisis estratégico | `anton reanalyze ORDER_ID` |
| Repetir también el análisis visual | `anton reanalyze ORDER_ID --refresh-images` |
| Exportar los datos locales | `anton export ORDER_ID` |
| Actualizar el knowledge local | `anton knowledge sync` |
| Buscar en el knowledge | `anton knowledge search "CONSULTA"` |

## Opciones globales

| Opción | Uso |
|---|---|
| `--prod` | Lee la configuración de `.env.prod` en vez de `.env`. |
| `--output RUTA` | Define la ruta del archivo generado por `regenerate`, `reanalyze` o `export`. |
| `--language en\|es` | Cambia el idioma del PDF regenerado o reanalizado. |
| `--refresh-images` | Con `reanalyze`, vuelve a descargar y analizar los thumbnails. |
| `--lines N` | Define cuántas líneas iniciales muestra `anton logs`. |
| `--no-follow` | Muestra los logs existentes y termina. |
| `--limit N` | Limita los resultados de `knowledge search` entre 1 y 20. |
| `-h`, `--help` | Muestra la ayuda integrada. |

> [!tip] Posición de los flags
> Puedes escribir `--prod` antes o después del identificador de la orden. Para mantener los
> ejemplos consistentes, esta nota lo coloca al final.

## `anton run`

Mantiene Anton activo, consulta periódicamente si existe una orden y procesa una a la vez.

```bash
anton run
```

Producción:

```bash
anton run --prod
```

Detén el proceso con `Ctrl+C`.

> [!note] Flujo normal
> Anton reclama la orden más antigua disponible, valida la conexión, recopila los datos, analiza
> el contenido, genera el PDF y marca la orden como lista para revisión.

## `anton once`

Busca una sola orden, la procesa y termina. Es el comando recomendado para probar el flujo paso a
paso.

```bash
anton once
```

Producción:

```bash
anton once --prod
```

Si no hay órdenes esperando, Anton lo indica en el log y termina sin procesar nada.

## `anton status`

Muestra los trabajos guardados en la base de datos local.

```bash
anton status
```

Producción:

```bash
anton status --prod
```

Columnas mostradas:

| Columna | Significado |
|---|---|
| `ORDER` | Identificador de la orden. |
| `STAGE` | Última etapa local alcanzada. |
| `ATTEMPTS` | Número de reintentos o reanudaciones. |
| `UPDATED` | Última actualización del trabajo. |

Etapas locales habituales:

```text
CLAIMED → VALIDATED → DATA_COLLECTED → ANALYZING
        → SYNTHESIZED → REPORT_CREATED → COMPLETED
```

También pueden aparecer `NEEDS_RECONNECT` o `FAILED`.

## `anton logs`

Muestra las últimas 100 líneas y continúa siguiendo el archivo de log.

```bash
anton logs
```

Mostrar las últimas 250 líneas:

```bash
anton logs --lines 250
```

Mostrar el contenido actual y terminar:

```bash
anton logs --no-follow
```

Logs de producción:

```bash
anton logs --prod
```

> [!info] Niveles de log
> `LOG_LEVEL=INFO` muestra el flujo operativo. Usa `LOG_LEVEL=DEBUG` temporalmente para revisar
> tiempos, caché, IDs de contenido y llamadas al modelo local. Los logs no deben contener tokens,
> captions, URLs privadas ni prompts completos.

## `anton regenerate`

Regenera un PDF utilizando únicamente lo que Anton conserva localmente para una orden.

```bash
anton regenerate ORDER_ID
```

Salida predeterminada:

```text
reports/ORDER_ID-local.pdf
```

Elegir otra ruta:

```bash
anton regenerate ORDER_ID --output reports/revision-2.pdf
```

Regenerar en español:

```bash
anton regenerate ORDER_ID --language es
```

Regenerar usando `.env.prod`:

```bash
anton regenerate ORDER_ID --prod
```

El comando utiliza:

- El snapshot consolidado de Instagram.
- Los análisis visuales guardados en SQLite.
- La síntesis guardada de la cuenta.
- Las imágenes que sigan disponibles localmente.
- La versión actual del generador de PDF.

> [!success] Operación local
> `regenerate` no reclama órdenes, no consulta Instagram, no llama al backend y no cambia el
> estado remoto de la orden.

> [!warning] Imágenes eliminadas
> Si la orden se procesó cuando `CLEANUP_MEDIA_AFTER_SUCCESS=true`, el reporte puede regenerarse
> con los análisis guardados, pero algunas imágenes o thumbnails podrían no estar disponibles.

## `anton reanalyze`

Genera una síntesis estratégica nueva con el modelo local y luego crea un PDF nuevo.

```bash
anton reanalyze ORDER_ID
```

Salida predeterminada:

```text
reports/ORDER_ID-reanalyzed.pdf
```

Sin opciones adicionales, utiliza el snapshot y los análisis visuales guardados, pero vuelve a
ejecutar el modelo de texto para descubrir patrones, recomendaciones y el plan de 30 días.

Para volver a descargar los thumbnails y repetir también el análisis visual de cada publicación:

```bash
anton reanalyze ORDER_ID --refresh-images
```

También acepta idioma y ruta personalizados:

```bash
anton reanalyze ORDER_ID --refresh-images --language es
anton reanalyze ORDER_ID --output reports/revision-ai.pdf
anton reanalyze ORDER_ID --prod
```

| Comando | Imágenes | Análisis visual | Síntesis estratégica | PDF |
|---|---|---|---|---|
| `regenerate` | Usa las locales | Usa la guardada | Usa la guardada | Nuevo |
| `reanalyze` | Usa las locales | Usa la guardada | Nueva | Nuevo |
| `reanalyze --refresh-images` | Vuelve a descargarlas | Nuevo cuando hay imagen | Nueva | Nuevo |

> [!success] No altera la orden remota
> `reanalyze` no reclama órdenes, no llama al backend de MotifCue y no cambia el estado remoto.
> Solo actualiza la síntesis y, si corresponde, los análisis visuales de la base local de Anton.

> [!warning] URLs temporales
> Las URLs multimedia de Instagram pueden caducar. Si una descarga falla, Anton conserva la
> imagen local y el análisis visual anterior. El reporte puede completarse con esa evidencia
> guardada, y el log identifica qué contenidos no pudieron refrescarse.

## `anton export`

Exporta a JSON toda la información que Anton conserva localmente para una orden.

```bash
anton export ORDER_ID
```

Salida predeterminada:

```text
data/exports/ORDER_ID.json
```

Elegir otra ruta:

```bash
anton export ORDER_ID --output exports/orden-debug.json
```

Exportar usando `.env.prod`:

```bash
anton export ORDER_ID --prod
```

El archivo incluye:

- Respuestas paginadas originales guardadas durante la recopilación.
- Snapshot consolidado utilizado por Anton.
- Datos locales del trabajo.
- Síntesis de la cuenta.
- Análisis visual de cada publicación.
- Inventario de archivos multimedia locales.

> [!warning] Información privada
> El JSON puede contener captions, métricas y URLs de contenido del cliente. Compártelo solamente
> por un canal privado. No contiene el access token de Instagram porque Anton nunca lo recibe.

> [!note] Órdenes antiguas
> Las órdenes recopiladas antes de añadir el archivo de respuestas paginadas tendrán el snapshot
> consolidado, pero posiblemente no cada respuesta HTTP individual.

## `anton knowledge`

Gestiona la biblioteca RAG local que Anton consulta durante la síntesis estratégica.

Antes del primer uso, instala el modelo local de embeddings:

```bash
ollama pull nomic-embed-text
```

Descargar las fuentes oficiales y crear sus embeddings:

```bash
anton knowledge sync
```

Ver fuentes activas, cambios pendientes y errores de actualización:

```bash
anton knowledge status
```

Probar la recuperación semántica:

```bash
anton knowledge search "cómo mejorar la claridad visual de un Reel"
anton knowledge search "branded content disclosure" --limit 3
```

Cuando una fuente activa cambia, Anton guarda la revisión nueva como pendiente y continúa usando
la versión aprobada anterior. Inspecciona la diferencia y después aprueba el cambio:

```bash
anton knowledge diff SOURCE_ID
anton knowledge approve SOURCE_ID
```

> [!success] RAG local
> Los documentos, fragmentos y embeddings se guardan en SQLite. Las consultas de embeddings se
> ejecutan contra el Ollama local configurado; no se envían documentos a un proveedor externo.

> [!important] Jerarquía de evidencia
> El knowledge ofrece contexto y posibles experimentos. Nunca sustituye las métricas ni los
> patrones observados en la cuenta analizada. Anton también conserva el contexto `organic`,
> `paid` o `policy` para evitar aplicar recomendaciones publicitarias como reglas orgánicas.

Consulta [[Anton - Knowledge RAG]] para ver la arquitectura, las fuentes iniciales y el proceso de
aprobación completo.

## Conservación de datos

Para poder regenerar reportes con imágenes sin volver a descargar contenido:

```env
CLEANUP_MEDIA_AFTER_SUCCESS=false
```

Anton guarda la información de cada orden dentro de:

```text
data/
├── anton.db
├── exports/
│   └── ORDER_ID.json
└── orders/
    └── ORDER_ID/
        ├── instagram-snapshot.json
        ├── endpoint-responses/
        │   ├── instagram-data-page-001.json
        │   └── instagram-data-page-002.json
        └── media/
            ├── MEDIA_ID.jpg
            └── ...
```

Los reportes se guardan normalmente en:

```text
reports/
├── ORDER_ID.pdf
├── ORDER_ID-local.pdf
└── ORDER_ID-reanalyzed.pdf
```

## Configuración de desarrollo y producción

Desarrollo:

```bash
cp .env.example .env
anton status
```

Producción:

```bash
cp .env.prod.example .env.prod
anton status --prod
```

> [!danger] No subir secretos
> `.env` y `.env.prod` contienen secretos y nunca deben incluirse en Git ni adjuntarse a una
> exportación.

## Solución de problemas

### No aparece la orden

```bash
anton status
anton logs --lines 250 --no-follow
```

Comprueba que estás usando el entorno correcto. Si la orden fue procesada con `.env.prod`, añade
`--prod` a los comandos locales.

### No existe el snapshot local

`regenerate`, `reanalyze` y `export` necesitan:

```text
data/orders/ORDER_ID/instagram-snapshot.json
```

Verifica `DATA_DIRECTORY` y que el `ORDER_ID` sea exacto.

### El PDF no muestra thumbnails

Comprueba si existen imágenes en:

```text
data/orders/ORDER_ID/media/
```

Para órdenes nuevas, mantén `CLEANUP_MEDIA_AFTER_SUCCESS=false`.

### Ver ayuda integrada

```bash
anton --help
```

## Comandos de mantenimiento del proyecto

Instalar Anton para desarrollo:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Ejecutar las pruebas:

```bash
pytest
ruff check .
```

Actualizar el branch local de staging:

```bash
git switch staging
git pull origin staging
```

## Notas relacionadas

- [[README|MotifCue Anton]]
