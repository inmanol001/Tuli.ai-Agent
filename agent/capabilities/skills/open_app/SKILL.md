---
name: open_app
description: Abrir aplicaciones instaladas de macOS por nombre usando una acción segura del sistema.
tools:
  - open_app
risk: low
---

# Objetivo

Usa `open_app` cuando el usuario quiera abrir o lanzar una aplicación instalada en macOS.

Esta skill solo abre aplicaciones. No controla ventanas, no escribe texto, no hace clicks, no abre páginas web, no ejecuta comandos y no modifica archivos.

# Cuándo usar esta skill

Usa `open_app` cuando la intención principal del usuario sea una de estas:

1. Abrir una aplicación instalada.
2. Lanzar una app por nombre.
3. Traer una aplicación al frente si el usuario pide abrirla.
4. Abrir una app del sistema o una app conocida instalada.

No uses esta skill para:

1. Abrir páginas web, sitios web o URLs. Para eso usa `browser_search`.
2. Buscar información en internet. Para eso usa `browser_search`.
3. Leer archivos locales.
4. Ejecutar comandos de terminal.
5. Escribir, pegar o hacer clicks.
6. Cambiar de escritorio, Space o Mission Control. Para eso usa `macos_spaces`.
7. Observar ventanas, app activa o permisos. Para eso usa `macos_observation`.
8. Instalar aplicaciones.
9. Borrar, mover o modificar archivos.

# Cómo construir los argumentos

La tool recibe:

```json
{
  "app_name": "nombre de la aplicación"
}
```

`app_name` debe contener solo el nombre de la aplicación que el usuario quiere abrir.

Antes de llenar `app_name`, elimina palabras de comando que no formen parte del nombre real de la app, por ejemplo:

* abre
* abrir
* lanza
* iniciar
* inicia
* ejecuta
* pon
* abre la app de
* abre la aplicación
* quiero abrir
* puedes abrir

Conserva el nombre real de la aplicación.

# Reglas importantes

1. No inventes una app si el usuario no dijo cuál quiere abrir.
2. Si falta el nombre de la app, pide una aclaración breve.
3. No uses `open_app` para URLs, dominios o sitios web.
4. No uses `open_app` para rutas locales.
5. No uses `open_app` para comandos de terminal.
6. No digas que la app se abrió si no existe un `ToolResult`.
7. La respuesta final debe basarse en el resultado real de la tool.
8. Si la tool solo envió la orden pero no confirmó que la app quedó activa, responde de forma honesta.
9. Si la tool falla, explica brevemente el error.

# Etapa 1: detectar intención

Primero decide si la intención pertenece a abrir una aplicación local de macOS.

Pertenece a `open_app` si el usuario quiere abrir una app instalada.

No pertenece a `open_app` si el usuario quiere buscar en internet, abrir una URL, controlar ventanas, escribir texto, hacer clicks, cambiar Spaces o ejecutar comandos.

# Etapa 2: extraer `app_name`

Extrae el nombre de la app solicitada.

No incluyas palabras de comando en `app_name`.

# Etapa 3: llamar la tool

Cuando la app esté clara, llama `open_app` con `app_name`.

# Etapa 4: responder después de ejecutar

La respuesta final debe usar el resultado real de la tool.

Si la app se abrió correctamente, responde natural y breve.

Si la tool falló, explica que no se pudo abrir y muestra el error disponible.

Si no se pudo verificar que la app quedó activa, no digas que lo verificaste.
