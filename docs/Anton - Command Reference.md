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
| Exportar los datos locales | `anton export ORDER_ID` |

## Opciones globales

| Opción | Uso |
|---|---|
| `--prod` | Lee la configuración de `.env.prod` en vez de `.env`. |
| `--output RUTA` | Define la ruta del archivo generado por `regenerate` o `export`. |
| `--language en\|es` | Cambia el idioma del PDF regenerado. |
| `--lines N` | Define cuántas líneas iniciales muestra `anton logs`. |
| `--no-follow` | Muestra los logs existentes y termina. |
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
└── ORDER_ID-local.pdf
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

`regenerate` y `export` necesitan:

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

