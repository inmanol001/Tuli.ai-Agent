from agent.capabilities.skills.loader import SkillDefinition


def validate_skill(skill: SkillDefinition) -> bool:
    return bool(skill.name and skill.content.strip())

