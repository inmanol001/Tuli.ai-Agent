---
name: web_search
description: Buscar información en internet y devolver resultados estructurados al agente para responder.
tools:
  - web_search
risk: low
---

# Skill: web_search

## Objetivo

Usa `web_search` cuando el usuario quiera investigar, buscar información en internet, encontrar documentación, revisar noticias, comparar fuentes o responder usando resultados web.

`web_search` devuelve resultados estructurados al agente: título, URL y snippet.

`web_search` no abre navegador.
`web_search` no abre Google.
`web_search` no abre YouTube.
`web_search` no reproduce videos.
`web_search` no hace clicks.
`web_search` no navega visualmente.

## Diferencia crítica

`web_search` = buscar información para responder en el chat.

`browser_search` = abrir navegador, abrir Google, abrir YouTube, abrir una URL o navegar visualmente.

Si el usuario quiere información, usa `web_search`.
Si el usuario quiere abrir algo, usa `browser_search`.

## Regla obligatoria

Si `web_search` está disponible y el usuario pide investigar, buscar información, noticias, documentación, fuentes, referencias, latest/current/recent info o comparación, llama la tool `web_search`.

No respondas diciendo que no puedes buscar.
No respondas diciendo que no tienes herramientas.
No preguntes si quiere que busques cuando ya pidió buscar.
No uses `browser_search` para responder con información.
No finjas que buscaste si no hubo tool_result.

## Formato de tool call

Tool:

web_search

Argumentos:

{
  "query": "tema real de búsqueda",
  "max_results": 5
}

Usa `max_results: 5` por defecto.

## Limpieza de query

La query debe contener el tema real.

Quita palabras de comando como:

- investiga
- busca
- buscar
- busca en internet
- busca en la web
- quiero que investigues
- quiero que busques
- información sobre
- noticias de
- documentación de
- find
- look up
- search the web for
- investigate

Conserva:

- nombres de modelos
- nombres de librerías
- nombres de frameworks
- errores exactos
- versiones
- plataformas
- empresas
- fechas
- países
- términos técnicos
- nombres propios

## Cuándo usar web_search

Usa `web_search` para:

- investiga X
- busca información sobre X
- busca en internet X
- busca noticias de X
- busca documentación de X
- encuentra fuentes sobre X
- compara X con Y
- qué hay de nuevo sobre X
- información actual sobre X
- latest X
- current X
- recent X
- best practices for X
- official docs for X
- tutorial de X
- guía de X

## Cuándo NO usar web_search

No uses `web_search` para:

- abre YouTube
- abre Google
- abre google.com
- abre una URL
- abre este link
- abre GitHub
- pon música
- pon un video
- busca en YouTube un video
- reproduce algo
- navega a una página
- visita una web

En esos casos usa `browser_search`.

## Documentación técnica

Si el usuario pide documentación, usa `web_search`.

Buenas queries:

- ollama tool calling documentation
- ollama tool calling official documentation
- ddgs python documentation
- pyautogui macOS accessibility documentation
- OpenAI API function calling documentation

## Noticias

Si el usuario pide noticias, usa `web_search`.

Buenas queries:

- noticias de inteligencia artificial
- AI news latest
- OpenAI news latest
- Ollama latest news

No inventes fechas.
No inventes eventos.
No inventes fuentes.

## Comparaciones

Si el usuario pide comparar, usa `web_search`.

Buenas queries:

- qwen3 vs llama3 tool calling
- ollama vs lm studio local agents
- ddgs vs duckduckgo-search python

## Errores técnicos

Si el usuario pega un error y pide investigar, usa `web_search`.

Conserva la parte más distintiva del error.

Buenas queries:

- no_native_tool_call llama3-groq-tool-use
- Ollama tool_calls None python
- pyautogui macos accessibility permission error

## Después del tool_result

Después de recibir resultados:

1. Lee títulos.
2. Lee URLs.
3. Lee snippets.
4. Resume hallazgos.
5. No inventes fuentes.
6. No inventes URLs.
7. No digas que abriste navegador.
8. No digas que leíste páginas completas si solo tienes snippets.
9. Si los resultados son débiles, dilo.
10. Si no hay resultados, dilo.
11. Si hay error, dilo.

## Ejemplos positivos

### Ejemplo positivo 1

Usuario: investiga ollama tool calling best practices

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "ollama tool calling best practices",
    "max_results": 5
  }
}

### Ejemplo positivo 2

Usuario: busca documentación de ollama tool calling

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "ollama tool calling documentation",
    "max_results": 5
  }
}

### Ejemplo positivo 3

Usuario: busca documentación oficial de ollama tool calling

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "ollama tool calling official documentation",
    "max_results": 5
  }
}

### Ejemplo positivo 4

