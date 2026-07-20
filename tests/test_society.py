from __future__ import annotations

from dataclasses import dataclass

from game_of_life.ai.client import AgentIntent
from game_of_life.ai.scheduler import DecisionResult
from game_of_life.engine import Simulation
from game_of_life.models import Action, ActionType, EntityKind, Position


@dataclass
class ResultWorker:
    results: list[DecisionResult]
    pending_count: int = 0

    def drain(self) -> list[DecisionResult]:
        results, self.results = self.results, []
        return results

    def drain_rules(self) -> list[object]:
        return []

    def submit(self, *_args, **_kwargs) -> bool:
        return False


def test_ai_talk_is_executed_before_local_logic(empty_config) -> None:
    simulation = Simulation(empty_config)
    actor = simulation.spawn_human(position=Position(100, 100))
    target = simulation.spawn_human(position=Position(105, 100))
    intent = AgentIntent(
        action=ActionType.TALK,
        target_id=target.id,
        explanation="I want an ally",
        goal="build a trusted circle",
        mood="hopeful",
    )
    simulation.ai_worker = ResultWorker([DecisionResult(actor.id, intent)])  # type: ignore[assignment]

    simulation.step()

    assert actor.relationships[target.id] > 0
    assert actor.goal == "build a trusted circle"
    assert actor.mood == "hopeful"
    assert any(event.event_type == "talk" for event in simulation.events)


def test_factions_can_recruit_and_declare_war(empty_config) -> None:
    simulation = Simulation(empty_config)
    first = simulation.spawn_human(position=Position(100, 100))
    recruit = simulation.spawn_human(position=Position(104, 100))
    second = simulation.spawn_human(position=Position(110, 100))
    first.reputation = 100
    recruit.relationships[first.id] = 100
    recruit.temperament.sociability = 1

    simulation._form_faction(first)
    simulation._recruit(first, recruit)
    simulation._form_faction(second)
    simulation._declare_war(first, second)

    first_faction = simulation.state.factions[first.faction_id]
    second_faction = simulation.state.factions[second.faction_id]
    assert recruit.faction_id == first.faction_id
    assert second_faction.id in first_faction.rivals
    assert first_faction.id in second_faction.rivals
    assert any(event.event_type == "war_declared" for event in simulation.events)


def test_stealing_creates_real_resource_and_relationship_effects(empty_config) -> None:
    simulation = Simulation(empty_config)
    thief = simulation.spawn_human(position=Position(100, 100))
    victim = simulation.spawn_human(position=Position(103, 100))
    thief.temperament.risk_tolerance = 0
    victim.inventory["food"] = 2

    thief.action = Action(ActionType.STEAL, victim.id)
    simulation._resolve(thief)

    assert thief.inventory["food"] == 1
    assert victim.inventory["food"] == 1
    assert victim.relationships[thief.id] < 0
    assert any(event.event_type == "steal" for event in simulation.events)


def test_world_events_change_the_environment(empty_config) -> None:
    empty_config.world_event_interval_ticks = 1
    simulation = Simulation(empty_config)
    simulation.spawn_resource(EntityKind.TREE)
    simulation.spawn_human()

    simulation.step()

    assert any(event.event_type == "world_event" for event in simulation.events)
