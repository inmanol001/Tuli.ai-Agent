---
name: browser_search
description: Buscar información o abrir contenido web usando el navegador por defecto.
tools:
  - browser_search
risk: low
---

# Objetivo

Usa `browser_search` cuando el usuario quiera buscar información, abrir una página web o navegar a contenido usando el navegador por defecto.

Esta skill no controla aplicaciones de macOS, no hace screenshots, no hace clicks, no escribe texto, no lee páginas y no ejecuta comandos.

# Cuándo usar esta skill

Usa `browser_search` cuando la intención principal del usuario sea una de estas:

1. Buscar información en internet.
2. Investigar un tema.
3. Abrir una página web.
4. Abrir una URL absoluta `http` o `https`.
5. Navegar a un sitio web conocido.
6. Buscar contenido en un destino web específico si el usuario lo indica claramente.

No uses esta skill para:

1. Abrir aplicaciones de macOS. Para eso usa `open_app`.
2. Observar la app activa o ventanas. Para eso usa las tools de observación de macOS.
3. Cambiar de escritorio o Mission Control. Para eso usa las tools de macOS Spaces.
4. Leer una página web después de abrirla.
5. Hacer screenshots.
6. Hacer clicks.
7. Escribir o pegar texto.
8. Ejecutar comandos.
9. Abrir rutas locales, archivos locales o esquemas inseguros.

# Cómo construir los argumentos

La tool recibe:

```json
{
  "query": "texto o URL solicitada por el usuario",
  "target": "auto"
}
```

`query` debe contener el tema real de búsqueda, el nombre del sitio o la URL indicada por el usuario.

Antes de llenar `query`, elimina palabras de comando que no formen parte del tema real, por ejemplo:

* busca
* buscar
* investiga
* abre
* abrir
* muéstrame
* pon
* en internet
* en la web

Conserva las palabras que sí formen parte del tema solicitado.

# Uso de `target`

Usa `target="auto"` cuando el destino no esté completamente claro o cuando una resolución automática sea suficiente.

Usa `target="web"` cuando el usuario pida una búsqueda general de información en internet.

Usa `target="google"` cuando el usuario pida explícitamente buscar usando Google.

Usa `target="youtube"` cuando el usuario pida explícitamente buscar contenido en YouTube o cuando el contenido solicitado sea claramente de video/música y el usuario indique ese destino.

Usa `target="url"` solo si el usuario proporciona una URL absoluta que empieza con `http://` o `https://`.

Usa `target="google_home"` solo si el usuario pide abrir la página principal de Google, no una búsqueda.

Usa `target="youtube_home"` solo si el usuario pide abrir la página principal de YouTube, no una búsqueda.

# Reglas importantes

1. No inventes URLs.
2. No conviertas una búsqueda general en una búsqueda de YouTube si el usuario no lo pidió.
3. No conviertas una búsqueda general en abrir una página principal.
4. No uses `target="url"` si el usuario no proporcionó una URL absoluta `http` o `https`.
5. No abras rutas locales.
6. No abras esquemas como `file://`, `javascript:`, `data:` o `ftp:`.
7. Si el usuario solo quiere conversar o preguntar algo que puedes responder sin navegador, no uses esta skill.
8. Si el usuario pide una acción del sistema operativo, no uses esta skill.
9. Si falta el tema de búsqueda, pide una aclaración breve.
10. Si hay una tool más específica para la intención del usuario, usa la tool específica.

# Etapa 1: detectar intención

Primero decide si la intención pertenece al navegador.

La intención pertenece al navegador si el usuario quiere buscar, investigar, abrir una web, abrir una URL o navegar a contenido web.

La intención no pertenece al navegador si el usuario quiere abrir una app, controlar macOS, cambiar ventanas, cambiar escritorios, leer archivos, ejecutar comandos o hacer automatización de escritorio.

# Etapa 2: extraer el tema real

Extrae de la petición el contenido importante.

Elimina solamente las palabras de instrucción. No elimines nombres, temas, títulos, marcas, artistas, productos, tecnologías o frases que forman parte de la búsqueda.

# Etapa 3: elegir target

Elige el target más seguro:

* `auto` si no hace falta especificar.
* `web` para búsqueda general.
* `google` si el usuario lo pidió explícitamente.
* `youtube` si el usuario pidió explícitamente YouTube o contenido claramente destinado a YouTube.
* `url` si hay URL absoluta.
* `google_home` o `youtube_home` si pidió abrir la página principal.

# Etapa 4: llamar la tool

Cuando la intención sea clara, llama `browser_search` con `query` y `target`.

No respondas como si hubieras abierto o buscado algo sin haber llamado la tool.

# Etapa 5: respuesta después de ejecutar

La respuesta final debe basarse en el resultado real de la tool.

Si la tool abrió una búsqueda, responde de forma natural indicando que abriste la búsqueda en el navegador.

Si la tool abrió una página, responde indicando que abriste la página.

Si la tool falló, explica brevemente que no se pudo abrir y muestra el error si está disponible.
