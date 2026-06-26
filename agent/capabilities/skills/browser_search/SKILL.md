---
name: browser_search
description: "Abrir contenido web visible en el navegador por defecto: páginas, URLs, Google, YouTube o búsquedas navegables."
tools:
  - browser_search
risk: low
---

# Skill: browser_search

## Objetivo

Usa browser_search cuando el usuario quiera abrir, navegar o buscar algo visible en el navegador.
browser_search abre páginas web.
browser_search abre búsquedas visibles.
browser_search abre Google.
browser_search abre YouTube.
browser_search abre URLs.
browser_search abre sitios conocidos.
browser_search no es para investigar y responder dentro del chat.
browser_search no sustituye web_search.

## Diferencia crítica

browser_search abre.
web_search investiga.
browser_search navega.
web_search informa.
browser_search muestra algo en navegador.
web_search devuelve resultados al agente.

Usa browser_search si el usuario quiere ver algo abierto.
Usa browser_search si el usuario dice abrir.
Usa browser_search si el usuario dice navegar.
Usa browser_search si el usuario dice visitar.
Usa browser_search si el usuario quiere YouTube visible.
Usa browser_search si el usuario quiere Google visible.
Usa browser_search si el usuario da una URL para abrir.
Usa web_search si el usuario quiere información para responder dentro del chat.
Usa web_search si el usuario quiere noticias resumidas.
Usa web_search si el usuario quiere documentación resumida.
Usa web_search si el usuario quiere comparar fuentes.

## Tool disponible

Tool: browser_search

Argumentos:

{
  "query": "destino o búsqueda visible",
  "target": "auto"
}

Targets permitidos:
- auto
- web
- google
- youtube
- url
- google_home
- youtube_home

## Reglas obligatorias

Si el usuario pide abrir una página, llama browser_search.
Si el usuario pide abrir YouTube, llama browser_search.
Si el usuario pide abrir Google, llama browser_search.
Si el usuario pide abrir una URL, llama browser_search.
Si el usuario pide buscar en YouTube, llama browser_search.
Si el usuario pide buscar en Google visible, llama browser_search.
No respondas sin tool call.
No digas que abriste algo sin tool_result.
No uses web_search para abrir navegador.

## Target youtube_home

Usa youtube_home cuando el usuario pida abrir YouTube sin tema de búsqueda.
Ejemplos: abre YouTube, abre youtube, abre la página de YouTube, pon YouTube.
Tool call esperado: browser_search query=youtube target=youtube_home.

## Target google_home

Usa google_home cuando el usuario pida abrir Google sin tema de búsqueda.
Ejemplos: abre Google, abre google, abre la página de Google, pon Google.
Tool call esperado: browser_search query=google target=google_home.

## Target url

Usa url solo si el usuario proporciona una URL absoluta.
Una URL absoluta empieza con http:// o https://.
Ejemplo: abre https://youtube.com -> query=https://youtube.com target=url.
No uses url para dominios sin protocolo.
youtube.com no es URL absoluta.
google.com no es URL absoluta.
Para dominios sin protocolo usa auto.

## Target youtube

Usa youtube cuando el usuario quiera buscar algo en YouTube.
Usa youtube cuando el usuario quiera video.
Usa youtube cuando el usuario quiera música en YouTube.
Usa youtube cuando el usuario quiera reproducir o encontrar contenido audiovisual.
Ejemplo: busca en YouTube un video de Ollama -> query=video de Ollama target=youtube.

## Target google

Usa google cuando el usuario pida buscar en Google visible.
Ejemplo: busca en Google Ollama tool calling -> query=Ollama tool calling target=google.
Ejemplo: abre Google y busca Ollama -> query=Ollama target=google.

## Target web

Usa web cuando el usuario pida abrir una búsqueda web visible sin decir Google.
Ejemplo: abre una búsqueda de Ollama tool calling -> query=Ollama tool calling target=web.

## Target auto

Usa auto para sitios conocidos o dominios sin protocolo.
Ejemplos: abre github, abre google.com, abre youtube.com, abre ollama.com.

## Limpieza de query

