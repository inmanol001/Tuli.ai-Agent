from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.plan_schemas import WorkflowPlanStep
from agent.workflows.requirement_checker import RequirementChecker, RequirementContext


def test_requirement_checker_asks_specific_canva_question_when_details_are_missing():
    result = RequirementChecker().check(
        RequirementContext(
            workflow_name="design_canva_post",
            user_goal="Haz un post en Canva del Día del Padre",
            state={"topic": "Día del Padre"},
        )
    )

    assert result.can_continue is False
    assert result.needs_user_input is True
    assert result.needs_approval is False
    assert result.reason == "missing_info"
    assert result.missing_info == ["format", "style", "platform"]
    assert "post cuadrado" in result.questions[0]
    assert "estilo elegante" in result.questions[0]


def test_requirement_checker_requests_approval_for_risky_action():
    result = RequirementChecker().check(
        RequirementContext(
            workflow_name="filesystem_workflow",
            user_goal="Borra el archivo temporal",
            step_title="Eliminar archivo",
        )
    )

    assert result.can_continue is False
    assert result.needs_approval is True
    assert result.needs_user_input is False
    assert result.reason == "safety_confirmation"
    assert result.approval_request is not None


def test_requirement_checker_requests_visual_validation_when_needed():
    result = RequirementChecker().check(
        RequirementContext(
            workflow_name="design_canva_post",
            user_goal="Haz un post en Canva del Día del Padre",
            requires_visual_validation=True,
        )
    )

    assert result.can_continue is False
    assert result.needs_approval is True
    assert result.reason == "visual_validation"
    assert "visualmente" in result.approval_request


def test_requirement_checker_requests_correction_when_user_is_revising():
    result = RequirementChecker().check(
        RequirementContext(
            workflow_name="design_canva_post",
            user_goal="Haz un post en Canva del Día del Padre",
            correction_request=True,
        )
    )

    assert result.can_continue is False
    assert result.needs_user_input is True
    assert result.needs_approval is False
    assert result.reason == "correction_request"
    assert result.questions == ["¿Qué ajuste específico quieres que haga?"]


def test_workflow_plan_manager_applies_requirement_checks_without_marking_failed(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    plan = manager.create_plan(
        workflow_name="design_canva_post",
        user_goal="Haz un post en Canva del Día del Padre",
        session_id="session-3",
        steps=[WorkflowPlanStep(title="Abrir Canva", kind="tool")],
        state={"topic": "Día del Padre"},
    )

    step_id = plan.steps[0].id
    result = manager.check_requirements(plan, step_id)

    assert result.needs_user_input is True
    loaded = manager.load_plan(plan.workflow_id, session_id="session-3")
    assert loaded.status == "waiting_user_input"
    assert loaded.steps[0].status == "waiting_user_input"
    assert loaded.steps[0].question is not None

    approval_plan = manager.create_plan(
        workflow_name="filesystem_workflow",
        user_goal="Borra el archivo temporal",
        session_id="session-4",
        steps=[WorkflowPlanStep(title="Eliminar archivo", kind="tool")],
    )
    approval_step_id = approval_plan.steps[0].id
    approval_result = manager.check_requirements(
        approval_plan,
        approval_step_id,
        requires_approval=True,
    )

    assert approval_result.needs_approval is True
    approval_loaded = manager.load_plan(approval_plan.workflow_id, session_id="session-4")
    assert approval_loaded.status == "waiting_approval"
    assert approval_loaded.steps[0].status == "waiting_approval"
