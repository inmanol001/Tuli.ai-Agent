from __future__ import annotations

import json

from pydantic import BaseModel

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.models.ollama_client import OllamaClient


TOOL_FINALIZER_SYSTEM_PROMPT = """Eres el finalizador de acciones de un agente local.
Recibirás el mensaje original del usuario, la tool llamada y el resultado real de la tool.
Responde en español, natural y breve.
No llames herramientas.
No inventes resultados.
No digas que una acción se completó si el ToolResult no lo confirma.
Si success=false, explica brevemente el error.
Si success=true y verified=false, di que se envió la orden o se abrió la solicitud, pero no digas que lo verificaste.
Si success=true y hay datos confirmados, responde con el resultado confirmado.
No menciones JSON, ToolResult, metadata ni detalles internos salvo que ayuden al usuario.
"""


WINDOW_NATIVE_TILING_ACTIONS = {
    "fill": "llenar la pantalla",
    "center": "centrar la ventana activa",
    "left": "colocar la ventana activa a la izquierda",
    "right": "colocar la ventana activa a la derecha",
    "top": "colocar la ventana activa arriba",
    "bottom": "colocar la ventana activa abajo",
    "top-left": "colocar la ventana activa en la esquina superior izquierda",
    "top-right": "colocar la ventana activa en la esquina superior derecha",
    "bottom-left": "colocar la ventana activa en la esquina inferior izquierda",
    "bottom-right": "colocar la ventana activa en la esquina inferior derecha",
    "left-right": "usar la acción Left & Right en la ventana activa",
    "quarters": "usar la acción Quarters en la ventana activa",
    "return": "volver la ventana activa a su tamaño anterior",
}


class ToolFinalizerResult(BaseModel):
    model_used: str
    text: str
    fallback: bool = False
    error: str | None = None


