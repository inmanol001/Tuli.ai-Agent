MEDIUM_OR_HIGH_RISK = {"medium", "high"}


def requires_confirmation(risk_level: str) -> bool:
    return risk_level in MEDIUM_OR_HIGH_RISK

