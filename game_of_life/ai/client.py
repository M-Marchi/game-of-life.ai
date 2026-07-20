from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    goal: str = Field(min_length=3, max_length=180)
    mood: Literal["calm", "hopeful", "curious", "proud", "afraid", "angry", "sad"]

    @model_validator(mode="after")
    def require_action_arguments(self) -> AgentIntent:
        target_actions = {
            ActionType.MOVE,
            ActionType.DRINK,
            ActionType.GATHER,
            ActionType.ATTACK,
            ActionType.TALK,
            ActionType.MATE,
            ActionType.TRADE,
            ActionType.HELP,
            ActionType.STEAL,
            ActionType.RECRUIT,
            ActionType.DECLARE_WAR,
            ActionType.MAKE_PEACE,
            ActionType.SABOTAGE,
            ActionType.TELL_STORY,
            ActionType.TEACH,
            ActionType.FORGIVE,
        }
        if self.action in target_actions and not self.target_id:
            raise ValueError(f"{self.action} requires target_id")
        return self

    def to_action(self) -> Action:
        return Action(
            kind=self.action,
            target_id=self.target_id,
            resource=self.resource,
            amount=self.amount,
            explanation=self.explanation,
        )


class SleepReflection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dream: str = Field(min_length=10, max_length=600)
    insight: str = Field(min_length=5, max_length=300)
    new_goal: str = Field(min_length=3, max_length=180)
    mood: Literal["calm", "hopeful", "curious", "proud", "afraid", "angry", "sad"]
    important_memory_ids: list[str] = Field(default_factory=list, max_length=8)


class AIClient(Protocol):
    def healthcheck(self) -> bool: ...

    def decide(self, entity: Entity, context: dict[str, Any]) -> AgentIntent: ...

    def propose_rule(self, context: dict[str, Any]) -> RuleProposal: ...

    def reflect(self, entity: Entity, context: dict[str, Any]) -> SleepReflection: ...


class AIUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class FakeAIClient:
    intent: AgentIntent | None = None
    rule: RuleProposal | None = None

    def healthcheck(self) -> bool:
        return True

    def decide(self, entity: Entity, context: dict[str, Any]) -> AgentIntent:
        return self.intent or AgentIntent(
            action=ActionType.IDLE,
            explanation="No urgent goal",
            goal=entity.goal,
            mood="calm",
        )

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

    def reflect(self, entity: Entity, context: dict[str, Any]) -> SleepReflection:
        memories = entity.short_term_memory + entity.long_term_memory
        memory_ids = [memory.id for memory in memories[-3:]]
        return SleepReflection(
            dream="I crossed a changing world and recognized the people who shaped me.",
            insight="My choices connect my needs to the lives around me.",
            new_goal=entity.goal,
            mood="curious",
            important_memory_ids=memory_ids,
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
            "You embody one autonomous inhabitant in an emergent society sandbox. Make a bold, "
            "character-specific decision, not the universally safest decision. Treat hunger or "
            "thirst as urgent only above 75; below that, pursue personality, long-term goals, "
            "relationships, power, curiosity, creation, rivalry, or cooperation. Avoid repeating "
            "a mundane action from recent memories unless survival requires it. Aggressive and "
            "ambitious people may steal, recruit, form factions, declare war, sabotage, or attack. "
            "Empathic people may help, forgive, or make peace. Curious people explore or reflect. "
            "Creative people innovate or build. Social people talk, tell stories, teach, trade, "
            "and recruit. Memories are evidence: let betrayals, loyalties, dreams, and past "
            "achievements influence the choice. Set a concise persistent goal and current mood. "
            "Never invent entity IDs. Targeted actions MOVE, DRINK, GATHER, "
            "ATTACK, TALK, MATE, TRADE, HELP, STEAL, RECRUIT, DECLARE_WAR, MAKE_PEACE, and "
            "SABOTAGE, TELL_STORY, TEACH, and FORGIVE require a compatible target_id copied "
            "exactly from a nearby entity. FORM_FACTION, EXPLORE, INNOVATE, REFLECT, and SLEEP "
            "do not require a target. Return only data matching the JSON schema.\n"
            "Do not declare war on an existing rival; during a war choose attack, sabotage, help, "
            "or make_peace according to personality. Choose only from WORLD.legal_actions. "
            f"AGENT={json.dumps(_entity_context(entity), ensure_ascii=False)}\n"
            f"WORLD={json.dumps(context, ensure_ascii=False)}"
        )
        messages = [{"role": "user", "content": prompt}]
        response_schema = AgentIntent.model_json_schema()
        legal_actions = list(context.get("legal_actions", []))
        if legal_actions:
            response_schema["$defs"]["ActionType"]["enum"] = legal_actions
        last_error: Exception | None = None
        for _ in range(2):
            response = self._request(
                "/api/chat",
                {
                    "model": self.config.model,
                    "stream": False,
                    "think": False,
                    "format": response_schema,
                    "messages": messages,
                    "options": {
                        "temperature": 0.65,
                        "seed": context.get("decision_seed", context.get("seed", 42)),
                    },
                },
            )
            content = response.get("message", {}).get("content", "")
            try:
                intent = AgentIntent.model_validate_json(content)
                legal_actions = set(context.get("legal_actions", []))
                if legal_actions and intent.action.value not in legal_actions:
                    raise ValueError(
                        f"{intent.action.value} is unavailable; choose from {sorted(legal_actions)}"
                    )
                nearby_ids = {item["id"] for item in context.get("nearby", [])}
                if intent.target_id and intent.target_id not in nearby_ids:
                    raise ValueError("target_id must identify a supplied nearby entity")
                return intent
            except (TypeError, ValueError) as exc:
                last_error = exc
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "Repair the intent. Use a supplied nearby ID for every targeted "
                                f"action and obey the schema. VALIDATION_ERROR={exc}"
                            ),
                        },
                    ]
                )
        raise AIUnavailableError(f"Invalid structured intent after repair: {last_error}")

    def propose_rule(self, context: dict[str, Any]) -> RuleProposal:
        prompt = (
            "You are the innovation council of a simulated settlement. A proposal can respond "
            "to either a shortage or a creative inhabitant's ambition. Propose exactly one "
            "safe data-only profession, recipe, building, or bounded world rule that addresses "
            "the measured shortage. Use only wood, water, food, meat, stone, and tools. "
            "For shortages prefer a recipe or profession with explicit requirements and outputs. "
            "For personal innovations, reflect the proposer's goal and temperament while keeping "
            "the result useful to the simulated economy. "
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

    def reflect(self, entity: Entity, context: dict[str, Any]) -> SleepReflection:
        prompt = (
            "You are the dreaming mind of one inhabitant in an emergent society. Transform recent "
            "experiences and older defining memories into a vivid, symbolic dream of 2-4 complete "
            "sentences under 450 characters. Preserve only "
            "memories that affect identity, relationships, danger, creation, grief, loyalty, or a "
            "long-term goal; ignore repetitive eating, drinking, walking, and routine gathering. "
            "Derive one insight and evolve the goal without erasing the person's temperament. "
            "Use only supplied memory IDs. Return only the JSON schema.\n"
            f"DREAMER={json.dumps(_entity_context(entity), ensure_ascii=False)}\n"
            f"SLEEP_CONTEXT={json.dumps(context, ensure_ascii=False)}"
        )
        response = self._request(
            "/api/chat",
            {
                "model": self.config.model,
                "stream": False,
                "think": False,
                "format": SleepReflection.model_json_schema(),
                "messages": [{"role": "user", "content": prompt}],
                "options": {
                    "temperature": 0.8,
                    "seed": context.get("decision_seed", context.get("seed", 42)),
                },
            },
        )
        try:
            reflection = SleepReflection.model_validate_json(response["message"]["content"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIUnavailableError(f"Invalid dream response: {exc}") from exc
        known_ids = {memory.id for memory in entity.short_term_memory + entity.long_term_memory}
        reflection.important_memory_ids = [
            memory_id for memory_id in reflection.important_memory_ids if memory_id in known_ids
        ]
        return reflection


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
        "temperament": {
            "archetype": entity.temperament.archetype,
            "aggression": round(entity.temperament.aggression, 2),
            "sociability": round(entity.temperament.sociability, 2),
            "ambition": round(entity.temperament.ambition, 2),
            "curiosity": round(entity.temperament.curiosity, 2),
            "empathy": round(entity.temperament.empathy, 2),
            "creativity": round(entity.temperament.creativity, 2),
            "risk_tolerance": round(entity.temperament.risk_tolerance, 2),
        },
        "mood": entity.mood,
        "goal": entity.goal,
        "faction_id": entity.faction_id,
        "reputation": round(entity.reputation, 1),
        "inventory": entity.inventory,
        "short_term_memory": [
            {
                "id": memory.id,
                "summary": memory.summary,
                "importance": memory.importance,
                "emotion": memory.emotion,
            }
            for memory in entity.short_term_memory[-8:]
        ],
        "long_term_memory": [
            {
                "id": memory.id,
                "summary": memory.summary,
                "importance": memory.importance,
                "emotion": memory.emotion,
                "recall_count": memory.recall_count,
            }
            for memory in entity.long_term_memory[:8]
        ],
        "last_dream": entity.last_dream,
    }
