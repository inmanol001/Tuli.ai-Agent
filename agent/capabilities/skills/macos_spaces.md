---
name: macos_spaces
description: Navegar de forma segura entre macOS Spaces, escritorios y Mission Control usando acciones fijas.
tools:
  - macos_space_status
  - macos_space_next
  - macos_space_previous
  - macos_space_mission_control
  - macos_space_switch_desktop_number
risk: low
---

# Objetivo

Usa `macos_spaces` cuando el usuario quiera navegar entre escritorios o Spaces de macOS, revisar el estado básico de Spaces o abrir Mission Control.

Esta skill solo usa acciones fijas y seguras. No ejecuta AppleScript generado por el modelo, no hace screenshots, no hace clicks, no escribe texto y no mueve ventanas.

# Cuándo usar esta skill

Usa esta skill cuando el usuario quiera:

1. Cambiar al siguiente escritorio o Space.
2. Volver al escritorio o Space anterior.
3. Cambiar a un escritorio o Space por número.
4. Abrir Mission Control.
5. Revisar el estado básico de Spaces o del escritorio actual.

No uses esta skill para:

1. Abrir apps. Para eso usa `open_app`.
2. Buscar información o abrir web. Para eso usa `browser_search`.
3. Observar app activa, ventanas o permisos. Para eso usa `macos_observation`.
4. Hacer screenshots.
5. Hacer clicks.
6. Mover ventanas entre escritorios.
7. Hacer window tiling.
8. Crear, borrar o renombrar escritorios.
9. Ejecutar AppleScript dinámico generado por el modelo.
10. Ejecutar comandos de terminal.

# Selección de tool

Usa `macos_space_status` cuando el usuario pregunte por el estado actual de Spaces o del escritorio.

Usa `macos_space_next` cuando el usuario quiera ir al siguiente escritorio o Space.

Usa `macos_space_previous` cuando el usuario quiera volver al escritorio o Space anterior.

Usa `macos_space_mission_control` cuando el usuario quiera abrir Mission Control.

Usa `macos_space_switch_desktop_number` cuando el usuario indique un número de escritorio o Space.

# Cómo construir los argumentos

Solo `macos_space_switch_desktop_number` requiere argumento:

```json
{
  "number": 1
}
```

`number` debe ser un entero entre 1 y 9.

Si el usuario indica un número fuera de rango, no llames la tool. Pide una aclaración breve o explica el límite.

# Reglas importantes

1. No inventes números de escritorio.
2. No uses esta skill si el usuario no pidió cambiar o revisar Spaces.
3. No digas que verificaste el cambio si la tool solo envió un atajo.
4. Si la tool solo envía un atajo, la respuesta final debe usar lenguaje honesto como “Envié el atajo...”.
5. No ejecutes scripts dinámicos.
6. No uses screenshots.
7. No hagas clicks.
8. No muevas ventanas.
9. No hagas window tiling.
10. La respuesta final debe basarse en el `ToolResult`.
11. Si la tool falla, explica brevemente el error.

# Etapa 1: detectar intención

Determina si la intención pertenece a navegación de Spaces, escritorios o Mission Control.

# Etapa 2: elegir tool

Elige la tool más específica.

* Estado de Spaces → `macos_space_status`
* Siguiente escritorio → `macos_space_next`
* Escritorio anterior → `macos_space_previous`
* Mission Control → `macos_space_mission_control`
* Escritorio por número → `macos_space_switch_desktop_number`

# Etapa 3: validar argumentos

Si se requiere número, valida que exista y que sea entre 1 y 9.

# Etapa 4: llamar la tool

Llama solo la tool necesaria.

# Etapa 5: responder después de ejecutar

Responde usando el resultado real de la tool.

Si no hay verificación final del escritorio activo, usa lenguaje honesto como “Envié el atajo...”.

Si la tool falla, explica brevemente el error.
