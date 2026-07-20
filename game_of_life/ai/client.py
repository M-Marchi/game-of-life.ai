from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from game_of_life.config import AIConfig
from game_of_life.models import Action, ActionType, Entity
from game_of_life.rules import RuleProposal


class AgentIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ActionType
    target_id: str | None = None
    resource: str | None = None
    amount: int = Field(default=1, ge=1, le=20)
    explanation: str = Field(min_length=1, max_length=300)

    def to_action(self) -> Action:
        return Action(
            kind=self.action,
            target_id=self.target_id,
            resource=self.resource,
            amount=self.amount,
            explanation=self.explanation,
        )


class AIClient(Protocol):
    def healthcheck(self) -> bool: ...

    def decide(self, entity: Entity, context: dict[str, Any]) -> AgentIntent: ...

    def propose_rule(self, context: dict[str, Any]) -> RuleProposal: ...


class AIUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class FakeAIClient:
    intent: AgentIntent | None = None
    rule: RuleProposal | None = None

    def healthcheck(self) -> bool:
        return True

    def decide(self, entity: Entity, context: dict[str, Any]) -> AgentIntent:
        return self.intent or AgentIntent(action=ActionType.IDLE, explanation="No urgent goal")

    def propose_rule(self, context: dict[str, Any]) -> RuleProposal:
        if self.rule:
            return self.rule
        return RuleProposal(
            id="water_carrier",
            category="profession",
            name="Water carrier",
            description="Carries water to inhabitants who are far from a lake.",
            outputs={"water": 1},
            duration_ticks=20,
            activation_reason="The settlement has a water shortage.",
        )


class OllamaAIClient:
    def __init__(self, config: AIConfig) -> None:
        self.config = config

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.config.endpoint.rstrip('/')}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIUnavailableError(str(exc)) from exc

    def healthcheck(self) -> bool:
        try:
            response = self._request("/api/tags")
        except AIUnavailableError:
            return False
        return any(model.get("name") == self.config.model for model in response.get("models", []))

    def decide(self, entity: Entity, context: dict[str, Any]) -> AgentIntent:
        prompt = (
            "You control one inhabitant in a deterministic society simulation. "
            "Choose one legal action from the supplied state. Prefer survival needs, then work "
            "and social goals. Never invent entity IDs. Return only data matching the "
            "JSON schema.\n"
            f"AGENT={json.dumps(_entity_context(entity), ensure_ascii=False)}\n"
            f"WORLD={json.dumps(context, ensure_ascii=False)}"
        )
        response = self._request(
            "/api/chat",
            {
                "model": self.config.model,
                "stream": False,
                "think": False,
                "format": AgentIntent.model_json_schema(),
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.2, "seed": context.get("seed", 42)},
            },
        )
        try:
            return AgentIntent.model_validate_json(response["message"]["content"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIUnavailableError(f"Invalid structured response: {exc}") from exc

    def propose_rule(self, context: dict[str, Any]) -> RuleProposal:
        prompt = (
            "You are the innovation council of a simulated settlement. Propose exactly one "
            "safe data-only profession, recipe, building, or bounded world rule that addresses "
            "the measured shortage. Use only wood, water, food, meat, stone, and tools. "
            "For shortages prefer a recipe or profession with explicit requirements and outputs. "
            "World rule effects may only be food_regeneration, wood_regeneration, "
            "stone_regeneration, hunger_rate_multiplier, or thirst_rate_multiplier. "
            "Never output Python or instructions. Return only the requested JSON schema.\n"
            f"SETTLEMENT={json.dumps(context, ensure_ascii=False)}"
        )
        messages = [{"role": "user", "content": prompt}]
        last_error: Exception | None = None
        for _ in range(2):
            response = self._request(
                "/api/chat",
                {
                    "model": self.config.model,
                    "stream": False,
                    "think": False,
                    "format": RuleProposal.model_json_schema(),
                    "messages": messages,
                    "options": {"temperature": 0.25, "seed": context.get("seed", 42)},
                },
            )
            content = response.get("message", {}).get("content", "")
            try:
                return RuleProposal.model_validate_json(content)
            except (TypeError, ValidationError) as exc:
                last_error = exc
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "The validator rejected that proposal. Correct it without "
                                "inventing new fields or effects. Profession and recipe rules "
                                "must use outputs; "
                                "effects should be empty unless category is world_rule. "
                                f"VALIDATION_ERROR={exc}"
                            ),
                        },
                    ]
                )
        raise AIUnavailableError(f"Invalid generated rule after repair: {last_error}")


def _entity_context(entity: Entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "name": entity.name,
        "age": round(entity.age_years, 1),
        "needs": {
            "hunger": round(entity.hunger, 1),
            "thirst": round(entity.thirst, 1),
            "energy": round(entity.energy, 1),
            "social": round(entity.social, 1),
        },
        "profession": entity.profession,
        "inventory": entity.inventory,
        "memories": entity.memories[-5:],
    }
