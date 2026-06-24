# Plan Para Construir El Agente Local

## Resumen Y Viabilidad

Sí, la propuesta es viable y puede funcionar, especialmente porque el entorno ya tiene Python 3.11, Ollama y los modelos clave instalados: `allenporter/xlam:1b`, `qwen3:4b`, `qwen2.5-coder:7b` y `qwen3-embedding:0.6b`.

El ajuste importante: no construir el “agente perfecto” completo desde el inicio. El primer objetivo debe ser un MVP local estable:

`CLI -> Gateway -> Session Manager -> Router validado -> Context Builder simple -> Qwen -> Logs`

RAG, memoria larga, desktop automation, reflection avanzada y plugins complejos deben ir después, por etapas.

Hallazgo clave de validación: `xLAM` devuelve JSON válido si se usa schema, pero puede fallar semánticamente en campos como `route` o `needs_tool`. Por eso el router debe tener validación semántica, reglas deterministas para rutas críticas y fallback a `qwen3:4b`.

## Retos Principales

- Router confiable: `xLAM` no debe ser la única fuente de verdad; validar enums, herramientas permitidas, riesgo y rutas.
- Tool calling: para MVP, usar tool calls sin streaming y con un ciclo obligatorio `tool_call -> tool_result -> final_answer`.
- Seguridad: bloquear acciones destructivas, pedir confirmación para escritura, terminal, instalaciones y automatización.
- Contexto: evitar meter todas las skills, tools, memoria y RAG en cada prompt.
- Rendimiento: `qwen3:4b` funciona mejor como modelo principal/fallback, pero puede ser lento como router.
- Alcance: YouTube/browser tools reales pueden complicar el MVP; empezar con herramientas simuladas o simples antes de automatizar navegador/escritorio.

## Interfaces Y Contratos

- `gateway.handle_message(user_text: str, session_id: str | None, debug: bool = False) -> AgentResponse`
- `AgentResponse`: `session_id`, `status`, `text`, `route`, `tool_calls`, `debug`.
- `RouterDecision`: `intent`, `domain`, `action`, `route`, `needs_tool`, `needs_clarification`, `missing_info`, `needs_memory`, `needs_rag`, `risk_level`, `suggested_tools`, `suggested_skills`.
- `ContextPackage`: `system_prompt`, `user_message`, `router_decision`, `recent_history`, `selected_tools`, `selected_skills`, `memory_snippets`, `safety_rules`.
- `ToolCall`: `tool_name`, `arguments`, `risk_level`, `requires_confirmation`.
- `ToolResult`: `tool_name`, `success`, `data`, `error`, `metadata`.

## Implementación Por Etapas

1. Crear proyecto base en `/Users/inma/Documents/AI Agent` con `.venv` local usando `/opt/homebrew/bin/python3.11`.
   - Instalar solo: `ollama`, `pydantic`, `pyyaml`, `python-dotenv`, `rich`, `typer`, `pytest`.
   - Crear estructura mínima: `agent/`, `config/`, `gateway/`, `router/`, `context_builder/`, `models/`, `logs/`, `tests/`.

2. MVP sin tools reales.
   - Implementar CLI con Typer.
   - Implementar `SessionManager` en memoria.
   - Implementar logger JSONL.
   - Implementar cliente Ollama centralizado.
   - Implementar router con JSON schema, Pydantic, retry y fallback.
   - Implementar reglas deterministas posteriores al router para corregir rutas obvias:
     - “hola” -> `chat`
     - “busca música en YouTube” -> `clarification`
     - “borra/elimina” -> `safety_confirmation`
   - Implementar Context Builder simple sin SQLite, sin RAG y sin plugins dinámicos.
   - Conectar `qwen3:4b` como modelo principal.

3. Añadir Response Controller.
   - Manejar `chat`, `clarification`, `action_ready`, `safety_confirmation`, `refuse`.
   - Guardar estado pendiente de aclaración.
   - No ejecutar acciones todavía si falta información.
   - Responder limpio al usuario y mostrar debug solo con flag.

