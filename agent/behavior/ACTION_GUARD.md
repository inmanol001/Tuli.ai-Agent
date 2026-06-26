# ACTION_GUARD

## Propósito

Evitar que Tuli responda como chat cuando el usuario pidió una acción real.

Este guard no reemplaza al router, no llama modelos y no ejecuta herramientas directamente.

## Regla principal

Detectar intención operativa usando:

```txt
verbo de acción + objetivo explícito
