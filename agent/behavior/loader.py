from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass


SOUL_PATH = Path(__file__).with_name("SOUL.md")
FALLBACK_SOUL_PROMPT = (
    "You are Tuli, a local agent. Be honest, concise, helpful, and do not pretend to have executed tools."
)


@dataclass(frozen=True)
class SoulLoadResult:
    loaded: bool
    source_path: str
    content: str
    fallback_used: bool
    error: str | None = None


@lru_cache(maxsize=1)
def load_soul() -> SoulLoadResult:
    try:
        content = SOUL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return SoulLoadResult(
            loaded=False,
            source_path=str(SOUL_PATH),
            content=FALLBACK_SOUL_PROMPT,
            fallback_used=True,
            error="SOUL.md not found",
        )
    except OSError as exc:
        return SoulLoadResult(
            loaded=False,
            source_path=str(SOUL_PATH),
            content=FALLBACK_SOUL_PROMPT,
            fallback_used=True,
            error=str(exc),
        )

    stripped = content.strip()
    if not stripped:
        return SoulLoadResult(
            loaded=False,
            source_path=str(SOUL_PATH),
            content=FALLBACK_SOUL_PROMPT,
            fallback_used=True,
            error="SOUL.md is empty",
        )
    return SoulLoadResult(
        loaded=True,
        source_path=str(SOUL_PATH),
        content=stripped,
        fallback_used=False,
    )


def get_soul_prompt() -> str:
    return load_soul().content

