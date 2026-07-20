from __future__ import annotations

import time

from game_of_life.ai.client import FakeAIClient
from game_of_life.ai.scheduler import AIWorker
from game_of_life.engine import Simulation
from game_of_life.innovation import InnovationManager
from game_of_life.models import Profession
from game_of_life.rules import RuleProposal


def test_generated_profession_is_activated_and_used(empty_config) -> None:
    proposal = RuleProposal(
        id="toolmaker",
        category="profession",
        name="Toolmaker",
        description="Makes tools needed by the settlement.",
        requirements={"wood": 2, "stone": 1},
        outputs={"tools": 1},
        duration_ticks=10,
        activation_reason="The settlement has no tools.",
    )
    worker = AIWorker(FakeAIClient(rule=proposal), max_pending=2)
    worker.start()
    manager = InnovationManager(worker, interval_ticks=1)
    simulation = Simulation(empty_config, ai_worker=worker, innovation_manager=manager)
    human = simulation.spawn_human()
    human.profession = Profession.MERCHANT
    human.inventory = {"wood": 2, "stone": 1}

    try:
        for _ in range(50):
            simulation.step()
            if proposal.id in simulation.state.active_rules:
                break
            time.sleep(0.005)
        assert proposal.id in simulation.state.active_rules
        assert human.profession == proposal.id

        simulation.step()
        assert human.inventory.get("tools", 0) == 1
        assert any(event.event_type == "rule_activated" for event in simulation.events)
    finally:
        worker.stop()
