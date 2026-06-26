from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.plan_schemas import WorkflowPlanStep


def test_human_checkpoint_payload_uses_waiting_user_input_shape(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    plan = manager.create_plan(
        workflow_name="design_canva_post",
        user_goal="Haz un post en Canva del Día del Padre",
        session_id="session-10",
        steps=[WorkflowPlanStep(title="Abrir Canva", kind="tool")],
        state={"topic": "Día del Padre"},
    )

    payload = manager.build_human_checkpoint_payload(
        plan,
        plan.steps[0].id,
        kind="missing_info",
        question="¿Lo quieres como post cuadrado, historia o flyer?",
        options=["post cuadrado", "historia", "flyer"],
    )

    assert payload["status"] == "waiting_user_input"
    assert payload["needs_user_input"] is True
    assert payload["text"] == "¿Lo quieres como post cuadrado, historia o flyer?"
    assert payload["workflow_id"] == plan.workflow_id
    assert payload["current_step_id"] == plan.steps[0].id
    loaded = manager.load_plan(plan.workflow_id, session_id="session-10")
    assert loaded.status == "waiting_user_input"
    assert loaded.active_checkpoint_id is not None
    assert loaded.checkpoints[0]["kind"] == "missing_info"


def test_human_checkpoint_resolution_releases_pause_and_updates_state(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    plan = manager.create_plan(
        workflow_name="design_canva_post",
        user_goal="Haz un post en Canva del Día del Padre",
        session_id="session-11",
        steps=[WorkflowPlanStep(title="Abrir Canva", kind="tool")],
        state={"topic": "Día del Padre"},
    )

    checkpoint = manager.create_human_checkpoint(
        plan,
        plan.steps[0].id,
        kind="preference",
        question="¿Quieres estilo elegante, playero o promocional?",
        options=["elegante", "playero", "promocional"],
    )

    manager.resolve_human_checkpoint(
        plan,
        checkpoint.checkpoint_id,
        user_response="playero",
        state_updates={"style": "playero"},
    )

    loaded = manager.load_plan(plan.workflow_id, session_id="session-11")
    assert loaded.status == "running"
    assert loaded.state["style"] == "playero"
    assert loaded.checkpoints[0]["resolved"] is True
    assert loaded.checkpoints[0]["user_response"] == "playero"


def test_human_checkpoint_rejection_marks_revision(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    plan = manager.create_plan(
        workflow_name="design_canva_post",
        user_goal="Haz un post en Canva del Día del Padre",
        session_id="session-12",
        steps=[WorkflowPlanStep(title="Abrir Canva", kind="tool")],
    )

    checkpoint = manager.create_human_checkpoint(
        plan,
        plan.steps[0].id,
        kind="approval",
        question="¿Me das permiso para continuar con este diseño?",
        options=["approve", "reject"],
    )

    manager.resolve_human_checkpoint(
        plan,
        checkpoint.checkpoint_id,
        approved=False,
    )

    loaded = manager.load_plan(plan.workflow_id, session_id="session-12")
    assert loaded.steps[0].status == "needs_revision"
    assert loaded.steps[0].approved is False
