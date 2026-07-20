from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

KNOWN_RESOURCES = {"wood", "water", "food", "meat", "stone", "tools"}
KNOWN_EFFECTS = {
    "food_regeneration",
    "wood_regeneration",
    "stone_regeneration",
    "hunger_rate_multiplier",
    "thirst_rate_multiplier",
}
SAFE_ID = re.compile(r"^[a-z][a-z0-9_-]{2,39}$")


class RuleProposal(BaseModel):
    """A data-only rule proposed by the model. It can never contain executable code."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(default=1, ge=1)
    category: Literal["profession", "recipe", "building", "world_rule"]
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(min_length=5, max_length=400)
    requirements: dict[str, int] = Field(default_factory=dict)
    outputs: dict[str, int] = Field(default_factory=dict)
    workplace: str | None = None
    duration_ticks: int = Field(default=20, ge=1, le=10_000)
    effects: dict[str, float] = Field(default_factory=dict)
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
        if self.category == "profession" and not self.outputs:
            raise ValueError("professions require at least one output")
        if self.category == "building" and not self.requirements:
            raise ValueError("buildings require a non-empty construction cost")
        if any(abs(value) > 100 for value in self.effects.values()):
            raise ValueError("effect outside safe bounds")
        unknown_effects = set(self.effects) - KNOWN_EFFECTS
        if unknown_effects:
            raise ValueError(f"unknown effects: {sorted(unknown_effects)}")
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
