from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.plan_schemas import WorkflowPlanStep


def test_workflow_plan_manager_renders_and_persists_plan(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    plan = manager.create_plan(
        workflow_name="design_canva_post",
        user_goal="Crear un post para el Día del Padre en Canva.",
        session_id="session-1",
        status="running",
        steps=[
            WorkflowPlanStep(title="Entender intención del usuario", kind="reason", status="completed"),
            WorkflowPlanStep(title="Abrir Canva", kind="tool", status="pending"),
        ],
        state={"Tema": "Día del Padre", "Formato": "post", "Plataforma": "Canva"},
    )

    rendered = manager.render_markdown(plan)
    assert "# Workflow Plan: design_canva_post" in rendered
    assert "## Objetivo" in rendered
    assert "Crear un post para el Día del Padre en Canva." in rendered
    assert "## Estado" in rendered
    assert "running" in rendered
    assert "- [x] Entender intención del usuario" in rendered
    assert "- [ ] Abrir Canva" in rendered
    assert "Tema: Día del Padre" in rendered

    saved = manager.save_plan(plan)
    loaded = manager.load_plan(saved.workflow_id, session_id="session-1")

    assert loaded.workflow_id == saved.workflow_id
    assert loaded.workflow_name == "design_canva_post"
    assert loaded.user_goal == "Crear un post para el Día del Padre en Canva."
    assert len(loaded.steps) == 2
    assert loaded.state["tema"] == "Día del Padre"
    assert loaded.notes == []


def test_workflow_plan_manager_updates_steps_and_state(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    plan = manager.create_plan(
        workflow_name="design_canva_post",
        user_goal="Crear un post para el Día del Padre en Canva.",
        session_id="session-2",
        steps=[WorkflowPlanStep(title="Abrir Canva", kind="tool")],
    )

    step_id = plan.steps[0].id
    manager.mark_step_running(plan, step_id)
    manager.mark_step_waiting_user_input(plan, step_id, question="¿Qué tema quieres?")
    manager.update_state(plan, {"topic": "Día del Padre"})
    manager.add_note(plan, "Pendiente abrir Canva.")

    loaded = manager.load_plan(plan.workflow_id, session_id="session-2")
    assert loaded.status == "waiting_user_input"
    assert loaded.steps[0].status == "waiting_user_input"
    assert loaded.steps[0].question == "¿Qué tema quieres?"
    assert loaded.state["topic"] == "Día del Padre"
    assert loaded.notes == ["Pendiente abrir Canva."]
