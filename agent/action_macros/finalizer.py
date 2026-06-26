from __future__ import annotations

from pydantic import BaseModel

from agent.action_macros.schemas import ActionMacroResult


WINDOW_ACTION_LABELS = {
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


class ActionMacroFinalizerResult(BaseModel):
    text: str
    fallback: bool = True
    error: str | None = None


class ActionMacroFinalizer:
    """Turn a completed macro recipe into a concise user-facing summary."""

    def finalize(
        self, *, user_message: str, workflow_result: ActionMacroResult
    ) -> ActionMacroFinalizerResult:
        try:
            return ActionMacroFinalizerResult(
                text=self._finalize_text(user_message=user_message, workflow_result=workflow_result),
                fallback=True,
            )
        except Exception as exc:
            return ActionMacroFinalizerResult(
                text="No pude redactar el resultado de la action macro.",
                fallback=True,
                error=str(exc),
            )

    def _finalize_text(self, *, user_message: str, workflow_result: ActionMacroResult) -> str:
        if workflow_result.workflow_name == "tile_active_window":
            return self._finalize_tile_active_window(workflow_result)
        if workflow_result.workflow_name == "open_app_and_tile_window":
            return self._finalize_open_app_and_tile_window(workflow_result)
        if workflow_result.workflow_name == "open_browser_and_search":
            return self._finalize_open_browser_and_search(workflow_result)
        if workflow_result.workflow_name == "play_random_youtube_video":
            return self._finalize_play_random_youtube_video(workflow_result)
        if workflow_result.workflow_name == "open_work_setup":
            return self._finalize_open_work_setup(workflow_result)
        return "La action macro se ejecutó, pero no tengo un resumen específico."

    def _finalize_tile_active_window(self, workflow_result: ActionMacroResult) -> str:
        if workflow_result.success:
            action = workflow_result.inputs.get("window_action", "window_action")
            return f"Envié la acción para {WINDOW_ACTION_LABELS.get(action, action)}."

        if workflow_result.stopped_reason == "no_frontmost_window":
            error = self._step_error(workflow_result, "macos_observe_frontmost")
            return f"No pude revisar la ventana activa antes de continuar: {error}"
        if workflow_result.stopped_reason == "step_failed:window_native_tiling":
            error = self._step_error(workflow_result, "window_native_tiling")
            return f"No pude mover la ventana activa: {error}"
        error = workflow_result.error or "error desconocido"
        return f"No pude completar la action macro: {error}"

    def _finalize_open_app_and_tile_window(self, workflow_result: ActionMacroResult) -> str:
        app_name = workflow_result.inputs.get("app_name", "la aplicación")
        action = workflow_result.inputs.get("window_action", "window_action")
        human_action = WINDOW_ACTION_LABELS.get(action, action)

        if workflow_result.success:
            return f"Abrí {app_name} y envié la acción para {human_action}."

        if workflow_result.stopped_reason == "step_failed:open_app":
            error = self._step_error(workflow_result, "open_app")
            return f"No pude completar la action macro porque no se pudo abrir {app_name}: {error}"
        if workflow_result.stopped_reason == "step_failed:macos_observe_frontmost":
            error = self._step_error(workflow_result, "macos_observe_frontmost")
            return f"No pude revisar la ventana activa antes de continuar: {error}"
        if workflow_result.stopped_reason == "step_failed:window_native_tiling":
            error = self._step_error(workflow_result, "window_native_tiling")
            return f"Abrí {app_name}, pero no pude mover la ventana activa: {error}"
        error = workflow_result.error or "error desconocido"
        return f"No pude completar la action macro: {error}"

    def _finalize_open_browser_and_search(self, workflow_result: ActionMacroResult) -> str:
        if workflow_result.success:
            query = workflow_result.inputs.get("query", "la búsqueda")
            target = workflow_result.inputs.get("target", "web")
            if target == "youtube":
                return f"Busqué {query} en YouTube."
            return f"Busqué {query} en el navegador."
        error = workflow_result.error or "error desconocido"
        return f"No pude completar la action macro: {error}"

    def _finalize_play_random_youtube_video(self, workflow_result: ActionMacroResult) -> str:
        if workflow_result.success:
            return "Abrí YouTube en Chrome y dejé un video aleatorio listo."
        if workflow_result.stopped_reason == "step_failed:open_app":
            error = self._step_error(workflow_result, "open_app")
            return f"No pude abrir Chrome para YouTube: {error}"
        if workflow_result.stopped_reason == "step_failed:browser_search":
            error = self._step_error(workflow_result, "browser_search")
            return f"Abrí Chrome, pero no pude cargar YouTube: {error}"
        error = workflow_result.error or "error desconocido"
        return f"No pude completar la action macro: {error}"

    def _finalize_open_work_setup(self, workflow_result: ActionMacroResult) -> str:
        if workflow_result.success:
            return "Abrí tu setup de trabajo: Chrome, Visual Studio Code y Terminal."
        if workflow_result.stopped_reason == "step_failed:open_app":
            failed_step = self._failed_step(workflow_result)
            if failed_step is not None:
                app_name = failed_step.tool_call.arguments.get("app_name", "la aplicación")
                error = failed_step.tool_result.error or "error desconocido"
                return f"No pude completar el setup de trabajo: no se pudo abrir {app_name}: {error}"
            return f"No pude completar el setup de trabajo: {workflow_result.error or 'error desconocido'}"
        if workflow_result.stopped_reason == "step_failed:browser_search":
            error = self._step_error(workflow_result, "browser_search")
            return f"Abrí las aplicaciones, pero no pude abrir ChatGPT: {error}"
        if workflow_result.stopped_reason == "step_failed:open_url":
            error = self._step_error(workflow_result, "open_url")
            return f"Abrí las aplicaciones, pero no pude abrir ChatGPT: {error}"
        error = workflow_result.error or "error desconocido"
        return f"No pude completar la action macro: {error}"

    def _step_error(self, workflow_result: ActionMacroResult, tool_name: str) -> str:
        for step in workflow_result.steps:
            if step.tool_call.tool_name == tool_name:
                return step.tool_result.error or "error desconocido"
        return workflow_result.error or "error desconocido"

    def _failed_step(self, workflow_result: ActionMacroResult):
        for step in workflow_result.steps:
            if step.stopped or not step.success:
                return step
        return None


WorkflowFinalizer = ActionMacroFinalizer
WorkflowFinalizerResult = ActionMacroFinalizerResult
