from __future__ import annotations

import json

from game_of_life.ai.client import OllamaAIClient
from game_of_life.config import AIConfig


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
