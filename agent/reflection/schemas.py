from pydantic import BaseModel, Field


class RetryState(BaseModel):
    attempt_number: int
    max_retries: int = 2
    previous_errors: list[str] = Field(default_factory=list)

    @property
    def executions_so_far(self) -> int:
        return self.attempt_number + 1

    @property
    def can_retry(self) -> bool:
        return self.attempt_number < self.max_retries


class ReflectionDecision(BaseModel):
    should_retry: bool = False
    should_stop: bool = False
    reason: str = "not_evaluated"
    user_message: str = ""