4. Añadir Capabilities mínimo.
   - Crear registry estático con herramientas declaradas, no necesariamente ejecutadas al inicio.
   - Skill inicial `youtube_search` como markdown.
   - Tool inicial simulada `youtube_search` que devuelva resultados mock para validar el loop.
   - Implementar Tool Validator con schema, existencia, argumentos y riesgo.

5. Añadir tool loop real básico.
   - Main Model produce `tool_call` estructurado.
   - Validator autoriza.
   - Executor ejecuta.
   - Tool result vuelve al Main Model.
   - Main Model produce `final_answer`.
   - Registrar todo en `logs/tool_calls.jsonl`.

6. Añadir SQLite después del MVP estable.
   - Crear `memory.db` y tablas iniciales: `session_state`, `preferences`, `tool_memory`, `error_memory`, `conversation_summaries`.
   - Persistir estado pendiente, historial corto y preferencias explícitas.
   - No guardar memoria automáticamente sin reglas claras.

7. Añadir Knowledge Base y RAG.
   - Crear `knowledge/` con markdown/jsonl.
   - Instalar LlamaIndex y Chroma solo en esta etapa.
   - Indexar documentos locales.
   - Usar RAG solo cuando `router_decision.needs_rag = true`.

8. Añadir Reflection y Self-Correction.
   - Empezar con verificación simple: tool success, error, retry count.
   - Máximo 2 reintentos.
   - Si falla dos veces, detener y explicar claramente.

9. Añadir UI/streaming.
   - Streaming solo para chat normal.
   - Tool calls sin streaming hasta que el loop sea confiable.
   - Modo dev muestra router JSON, contexto seleccionado, tools y logs.

## Pruebas Y Validación

- Router:
  - `"hola"` -> `route=chat`, `needs_tool=false`.
  - `"busca música en YouTube"` -> `route=clarification`, `needs_tool=true`, `missing_info` incluye artista/género/tema.
  - `"busca música nueva de Bad Bunny en YouTube"` -> `action_ready` o `planner`, tool `youtube_search`.
  - `"qué hicimos con el problema del JSON"` -> `memory_lookup` o `rag_lookup`.
  - `"borra esos archivos"` -> `safety_confirmation`.

- Context Builder:
  - Incluye solo tools sugeridas.
  - No incluye RAG si `needs_rag=false`.
  - No incluye memoria si `needs_memory=false`.
  - Incluye reglas de seguridad si riesgo no es `low`.

- Modelo principal:
  - Responde chat simple sin tool call.
  - Pregunta aclaración cuando falta información.
  - No inventa resultados de tools.

- Executor:
  - Ejecuta tool válida.
  - Bloquea tool inexistente.
  - Pide confirmación para riesgo medio/alto.
  - Devuelve `ToolResult` siempre, incluso en error.

- Tool loop:
  - Nunca produce respuesta final inventada antes del `tool_result`.
  - Registra `tool_call` y `tool_result`.
  - Pasa el resultado al modelo y luego genera `final_answer`.

- Memoria:
  - Guarda y recupera `session_state`.
  - No duplica preferencias.
  - No guarda ruido conversacional.

- RAG:
  - Ingesta markdown de prueba.
  - Recupera fragmentos correctos.
  - No usa RAG para preguntas generales.

## Supuestos Y Defaults

- El proyecto se creará dentro de `/Users/inma/Documents/AI Agent`.
- Se usará `.venv` local del proyecto, no `~/.venv`, aunque `~/.venv` ya tenga paquetes.
- `xLAM` será router principal solo si pasa pruebas semánticas; si falla, se corrige con reglas deterministas o fallback a `qwen3:4b`.
- No se implementará RAG, desktop automation ni browser automation en la primera entrega.
- La primera tool de YouTube puede ser simulada para validar arquitectura antes de abrir navegador real.
- Las acciones de escritura, terminal, instalación, borrado o envío externo requerirán confirmación.
