---
name: macos_windows
description: Mover o redimensionar la ventana activa de macOS usando acciones nativas seguras.
tools:
  - window_native_tiling
risk: low
---

# Objetivo

Usa `macos_windows` cuando el usuario quiera mover, redimensionar, centrar, llenar o acomodar la ventana activa/frontmost usando las acciones nativas de macOS.

Esta skill solo controla la ventana activa con acciones fijas permitidas. No hace clicks libres, no arrastra el mouse, no usa coordenadas, no escribe texto, no hace screenshots y no mueve ventanas arbitrarias por título.

# Cuándo usar esta skill

Usa esta skill cuando el usuario quiera:

1. Mover la ventana activa a la izquierda.
2. Mover la ventana activa a la derecha.
3. Mover la ventana activa arriba o abajo.
4. Mover la ventana activa a una esquina.
5. Centrar la ventana activa.
6. Hacer que la ventana activa llene la pantalla.
7. Volver la ventana activa a su tamaño anterior.
8. Usar una acción nativa de organización de ventanas de macOS.

No uses esta skill para:

1. Abrir apps. Para eso usa `open_app`.
2. Buscar en internet o abrir webs. Para eso usa `browser_search`.
3. Cambiar de escritorio, Space o Mission Control. Para eso usa `macos_spaces`.
4. Observar app activa, ventanas o permisos. Para eso usa `macos_observation`.
5. Hacer screenshots.
6. Hacer clicks libres.
7. Escribir o pegar texto.
8. Cerrar, minimizar o ocultar ventanas.
9. Mover una ventana específica por título.
10. Mover varias ventanas a la vez.
11. Ejecutar AppleScript dinámico generado por el modelo.
12. Usar coordenadas manuales.

# Selección de acción

Usa `window_native_tiling` con estos valores:

- `fill`: llenar pantalla o hacer la ventana grande usando la acción nativa Fill.
- `center`: centrar la ventana.
- `left`: mover/redimensionar la ventana hacia la izquierda.
- `right`: mover/redimensionar la ventana hacia la derecha.
- `top`: mover/redimensionar la ventana hacia arriba.
- `bottom`: mover/redimensionar la ventana hacia abajo.
- `top-left`: mover/redimensionar a la esquina superior izquierda.
- `top-right`: mover/redimensionar a la esquina superior derecha.
- `bottom-left`: mover/redimensionar a la esquina inferior izquierda.
- `bottom-right`: mover/redimensionar a la esquina inferior derecha.
- `left-right`: usar la acción nativa Left & Right.
- `quarters`: usar la acción nativa Quarters.
- `return`: volver al tamaño anterior.

# Cómo construir los argumentos

La tool recibe:

```json
{
  "action": "right"
}
```

`action` debe ser uno de los valores permitidos.

No inventes acciones fuera de la lista.

# Reglas importantes

1. Esta tool solo afecta la ventana activa/frontmost.
2. Si el usuario no especifica qué acción quiere hacer con la ventana, pide una aclaración breve.
3. Si el usuario pide controlar una ventana que no está activa, primero puede necesitarse observar el estado o pedirle que ponga esa ventana al frente.
4. No prometas verificación visual.
5. Si `verified=false`, la respuesta final debe decir que se envió la acción o se solicitó el cambio, no que se verificó visualmente.
6. No uses esta skill para acciones destructivas.
7. No uses AppleScript generado por el modelo.
8. La respuesta final debe basarse en el `ToolResult`.

# Etapa 1: detectar intención

Determina si el usuario quiere mover o redimensionar la ventana activa.

# Etapa 2: elegir acción

Mapea la intención del usuario a una acción permitida.

# Etapa 3: llamar la tool

Llama `window_native_tiling` con el `action` correcto.

# Etapa 4: responder después de ejecutar

Responde usando el resultado real de la tool.

Si la tool falla, explica brevemente el error.

Si la tool solo envió la acción y no verificó la posición final, responde de forma honesta.
