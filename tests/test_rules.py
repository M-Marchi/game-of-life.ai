from __future__ import annotations

import pytest
from pydantic import ValidationError

from game_of_life.rules import RuleProposal, RuleRegistry


def test_safe_recipe_can_be_activated() -> None:
    proposal = RuleProposal(
        id="stone_tools",
        category="recipe",
        name="Stone tools",
        description="Turns wood and stone into useful tools.",
        requirements={"wood": 2, "stone": 1},
        outputs={"tools": 1},
        activation_reason="Gatherers need better tools.",
    )
    registry = RuleRegistry()

    validation = registry.activate(proposal)

    assert validation.accepted
    assert registry.active[proposal.id] == proposal


def test_rule_rejects_code_and_unknown_resources() -> None:
    with pytest.raises(ValidationError):
        RuleProposal.model_validate(
            {
                "id": "unsafe_rule",
                "category": "recipe",
                "name": "Unsafe rule",
                "description": "Should never be accepted.",
                "requirements": {"uranium": 1},
                "outputs": {"food": 1},
                "activation_reason": "Trying unsafe input.",
                "code": "exec('bad')",
            }
        )


def test_rule_rejects_runaway_conversion() -> None:
    proposal = RuleProposal(
        id="food_multiplier",
        category="recipe",
        name="Food multiplier",
        description="Produces an unreasonable amount of food.",
        requirements={"food": 1},
        outputs={"food": 10},
        activation_reason="The settlement is hungry.",
    )

    validation = RuleRegistry().activate(proposal)

    assert not validation.accepted


def test_world_rule_rejects_unknown_effect() -> None:
    with pytest.raises(ValidationError):
        RuleProposal(
            id="unsafe_effect",
            category="world_rule",
            name="Unsafe effect",
            description="Attempts to add an unsupported effect.",
            effects={"execute_code": 1},
            activation_reason="This should be rejected.",
        )
