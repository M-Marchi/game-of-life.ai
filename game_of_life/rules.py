from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

KNOWN_RESOURCES = {"wood", "water", "food", "meat", "stone", "tools"}
WORLD_EFFECTS = {
    "food_regeneration",
    "wood_regeneration",
    "stone_regeneration",
    "hunger_rate_multiplier",
    "thirst_rate_multiplier",
}
PROFESSION_EFFECTS = {
    "knowledge_gain",
    "beauty_gain",
    "health_gain",
    "social_gain",
    "confidence_gain",
    "stress_relief",
}
KNOWN_EFFECTS = WORLD_EFFECTS | PROFESSION_EFFECTS
EffectName = Literal[
    "food_regeneration",
    "wood_regeneration",
    "stone_regeneration",
    "hunger_rate_multiplier",
    "thirst_rate_multiplier",
    "knowledge_gain",
    "beauty_gain",
    "health_gain",
    "social_gain",
    "confidence_gain",
    "stress_relief",
]
SAFE_ID = re.compile(r"^[a-z][a-z0-9_-]{2,39}$")


class RuleProposal(BaseModel):
    """A data-only rule proposed by the model. It can never contain executable code."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(default=1, ge=1)
    category: Literal["profession", "recipe", "building", "world_rule"]
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(min_length=5, max_length=400)
    requirements: dict[str, int] = Field(
        default_factory=dict,
        description="Physical input resources only: wood, water, food, meat, stone, tools.",
    )
    outputs: dict[str, int] = Field(
        default_factory=dict,
        description="Physical output resources only; never put social effects here.",
    )
    workplace: str | None = None
    duration_ticks: int = Field(default=20, ge=1, le=10_000)
    effects: dict[EffectName, Annotated[float, Field(gt=0, le=10)]] = Field(
        default_factory=dict,
        description=(
            "Non-resource effects. Professions use knowledge_gain, beauty_gain, health_gain, "
            "social_gain, confidence_gain, stress_relief; world rules use regeneration or need "
            "multipliers."
        ),
    )
    activation_reason: str = Field(min_length=5, max_length=300)

    @model_validator(mode="after")
    def validate_safe_values(self) -> RuleProposal:
        if not SAFE_ID.fullmatch(self.id):
            raise ValueError("id must be a safe lowercase slug")
        resources = set(self.requirements) | set(self.outputs)
        unknown = resources - KNOWN_RESOURCES
        if unknown:
            raise ValueError(f"unknown resources: {sorted(unknown)}")
        quantities = [*self.requirements.values(), *self.outputs.values()]
        if any(value <= 0 or value > 100 for value in quantities):
            raise ValueError("resource quantities must be between 1 and 100")
        if self.category == "recipe" and not self.outputs:
            raise ValueError("recipes require at least one output")
        if self.category == "profession" and not self.outputs and not self.effects:
            raise ValueError("professions require outputs or a social effect")
        if self.category == "building" and not self.requirements:
            raise ValueError("buildings require a non-empty construction cost")
        unknown_effects = set(self.effects) - KNOWN_EFFECTS
        if unknown_effects:
            raise ValueError(f"unknown effects: {sorted(unknown_effects)}")
        if self.category == "world_rule" and set(self.effects) - WORLD_EFFECTS:
            raise ValueError("world rules may only use world effects")
        if self.category == "profession" and set(self.effects) - PROFESSION_EFFECTS:
            raise ValueError("professions may only use profession effects")
        if self.category not in {"world_rule", "profession"} and self.effects:
            raise ValueError("only world rules and professions may define effects")
        return self


@dataclass(frozen=True, slots=True)
class RuleValidation:
    accepted: bool
    reasons: tuple[str, ...] = ()


@dataclass(slots=True)
class RuleRegistry:
    active: dict[str, RuleProposal] = field(default_factory=dict)
    rejected: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def validate(self, proposal: RuleProposal) -> RuleValidation:
        reasons: list[str] = []
        current = self.active.get(proposal.id)
        if current and proposal.version <= current.version:
            reasons.append("version must increase")

        input_total = sum(proposal.requirements.values())
        output_total = sum(proposal.outputs.values())
        if proposal.category == "recipe" and input_total == 0:
            reasons.append("recipes cannot create resources from nothing")
        if input_total and output_total > input_total * 4:
            reasons.append("output exceeds the safe conversion ratio")
        if proposal.category == "world_rule" and not proposal.effects:
            reasons.append("world rules require bounded effects")
        return RuleValidation(not reasons, tuple(reasons))

    def activate(self, proposal: RuleProposal) -> RuleValidation:
        validation = self.validate(proposal)
        if validation.accepted:
            self.active[proposal.id] = proposal
        else:
            self.rejected[proposal.id] = validation.reasons
        return validation

    def rollback(self, rule_id: str) -> RuleProposal | None:
        return self.active.pop(rule_id, None)
