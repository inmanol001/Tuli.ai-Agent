from pathlib import Path

from pydantic import BaseModel


class SkillDefinition(BaseModel):
    name: str
    description: str
    tools: list[str]
    content: str


def load_skill(path: str | Path) -> SkillDefinition:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(content)
    return SkillDefinition(
        name=frontmatter.get("name", path.parent.name),
        description=frontmatter.get("description", ""),
        tools=frontmatter.get("tools", []),
        content=content,
    )


def _parse_frontmatter(content: str) -> dict:
    if not content.startswith("---\n"):
        return {}
    try:
        _start, rest = content.split("---\n", 1)
        raw_frontmatter, _body = rest.split("\n---\n", 1)
    except ValueError:
        return {}
    try:
        import yaml
    except ModuleNotFoundError:
        return {}
    return yaml.safe_load(raw_frontmatter) or {}
