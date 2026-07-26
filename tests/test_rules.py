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


def test_profession_impacts_are_composable_but_bounded() -> None:
    proposal = RuleProposal(
        id="neighborhood_mediator",
        category="profession",
        name="Neighborhood mediator",
        description="Builds trust and relieves stress through local mediation.",
        impacts=[
            {"metric": "trust", "scope": "nearby", "amount": 3, "radius": 35},
            {"metric": "stress", "scope": "most_in_need", "amount": 4, "radius": 35},
        ],
        activation_reason="The settlement needs stronger relationships.",
    )

    assert len(proposal.impacts) == 2
    normalized = RuleProposal(
        id="stress_guide",
        category="profession",
        name="Stress guide",
        description="Helps a nearby person release accumulated stress.",
        impacts=[{"metric": "stress", "scope": "nearby", "amount": -3}],
        activation_reason="People need a safe way to decompress.",
    )
    assert normalized.impacts[0].amount == 3
    with pytest.raises(ValidationError):
        RuleProposal(
            id="unsafe_mediator",
            category="profession",
            name="Unsafe mediator",
            description="Attempts an unbounded intervention.",
            impacts=[{"metric": "trust", "scope": "nearby", "amount": 1000}],
            activation_reason="This should be rejected.",
        )


def test_profession_must_measurably_address_resource_shortage() -> None:
    counselor = RuleProposal(
        id="water_counselor",
        category="profession",
        name="Water counselor",
        description="Helps people discuss the stress caused by drought.",
        impacts=[{"metric": "stress", "scope": "nearby", "amount": 2}],
        activation_reason="There is not enough water.",
    )
    water_bearer = RuleProposal(
        id="water_bearer",
        category="profession",
        name="Water bearer",
        description="Brings water to thirsty people.",
        impacts=[{"metric": "thirst", "scope": "most_in_need", "amount": 5}],
        activation_reason="There is not enough water.",
    )

    assert not counselor.addresses_shortage("water")
    assert water_bearer.addresses_shortage("water")
    assert counselor.claimed_shortages() == {"water"}
