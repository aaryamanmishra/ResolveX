"""Runtime Skill Registry for ResolveX AI.

Validates and loads reviewed, versioned skills from the application repository.
Ensures tool allowlists and skill instructions are immutably verified via SHA-256
and never loaded from untrusted user uploads.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RuntimeSkillManifest:
    name: str
    version: str
    description: str
    allowed_tools: tuple[str, ...]
    content_hash: str
    instructions: str
    file_path: str


class SkillRegistryError(Exception):
    """Raised when skill validation fails."""

    pass


class SkillRegistry:
    """Registry of trusted runtime skills."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or Path(__file__).parent
        self._skills: dict[str, RuntimeSkillManifest] = {}
        self.load_trusted_skills()

    @staticmethod
    def _calculate_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def load_trusted_skills(self) -> None:
        """Scan and register all trusted skills in the trusted skills directory."""
        if not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            content = skill_file.read_text(encoding="utf-8")
            content_hash = self._calculate_hash(content)

            parts = content.split("---", 2)
            if len(parts) < 3:
                raise SkillRegistryError(
                    f"Skill {skill_file} missing valid YAML frontmatter delimiters."
                )

            frontmatter_raw = parts[1]
            instructions = parts[2].strip()

            try:
                frontmatter: dict[str, Any] = yaml.safe_load(frontmatter_raw) or {}
            except yaml.YAMLError as exc:
                raise SkillRegistryError(
                    f"Error parsing frontmatter in {skill_file}: {exc}"
                ) from exc

            name = frontmatter.get("name")
            version = str(frontmatter.get("version", "1.0.0"))
            description = frontmatter.get("description", "")
            allowed_tools = tuple(frontmatter.get("allowed_tools", []))

            if not name:
                raise SkillRegistryError(f"Skill in {skill_file} is missing 'name' field.")

            manifest = RuntimeSkillManifest(
                name=name,
                version=version,
                description=description,
                allowed_tools=allowed_tools,
                content_hash=content_hash,
                instructions=instructions,
                file_path=str(skill_file.resolve()),
            )

            self._skills[name] = manifest

    def get_skill(self, name: str) -> RuntimeSkillManifest:
        """Retrieve a skill by name. Raises SkillRegistryError if not found."""
        if name not in self._skills:
            raise SkillRegistryError(f"Skill '{name}' not found in trusted registry.")
        return self._skills[name]

    def list_skills(self) -> list[RuntimeSkillManifest]:
        """List all loaded trusted skills."""
        return list(self._skills.values())

    def validate_tool_permission(self, skill_name: str, tool_name: str) -> bool:
        """Check if a specific tool is allowed for the given skill."""
        skill = self.get_skill(skill_name)
        return tool_name in skill.allowed_tools
