from __future__ import annotations

from agent.workflows.schemas import FullWorkflowStepDefinition


class DesignCanvaPostWorkflow:
    name = "design_canva_post"
    missing_tools = [
        "screenshot",
        "vision",
        "click",
        "type_text",
        "browser_tab_window_control",
        "file_download",
        "file_upload",
        "canva_automation",
    ]

    def build_phases(self, inputs) -> list[FullWorkflowStepDefinition]:
        topic = inputs.get("topic") or "el tema solicitado"
        return [
            FullWorkflowStepDefinition(
                phase_name="brief_parse",
                kind="reason",
                description="Identificar el brief y guardar el objetivo del workflow.",
                reason_task="extrae el tema principal y resume el brief en una frase.",
                output_key="brief_summary",
                can_run_now=True,
                simulated_actions=[f"Brief principal: {topic}"],
            ),
            FullWorkflowStepDefinition(
                phase_name="creative_brief",
                kind="reason",
                description="Crear un prompt creativo para la imagen principal.",
                reason_task="genera un prompt creativo para una imagen de post en Canva.",
                output_key="image_prompt",
                can_run_now=True,
            ),
            FullWorkflowStepDefinition(
                phase_name="workspace_setup",
                kind="tool",
                description="Abrir Canva en el navegador para preparar el workspace.",
                tool_goal="Abrir https://www.canva.com en el navegador usando la herramienta disponible mas segura.",
                allowed_tools=["browser_search"],
                tool_arguments={
                    "query": "https://www.canva.com",
                    "target": "url",
                },
                expected_result="Canva abierto o navegacion iniciada.",
                can_run_now=True,
            ),
            FullWorkflowStepDefinition(
                phase_name="open_chatgpt",
                kind="tool",
                description="Abrir ChatGPT para usarlo como fuente creativa.",
                tool_goal="Abrir https://chatgpt.com en el navegador usando la herramienta disponible mas segura.",
                allowed_tools=["browser_search"],
                tool_arguments={
                    "query": "https://chatgpt.com",
                    "target": "url",
                },
                expected_result="ChatGPT abierto o navegacion iniciada.",
                can_run_now=True,
            ),
            FullWorkflowStepDefinition(
                phase_name="prompt_generation",
                kind="reason",
                description="Redactar el copy y prompt final a partir del estado actual.",
                reason_task="redacta un copy breve y un prompt creativo listo para reutilizar.",
                output_key="copy_text",
                can_run_now=True,
            ),
            FullWorkflowStepDefinition(
                phase_name="image_request",
                kind="blocked_missing_tools",
                description="Enviar el prompt a la herramienta creativa futura.",
                simulated_actions=[
                    "Enviar el prompt a la fuente creativa.",
                    "Esperar el resultado de la imagen.",
                ],
                missing_tools=["type_text", "browser_tab_window_control"],
            ),
            FullWorkflowStepDefinition(
                phase_name="wait_and_verify",
                kind="verify",
                description="Esperar y verificar que la imagen esté lista.",
                simulated_actions=[
                    "Esperar a que el recurso esté disponible.",
                    "Verificar el resultado con captura y visión.",
                ],
                missing_tools=["screenshot", "vision"],
            ),
            FullWorkflowStepDefinition(
                phase_name="asset_transfer",
                kind="tool",
                description="Transferir el recurso hacia Canva con herramientas futuras.",
                tool_name="upload_file",
                tool_arguments={"destination": "canva"},
                simulated_actions=[
                    "Descargar el recurso.",
                    "Subirlo a Canva.",
                ],
                missing_tools=["file_download", "file_upload"],
            ),
            FullWorkflowStepDefinition(
                phase_name="compose_design",
                kind="action_macro",
                description="Componer el diseño final con acciones cortas futuras.",
                simulated_actions=[
                    "Colocar el recurso en el lienzo.",
                    "Ajustar jerarquía y composición.",
                ],
                missing_tools=["click", "type_text", "canva_automation"],
            ),
            FullWorkflowStepDefinition(
                phase_name="final_verification",
                kind="observe",
                description="Verificar el resultado final con una observación visual futura.",
                simulated_actions=[
                    "Tomar captura del resultado final.",
                    "Verificar legibilidad y composición.",
                ],
                missing_tools=["screenshot", "vision"],
            ),
            FullWorkflowStepDefinition(
                phase_name="finalize",
                kind="simulated",
                description="Cerrar el workflow y preparar el resumen.",
                simulated_actions=["Guardar el estado final del workflow."],
            ),
        ]
