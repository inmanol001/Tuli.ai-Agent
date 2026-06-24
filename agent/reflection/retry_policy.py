from agent.reflection.schemas import RetryState


def make_retry_state(
    attempt_number: int,
    *,
    max_retries: int = 2,
    previous_errors: list[str] | None = None,
) -> RetryState:
    return RetryState(
        attempt_number=attempt_number,
        max_retries=max_retries,
        previous_errors=previous_errors or [],
    )