class ToolFinalizerModel:
    def __init__(
        self,
        client: OllamaClient | None = None,
        model: str = "llama3-groq-tool-use:8b",
    ) -> None:
        self.client = client or OllamaClient()
        self.model = model

    def finalize(
        self,
        *,
        user_message: str,
        tool_call: ToolCall,
        tool_result: ToolResult,
    ) -> ToolFinalizerResult:
        simple_text = self._deterministic_simple_finalize(tool_call, tool_result)
        if simple_text is not None:
            return ToolFinalizerResult(
                model_used="deterministic_simple_finalizer",
                text=simple_text,
                fallback=True,
            )

        payload = {
            "user_message": user_message,
            "tool_call": tool_call.model_dump(mode="json"),
            "tool_result": tool_result.model_dump(mode="json"),
        }
        try:
            text = self.client.chat(
                self.model,
                [
                    {"role": "system", "content": TOOL_FINALIZER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                stream=False,
                options={"temperature": 0.3},
            ).strip()
            if not text:
                raise ValueError("ToolFinalizerModel devolvio texto vacio")
            return ToolFinalizerResult(model_used=self.model, text=text)
        except Exception as exc:
            return ToolFinalizerResult(
                model_used=self.model,
                text=self._fallback_finalize(tool_call, tool_result),
                fallback=True,
                error=str(exc),
            )

    def _deterministic_simple_finalize(
        self,
        tool_call: ToolCall,
        tool_result: ToolResult,
    ) -> str | None:
        simple_tools = {
            "browser_search",
            "open_app",
            "macos_space_mission_control",
            "macos_space_next",
            "macos_space_previous",
            "macos_space_switch_desktop_number",
            "window_native_tiling",
        }
        if tool_result.tool_name not in simple_tools:
            return None
        return self._fallback_finalize(tool_call, tool_result)

    def _fallback_finalize(self, tool_call: ToolCall, tool_result: ToolResult) -> str:
        if tool_result.tool_name == "browser_search":
            if not tool_result.success:
                return f"No pude abrir el contenido web: {tool_result.error}".strip()
            target = tool_result.data.get("target", "auto")
            url = tool_result.data.get("url", "")
            if target in {"web", "google", "youtube", "auto"}:
                return f"Abrí la búsqueda en el navegador: {url}".strip()
            return f"Abrí la página en el navegador: {url}".strip()

        if tool_result.tool_name == "open_app":
            app_name = tool_result.data.get("app_name", "la aplicación")
            if not tool_result.success:
                return f"No pude abrir la aplicación: {tool_result.error}".strip()
            if tool_result.metadata.get("verified") is False:
                return (
                    f"Envié la orden para abrir {app_name}, "
                    "pero no pude confirmar que quedó activa."
                )
            return f"Abrí {app_name}."

        if tool_result.tool_name == "macos_permissions_check":
            if tool_result.success:
                data = tool_result.data
                return (
                    "Permisos de macOS: "
                    f"accessibility={data.get('accessibility')}, "
                    f"screen_recording={data.get('screen_recording')}, "
                    f"automation={data.get('automation')}."
                )
            return f"No pude revisar permisos de macOS: {tool_result.error}"

        if tool_result.tool_name == "macos_observe_frontmost":
            if tool_result.success:
                app = tool_result.data.get("app_name") or "desconocida"
                title = tool_result.data.get("window_title")
                suffix = f" - {title}" if title else ""
                return f"App activa: {app}{suffix}."
            return f"No pude observar la app activa: {tool_result.error}"

        if tool_result.tool_name == "macos_visible_windows":
            count = tool_result.data.get("count", 0)
            if tool_result.success:
                return f"Veo {count} ventanas visibles."
            return f"No pude listar ventanas visibles: {tool_result.error}"

        if tool_result.tool_name == "macos_list_apps":
            if tool_result.success:
                installed_count = len(tool_result.data.get("installed_apps") or [])
                known_count = len(tool_result.data.get("known_apps") or [])
                return (
                    f"Tengo {known_count} apps conocidas y detecté "
                    f"{installed_count} apps instaladas."
                )
            return f"No pude listar aplicaciones: {tool_result.error}"

        if tool_result.tool_name == "macos_space_status":
            if tool_result.success:
                current = tool_result.data.get("current_space", "unknown")
                app = tool_result.data.get("frontmost_app", "unknown")
                return f"Estado de Spaces: current_space={current}, frontmost_app={app}."
            return f"No pude revisar el estado de Spaces: {tool_result.error}"

        if tool_result.tool_name == "macos_space_next":
            if tool_result.success:
                return "Envié el atajo para cambiar al siguiente escritorio."
            return f"No pude cambiar al siguiente escritorio: {tool_result.error}"

        if tool_result.tool_name == "macos_space_previous":
            if tool_result.success:
                return "Envié el atajo para volver al escritorio anterior."
            return f"No pude volver al escritorio anterior: {tool_result.error}"

        if tool_result.tool_name == "macos_space_mission_control":
            if tool_result.success:
                return "Envié el atajo para abrir Mission Control."
            return f"No pude abrir Mission Control: {tool_result.error}"

        if tool_result.tool_name == "macos_space_switch_desktop_number":
            number = tool_result.data.get("number") or tool_call.arguments.get("number")
            if tool_result.success:
                return f"Envié el atajo para cambiar al escritorio {number}."
            return f"No pude cambiar al escritorio {number}: {tool_result.error}".strip()

        if tool_result.tool_name == "window_native_tiling":
            action = (
                tool_result.data.get("action")
                or tool_call.arguments.get("action")
                or "window_action"
            )
            human_action = WINDOW_NATIVE_TILING_ACTIONS.get(action, "mover la ventana activa")
            if not tool_result.success:
                return f"No pude mover la ventana activa: {tool_result.error}".strip()
            if tool_result.data.get("verified") is False:
                return f"Envié la acción nativa de macOS para {human_action}."
            return f"Realicé la acción nativa de macOS para {human_action}."

        if not tool_result.success:
            return f"No pude completar la acción: {tool_result.error}".strip()
        return "La acción se ejecutó, pero no tengo más detalles confirmados."
