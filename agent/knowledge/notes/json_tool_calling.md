# JSON y Tool Calling

En este agente local, el modelo principal debe devolver tool calls usando salida estructurada validada con Pydantic.

No se debe parsear texto libre para detectar herramientas. El flujo correcto es:

ToolPlanner -> ToolValidator -> Executor -> ToolResult -> final_answer.
