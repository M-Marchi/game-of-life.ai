from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from game_of_life.ai.client import AgentIntent, OllamaAIClient
from game_of_life.config import AIConfig
from game_of_life.models import ActionType


def test_talk_intent_requires_target() -> None:
    with pytest.raises(ValidationError):
        AgentIntent(action=ActionType.TALK, explanation="I want to talk")


def test_empty_target_is_normalized_for_non_targeted_action() -> None:
    intent = AgentIntent(
        action=ActionType.STUDY,
        target_id="",
        explanation="I want to learn.",
        goal="understand the world",
        mood="curious",
    )

    assert intent.target_id is None


def test_generated_rule_repairs_invalid_first_response(monkeypatch) -> None:
    client = OllamaAIClient(AIConfig())
    responses = iter(
        [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "id": "toolmaker",
                            "category": "profession",
                            "name": "Toolmaker",
                            "description": "Makes tools for the settlement.",
                            "requirements": {"wood": 2, "stone": 1},
                            "outputs": {"tools": 1},
                            "effects": {"invented_effect": 1},
                            "activation_reason": "The settlement needs tools.",
                        }
                    )
                }
            },
            {
                "message": {
                    "content": json.dumps(
                        {
                            "id": "toolmaker",
                            "category": "profession",
                            "name": "Toolmaker",
                            "description": "Makes tools for the settlement.",
                            "requirements": {"wood": 2, "stone": 1},
                            "outputs": {"tools": 1},
                            "effects": {},
                            "activation_reason": "The settlement needs tools.",
                        }
                    )
                }
            },
        ]
    )
    monkeypatch.setattr(client, "_request", lambda *_args, **_kwargs: next(responses))

    proposal = client.propose_rule({"seed": 42, "shortage": {"resource": "tools"}})

    assert proposal.id == "toolmaker"
    assert proposal.effects == {}


def test_decision_schema_is_restricted_to_context_actions(monkeypatch) -> None:
    client = OllamaAIClient(AIConfig())
    captured_payloads = []

    def respond(_path, payload):
        captured_payloads.append(payload)
        return {
            "message": {
                "content": json.dumps(
                    {
                        "action": "explore",
                        "target_id": None,
                        "resource": None,
                        "amount": 1,
                        "explanation": "I want to see the world.",
                        "goal": "discover an unknown place",
                        "mood": "curious",
                    }
                )
            }
        }

    monkeypatch.setattr(client, "_request", respond)
    context = {
        "seed": 42,
        "legal_actions": ["idle", "explore"],
        "nearby": [],
    }

    intent = client.decide(_human(), context)

    assert intent.action == ActionType.EXPLORE
    assert captured_payloads[0]["format"]["$defs"]["ActionType"]["enum"] == [
        "idle",
        "explore",
    ]


def test_dream_keeps_only_supplied_memory_ids(monkeypatch) -> None:
    client = OllamaAIClient(AIConfig())
    human = _human()
    known = human.remember("I protected Ada", tick=4, importance=0.9, emotion="hopeful")
    monkeypatch.setattr(
        client,
        "_request",
        lambda *_args, **_kwargs: {
            "message": {
                "content": json.dumps(
                    {
                        "dream": "A lantern carried Ada safely through a black forest.",
                        "insight": "Loyalty gives my courage a direction.",
                        "new_goal": "build a refuge for my allies",
                        "mood": "hopeful",
                        "important_memory_ids": [known.id, "invented-memory"],
                    }
                )
            }
        },
    )

    reflection = client.reflect(human, {"seed": 42})

    assert reflection.important_memory_ids == [known.id]


def _human():
    from game_of_life.models import Entity, EntityKind, Position

    return Entity("human-test", EntityKind.HUMAN, Position(10, 10), name="Ada")
