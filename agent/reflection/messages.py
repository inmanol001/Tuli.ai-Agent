from agent.reflection.schemas import ReflectionDecision


def final_stop_message(decision: ReflectionDecision) -> str:
    return decision.user_message or "No pude completar la accion tras verificar el resultado."