Quita palabras de comando como abre, abrir, navega a, visita, entra a, pon, ponme.
Quita frases como abre la página de, abre la web de, abre el sitio de.
Quita busca en YouTube, busca en Google, abre Google y busca, abre YouTube y busca.
Conserva nombre del sitio, dominio, URL completa, tema del video, tema de búsqueda.

## Casos que pertenecen a web_search

No uses browser_search cuando el usuario quiera que Tuli investigue y responda.
Usa web_search para investiga Ollama tool calling.
Usa web_search para busca documentación de Ollama tool calling.
Usa web_search para busca noticias de inteligencia artificial.
Usa web_search para compara Qwen y Llama.
Usa web_search para busca fuentes sobre agentes locales.
Usa web_search para latest news about AI.
Usa web_search para official documentation.
Usa web_search para best practices.

## Seguridad

No abras rutas locales.
No abras file://.
No abras javascript:.
No abras data:.
No abras ftp:.
No inventes URLs.
No conviertas investigación en navegación.
No conviertas abrir YouTube en investigación.
No conviertas abrir Google en investigación.
No digas que leíste una página.
No digas que verificaste visualmente.

## Respuesta final

Si abrió YouTube, responde que abriste YouTube.
Si abrió Google, responde que abriste Google.
Si abrió una URL, responde que abriste la página.
Si abrió una búsqueda en YouTube, responde que buscaste el tema en YouTube.
Si abrió una búsqueda en Google, responde que buscaste el tema en Google.
Si abrió una búsqueda web, responde que abriste la búsqueda en el navegador.
Si falló, explica brevemente el error real.
No inventes resultados.
No inventes lectura de página.

## Ejemplos positivos

### Ejemplo positivo 1
Usuario: abre youtube
Tool correcta:
browser_search query=youtube target=youtube_home
Razón: abrir YouTube home.

### Ejemplo positivo 2
Usuario: abre YouTube
Tool correcta:
browser_search query=youtube target=youtube_home
Razón: abrir YouTube home.

### Ejemplo positivo 3
Usuario: abre google
Tool correcta:
browser_search query=google target=google_home
Razón: abrir Google home.

### Ejemplo positivo 4
Usuario: abre Google
Tool correcta:
browser_search query=google target=google_home
Razón: abrir Google home.

### Ejemplo positivo 5
Usuario: abre google.com
Tool correcta:
browser_search query=google.com target=auto
Razón: dominio sin protocolo.

### Ejemplo positivo 6
Usuario: abre youtube.com
Tool correcta:
browser_search query=youtube.com target=auto
Razón: dominio sin protocolo.

### Ejemplo positivo 7
Usuario: abre https://youtube.com
Tool correcta:
browser_search query=https://youtube.com target=url
Razón: URL absoluta.

### Ejemplo positivo 8
Usuario: abre https://ollama.com/blog/tool-support
Tool correcta:
browser_search query=https://ollama.com/blog/tool-support target=url
Razón: URL absoluta.

### Ejemplo positivo 9
Usuario: busca en YouTube un video de ollama tool calling
Tool correcta:
browser_search query=video de ollama tool calling target=youtube
Razón: YouTube search.

### Ejemplo positivo 10
Usuario: abre YouTube y busca qwen3 tools
Tool correcta:
browser_search query=qwen3 tools target=youtube
Razón: YouTube search.

### Ejemplo positivo 11
Usuario: busca en Google ollama tool calling
Tool correcta:
browser_search query=ollama tool calling target=google
Razón: Google search.

### Ejemplo positivo 12
Usuario: abre Google y busca ollama tool calling
Tool correcta:
browser_search query=ollama tool calling target=google
Razón: Google search.

### Ejemplo positivo 13
Usuario: abre github
Tool correcta:
browser_search query=github target=auto
Razón: sitio conocido.

### Ejemplo positivo 14
Usuario: abre la página de Ollama
Tool correcta:
browser_search query=Ollama target=auto
Razón: sitio visible.

### Ejemplo positivo 15
Usuario: ponme música de Bad Bunny en YouTube
Tool correcta:
browser_search query=música de Bad Bunny target=youtube
Razón: música/video.