Usuario: busca en internet noticias de inteligencia artificial

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "noticias de inteligencia artificial",
    "max_results": 5
  }
}

### Ejemplo positivo 5

Usuario: compara qwen3 y llama3 para tool calling local

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "qwen3 vs llama3 local tool calling comparison",
    "max_results": 5
  }
}

### Ejemplo positivo 6

Usuario: qué hay de nuevo sobre llama 3.1 function calling

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "llama 3.1 function calling latest",
    "max_results": 5
  }
}

### Ejemplo positivo 7

Usuario: busca buenas prácticas de function calling en ollama

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "ollama function calling best practices",
    "max_results": 5
  }
}

### Ejemplo positivo 8

Usuario: investiga modelos pequeños para tool calling

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "small language models tool calling best practices",
    "max_results": 5
  }
}

### Ejemplo positivo 9

Usuario: busca fuentes sobre agentes locales con ollama

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "local agents with ollama sources",
    "max_results": 5
  }
}

### Ejemplo positivo 10

Usuario: busca documentación de pyautogui macOS accessibility

Tool correcta:

{
  "tool_name": "web_search",
  "arguments": {
    "query": "pyautogui macOS accessibility permissions documentation",
    "max_results": 5
  }
}

## Ejemplos negativos

### Ejemplo negativo 1

Usuario: abre YouTube

No uses `web_search`.

Usa `browser_search`.

Razón: el usuario quiere abrir un sitio.

### Ejemplo negativo 2

Usuario: abre Google

No uses `web_search`.

Usa `browser_search`.

Razón: el usuario quiere abrir un sitio.

### Ejemplo negativo 3

Usuario: abre google.com

No uses `web_search`.

Usa `browser_search`.

Razón: el usuario dio un dominio directo.

### Ejemplo negativo 4

Usuario: abre https://ollama.com

No uses `web_search`.

Usa `browser_search`.

Razón: el usuario dio una URL directa.

### Ejemplo negativo 5

Usuario: busca en YouTube un video de ollama

No uses `web_search`.

Usa `browser_search`.

Razón: el usuario quiere YouTube visible.

### Ejemplo negativo 6

Usuario: ponme música en YouTube

No uses `web_search`.

Usa `browser_search`.

Razón: el usuario quiere media o reproducción.

### Ejemplo negativo 7

Usuario: abre Google y busca ollama tool calling

No uses `web_search`.

Usa `browser_search`.

Razón: el usuario pidió abrir Google.

## Casos frontera

### Caso frontera 1

Usuario: busca ollama tool calling

Tool preferida: `web_search`.

Razón: no pidió abrir navegador.

### Caso frontera 2

Usuario: busca en Google ollama tool calling

Tool preferida: `web_search`.

Razón: aunque menciona Google, el objetivo parece información.

### Caso frontera 3

Usuario: abre Google y busca ollama tool calling

Tool preferida: `browser_search`.

Razón: pidió abrir Google.

### Caso frontera 4

Usuario: quiero leer documentación de ollama tool calling

Tool preferida: `web_search`.

Razón: quiere documentación.

### Caso frontera 5

Usuario: abre la documentación de ollama

Tool preferida: `browser_search`.

Razón: pidió abrir.

### Caso frontera 6

Usuario: necesito saber si qwen3 soporta tools

Tool preferida: `web_search`.

Razón: pregunta técnica que puede requerir información actual.

### Caso frontera 7

Usuario: ponme un video sobre qwen3 tools

Tool preferida: `browser_search`.

Razón: quiere video.

### Caso frontera 8

Usuario: investiga videos populares sobre qwen3 tools

Tool preferida: `web_search`.

Razón: quiere investigar, no reproducir.

## Frases prohibidas

No digas:

- No puedo buscar.
- No tengo internet.
- No puedo usar herramientas.
- No tengo capacidad para llamar herramientas.
- ¿Quieres que lo busque?
- Puedo ayudarte a buscar si quieres.

Si el usuario pidió buscar y `web_search` está disponible, llama la herramienta.

## Criterios de éxito

La skill fue usada bien si:

- Se llamó `web_search`.
- La query está limpia.
- `max_results` está definido.
- La respuesta usa resultados reales.
- No se abrió navegador.
- No se inventaron fuentes.
- No se pidió permiso innecesario.

## Criterios de fallo

La skill falló si:

- El agente respondió sin llamar tool.
- El agente dijo que no podía buscar.
- El agente usó `browser_search` para investigación.
- El agente inventó resultados.
- El agente dijo que abrió navegador.
- El agente pidió permiso sin necesidad.

## Regla final

Objetivo de información = `web_search`.

Objetivo de navegación visible = `browser_search`.

Fin de la skill.
