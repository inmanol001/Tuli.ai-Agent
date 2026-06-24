---
name: macos_observation
description: Observar estado básico de macOS sin controlar la pantalla ni modificar nada.
tools:
  - macos_permissions_check
  - macos_observe_frontmost
  - macos_visible_windows
  - macos_list_apps
risk: low
---

# Objetivo

Usa `macos_observation` cuando el usuario quiera revisar información básica del estado actual de macOS sin ejecutar acciones de control.

Esta skill solo observa estado. No hace screenshots, no usa visión, no hace clicks, no escribe texto, no mueve ventanas y no cambia de escritorio.

# Cuándo usar esta skill

Usa esta skill cuando el usuario quiera:

1. Saber qué app está activa.
2. Saber cuál ventana está al frente.
3. Ver qué ventanas visibles hay.
4. Revisar permisos relevantes del agente.
5. Listar apps conocidas o disponibles.
6. Diagnosticar si el agente tiene permisos suficientes para observar o controlar macOS.

No uses esta skill para:

1. Abrir apps. Para eso usa `open_app`.
2. Buscar en internet o abrir webs. Para eso usa `browser_search`.
3. Cambiar de escritorio, Space o Mission Control. Para eso usa `macos_spaces`.
4. Leer visualmente la pantalla.
5. Hacer screenshots.
6. Hacer clicks.
7. Escribir o pegar texto.
8. Mover, cerrar, minimizar o redimensionar ventanas.
9. Ejecutar comandos.
10. Pedir permisos al sistema.

# Selección de tool

Usa `macos_permissions_check` cuando el usuario quiera revisar permisos, diagnosticar permisos o saber si el agente tiene acceso necesario.

Usa `macos_observe_frontmost` cuando el usuario quiera saber qué app está activa, qué ventana está al frente o cuál es la app actual.

Usa `macos_visible_windows` cuando el usuario quiera listar ventanas abiertas o visibles.

Usa `macos_list_apps` cuando el usuario quiera saber qué apps puede abrir, qué apps están disponibles o qué apps conoce el agente.

# Reglas importantes

1. No confundas observar app activa con hacer screenshot.
2. No prometas leer contenido visual de la pantalla.
3. No digas que viste la pantalla completa.
4. No cambies nada del sistema.
5. No uses esta skill para acciones de control.
6. Si el usuario pide observar visualmente la pantalla, y no hay herramienta de screenshot o visión activa, responde que esa observación visual no está disponible en esta fase.
7. La respuesta final debe basarse en el `ToolResult`.
8. Si la tool falla, explica brevemente el error.
9. Si la información no está disponible en el resultado, no la inventes.

# Etapa 1: detectar intención

Determina si el usuario está pidiendo observar estado de macOS o controlar macOS.

Si solo quiere información de estado, usa esta skill.

Si quiere abrir, buscar, cambiar, escribir, hacer clicks o ejecutar comandos, usa otra skill.

# Etapa 2: elegir tool

Elige la tool más específica según la pregunta.

* Permisos → `macos_permissions_check`
* App o ventana activa → `macos_observe_frontmost`
* Ventanas visibles → `macos_visible_windows`
* Apps disponibles o conocidas → `macos_list_apps`

# Etapa 3: llamar la tool

Llama la tool elegida sin argumentos.

# Etapa 4: responder después de ejecutar

Responde usando los datos reales devueltos por la tool.

Si la tool falla, explica brevemente el error.