### Ejemplo positivo 16
Usuario: abre una búsqueda web de inteligencia artificial
Tool correcta:
browser_search query=inteligencia artificial target=web
Razón: búsqueda visible.

## Ejemplos negativos

### Ejemplo negativo 1
Usuario: investiga ollama tool calling best practices
No uses browser_search.
Usa web_search.
Razón: quiere investigación para responder.

### Ejemplo negativo 2
Usuario: busca documentación de ollama tool calling
No uses browser_search.
Usa web_search.
Razón: quiere documentación para responder.

### Ejemplo negativo 3
Usuario: busca en internet noticias de inteligencia artificial
No uses browser_search.
Usa web_search.
Razón: quiere noticias para resumir.

### Ejemplo negativo 4
Usuario: compara qwen3 y llama3 para tool calling local
No uses browser_search.
Usa web_search.
Razón: quiere comparación.

### Ejemplo negativo 5
Usuario: busca fuentes sobre agentes locales con ollama
No uses browser_search.
Usa web_search.
Razón: quiere fuentes.

### Ejemplo negativo 6
Usuario: latest AI news
No uses browser_search.
Usa web_search.
Razón: quiere actualidad para responder.

## Casos frontera

### Caso frontera 1
Usuario: busca ollama tool calling
Tool preferida: web_search
Razón: no pidió abrir navegador.

### Caso frontera 2
Usuario: busca en internet ollama tool calling
Tool preferida: web_search
Razón: quiere información.

### Caso frontera 3
Usuario: busca en Google ollama tool calling
Tool preferida: browser_search
Razón: pidió Google visible.

### Caso frontera 4
Usuario: abre Google y busca ollama tool calling
Tool preferida: browser_search
Razón: pidió abrir Google.

### Caso frontera 5
Usuario: busca documentación de Ollama
Tool preferida: web_search
Razón: documentación para responder.

### Caso frontera 6
Usuario: abre documentación de Ollama
Tool preferida: browser_search
Razón: pidió abrir.

### Caso frontera 7
Usuario: quiero ver un video de Ollama
Tool preferida: browser_search
Razón: video visible.

### Caso frontera 8
Usuario: investiga videos populares de Ollama
Tool preferida: web_search
Razón: investigar, no reproducir.

### Caso frontera 9
Usuario: abre página oficial de Ollama
Tool preferida: browser_search
Razón: abrir página visible.

### Caso frontera 10
Usuario: busca página oficial de Ollama
Tool preferida: web_search
Razón: encontrar información.

## Checklist final

¿El usuario dijo abrir? Sí: browser_search.
¿El usuario dio URL absoluta? Sí: browser_search target url.
¿El usuario pidió YouTube sin tema? Sí: browser_search target youtube_home.
¿El usuario pidió Google sin tema? Sí: browser_search target google_home.
¿El usuario pidió buscar en YouTube? Sí: browser_search target youtube.
¿El usuario pidió buscar en Google? Sí: browser_search target google.
¿El usuario pidió investigar? Sí: web_search.
¿El usuario pidió noticias? Sí: web_search.
¿El usuario pidió documentación para responder? Sí: web_search.

## Criterios de éxito

Se llamó browser_search.
El target coincide con la intención.
La query está limpia.
YouTube home usa youtube_home.
Google home usa google_home.
URL absoluta usa url.
YouTube search usa youtube.
Google search usa google.
Sitios conocidos usan auto.
Investigación usa web_search.

## Criterios de fallo

El agente no llamó herramienta.
El agente usó web_search para abrir YouTube.
El agente usó web_search para abrir Google.
El agente usó browser_search para noticias resumidas.
El agente usó browser_search para documentación resumida.
El agente inventó que abrió algo.
El agente inventó que leyó una página.
El agente eligió target incorrecto.

## Frases prohibidas

No digas: No puedo abrir el navegador.
No digas: No puedo abrir YouTube.
No digas: No puedo abrir Google.
No digas: No tengo herramientas para abrir eso.
No digas: Puedo ayudarte a buscar si quieres.
No digas: Deberías abrirlo tú.

## Regla final
