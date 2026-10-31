"""Tests for trusted runtime Skill Registry."""

import pytest

from backend.app.agent_skills.registry import SkillRegistry, SkillRegistryError


def test_skill_registry_loads_trusted_skills() -> None:
    """Skill registry loads runtime skills and calculates SHA-256 hashes."""
    registry = SkillRegistry()
    skills = registry.list_skills()
    assert len(skills) >= 3

    skill_names = [s.name for s in skills]
    assert "payment-triage" in skill_names
    assert "fraud-investigation" in skill_names
    assert "evidence-intake" in skill_names

    triage = registry.get_skill("payment-triage")
    assert triage.version == "1.0.0"
    assert len(triage.content_hash) == 64  # SHA-256 hex length
    assert "get_payment" in triage.allowed_tools
    assert registry.validate_tool_permission("payment-triage", "get_payment") is True
    assert registry.validate_tool_permission("payment-triage", "execute_refund") is False


def test_unknown_skill_raises_error() -> None:
    """Requesting an unapproved skill fails closed."""
    registry = SkillRegistry()
    with pytest.raises(SkillRegistryError):
        registry.get_skill("untrusted-user-skill")
