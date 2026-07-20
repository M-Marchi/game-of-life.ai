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
