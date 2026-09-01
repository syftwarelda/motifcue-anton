---
title: Anton - Knowledge RAG
aliases:
  - Anton Knowledge
  - MotifCue RAG
tags:
  - motifcue
  - anton
  - rag
  - knowledge
status: active
updated: 2026-09-01
---

# Anton — Knowledge RAG

Anton utiliza una biblioteca local y versionada para complementar el análisis de cada cuenta con
información estratégica aprobada. La evidencia de la cuenta siempre tiene prioridad.

## Flujo

```text
Fuentes permitidas
    ↓
Descarga y limpieza
    ↓
Revisión versionada
    ↓
Fragmentos de aproximadamente 1.400 caracteres
    ↓
Embeddings locales con Ollama
    ↓
Índice local en SQLite
    ↓
Recuperación semántica por cuenta
    ↓
Síntesis estratégica con Llama
```

## Configuración

```env
LLM_EMBEDDING_MODEL=nomic-embed-text
KNOWLEDGE_CONTEXT_CHUNKS=6
```

Instalar el modelo:

```bash
ollama pull nomic-embed-text
```

`KNOWLEDGE_CONTEXT_CHUNKS=0` desactiva la incorporación de knowledge en los reportes sin eliminar
la biblioteca local.

## Primer arranque

```bash
anton knowledge sync
anton knowledge status
anton knowledge search "Reels reach and engagement"
```

La primera revisión de las fuentes oficiales incluidas en Anton se activa automáticamente porque
el catálogo fue curado en código. Los cambios posteriores necesitan aprobación explícita.

## Aprobación de cambios

1. Ejecuta `anton knowledge sync`.
2. Revisa `anton knowledge status`.
3. Identifica una fuente con `PENDING=True`.
4. Ejecuta `anton knowledge diff SOURCE_ID` para comparar las revisiones.
5. Revisa también la fuente original antes de aprobarla.
6. Ejecuta `anton knowledge approve SOURCE_ID`.

Hasta la aprobación, Anton continúa utilizando la revisión anterior.

## Fuentes iniciales

| Fuente | Contexto |
|---|---|
| Instagram Best Practices education hub | `organic` |
| Meta Instagram Newsroom | `product_updates` |
| Meta Recommendation Guidelines | `policy` |
| Instagram Feed Ranking System Card | `organic` |
| Instagram Explore recommendations engineering article | `organic` |
| Instagram branded content guidance | `policy` |
| Instagram licensed music guidance | `policy` |
| Meta Reels creative guidance | `paid` |

## Recuperación durante un reporte

Anton crea una consulta usando:

- Tipos de publicación observados.
- Temas detectados visualmente.
- Intención del contenido.
- Biografía de la cuenta cuando está disponible.
- Conceptos generales de estrategia, engagement y alcance.

La consulta se convierte en un embedding local. Anton compara ese vector con los fragmentos
activos mediante similitud coseno y entrega los más relevantes a la síntesis. Limita a dos
fragmentos por fuente para evitar que un solo documento domine el contexto.

Si el modelo de embeddings no está disponible, utiliza una búsqueda léxica local como fallback.
El reporte no falla por este motivo.

## Reglas de uso

- Solo se recuperan revisiones activas y aprobadas.
- Las recomendaciones deben conectarse con evidencia de la cuenta.
- El knowledge puede sugerir una prueba, pero no garantizar un resultado.
- El contexto `paid` no debe convertirse en una regla para contenido `organic`.
- Las políticas pueden generar advertencias, no asesoramiento legal.
- No se guardan tokens de Instagram en la biblioteca.
- Los datos privados de una cuenta nunca se convierten automáticamente en knowledge global.

## Escala futura

SQLite es suficiente para la primera biblioteca curada. Si el índice alcanza cientos de miles de
fragmentos, las mismas entidades pueden migrarse a Qdrant sin cambiar el flujo de aprobación ni el
formato entregado a Llama.

## Notas relacionadas

- [[Anton - Command Reference]]
- [[README|MotifCue Anton]]
