from pathlib import Path

from agent.capabilities.skills.loader import SkillDefinition, load_skill


class SkillSelector:
    def __init__(self, root: str | Path = "agent/capabilities/skills") -> None:
        self.root = Path(root)

    def select(self, names: list[str]) -> list[SkillDefinition]:
        selected: list[SkillDefinition] = []
        for name in names:
            if name == "browser_search":
                path = self.root / "browser_search" / "SKILL.md"
                if path.exists():
                    skill = load_skill(path)
                    if skill.name == "browser_search":
                        selected.append(skill)
            elif name == "open_app":
                path = self.root / name / "SKILL.md"
                if path.exists():
                    skill = load_skill(path)
                    if skill.name == name:
                        selected.append(skill)
            elif name == "macos_windows":
                path = self.root / "macos_windows.md"
                if path.exists():
                    skill = load_skill(path)
                    if skill.name == "macos_windows":
                        selected.append(skill)
            elif name == "macos_observation":
                path = self.root / "macos_observation.md"
                if path.exists():
                    skill = load_skill(path)
                    if skill.name == "macos_observation":
                        selected.append(skill)
            elif name == "macos_spaces":
                path = self.root / "macos_spaces.md"
                if path.exists():
                    skill = load_skill(path)
                    if skill.name == "macos_spaces":
                        selected.append(skill)
        return selected
