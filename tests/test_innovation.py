from __future__ import annotations

import time

from game_of_life.ai.client import FakeAIClient
from game_of_life.ai.scheduler import AIWorker
from game_of_life.engine import Simulation
from game_of_life.innovation import InnovationManager
from game_of_life.models import Action, ActionType, Position, Profession
from game_of_life.rules import RuleProposal


def test_generated_profession_is_activated_and_used(empty_config) -> None:
    proposal = RuleProposal(
        id="toolmaker",
        category="profession",
        name="Toolmaker",
        description="Makes tools needed by the settlement.",
        requirements={"wood": 2, "stone": 1},
        outputs={"tools": 1},
        duration_ticks=30,
        activation_reason="The settlement has no tools.",
    )
    worker = AIWorker(FakeAIClient(rule=proposal), max_pending=2)
    worker.start()
    manager = InnovationManager(worker, interval_ticks=1)
    simulation = Simulation(empty_config, ai_worker=worker, innovation_manager=manager)
    human = simulation.spawn_human()
    human.profession = Profession.MERCHANT
    human.inventory = {"food": 4, "water": 2, "wood": 5, "stone": 2}

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


def test_generated_human_development_profession_has_real_effect(empty_config) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human()
    human.profession = "story_counselor"
    simulation.state.active_rules["story_counselor"] = RuleProposal(
        id="story_counselor",
        category="profession",
        name="Story counselor",
        description="Uses shared stories to strengthen confidence and understanding.",
        effects={"knowledge_gain": 0.5, "confidence_gain": 2},
        duration_ticks=30,
        activation_reason="People need meaning and emotional support.",
    ).model_dump(mode="json")
    before_confidence = human.confidence

    human.action = Action(ActionType.WORK, resource="story_counselor")
    simulation._resolve(human)

    assert human.knowledge["story_counselor"] == 0.5
    assert human.confidence == before_confidence + 2


def test_composable_profession_impacts_the_person_most_in_need(empty_config) -> None:
    simulation = Simulation(empty_config)
    worker = simulation.spawn_human()
    patient = simulation.spawn_human(position=worker.position)
    patient.health = 40
    worker.profession = "community_medic"
    simulation.state.active_rules["community_medic"] = RuleProposal(
        id="community_medic",
        category="profession",
        name="Community medic",
        description="Finds and treats the person who most needs care.",
        impacts=[
            {"metric": "health", "scope": "most_in_need", "amount": 7, "radius": 40},
            {"metric": "trust", "scope": "nearby", "amount": 2, "radius": 40},
        ],
        duration_ticks=30,
        activation_reason="Someone is hurt and the settlement needs trusted care.",
    ).model_dump(mode="json")

    worker.action = Action(ActionType.WORK, resource="community_medic")
    simulation._resolve(worker)

    assert patient.health == 47
    assert worker.social_bonds[patient.id].trust == 2
    event = next(event for event in simulation.events if event.event_type == "work")
    assert event.payload["impacts"][0]["applied_to"] == [patient.id]
    assert event.payload["impacts"][0]["actual_amount"] == 7


def test_profession_telemetry_ignores_effects_that_change_nothing(empty_config) -> None:
    simulation = Simulation(empty_config)
    worker = simulation.spawn_human()
    neighbor = simulation.spawn_human(position=worker.position)
    neighbor.stress = 0
    worker.profession = "calm_guide"
    simulation.state.active_rules["calm_guide"] = RuleProposal(
        id="calm_guide",
        category="profession",
        name="Calm guide",
        description="Relieves stress for nearby inhabitants.",
        impacts=[{"metric": "stress", "scope": "nearby", "amount": 5}],
        duration_ticks=30,
        activation_reason="The community wants emotional support.",
    ).model_dump(mode="json")

    worker.action = Action(ActionType.WORK, resource="calm_guide")
    simulation._resolve(worker)

    event = next(event for event in simulation.events if event.event_type == "work")
    assert event.payload["impacts"][0]["actual_amount"] == 0
    assert event.payload["impacts"][0]["applied_to"] == []


def test_service_profession_moves_toward_the_person_it_can_help(empty_config) -> None:
    simulation = Simulation(empty_config)
    worker = simulation.spawn_human(position=Position(10, 10))
    patient = simulation.spawn_human(position=Position(200, 200))
    patient.health = 30
    worker.profession = "traveling_medic"
    simulation.state.active_rules["traveling_medic"] = RuleProposal(
        id="traveling_medic",
        category="profession",
        name="Traveling medic",
        description="Travels to inhabitants who need urgent treatment.",
        impacts=[{"metric": "health", "scope": "most_in_need", "amount": 5, "radius": 20}],
        duration_ticks=30,
        activation_reason="Care should reach isolated people.",
    ).model_dump(mode="json")

    action = simulation._choose_dynamic_work(worker)

    assert action is not None
    assert action.kind == ActionType.MOVE
    assert action.target_id == patient.id


def test_multi_impact_profession_chooses_one_primary_beneficiary(empty_config) -> None:
    simulation = Simulation(empty_config)
    worker = simulation.spawn_human(position=Position(10, 10))
    social_target = simulation.spawn_human(position=Position(220, 20))
    stressed_target = simulation.spawn_human(position=Position(20, 200))
    stressed_target.stress = 90
    worker.profession = "community_counselor"
    simulation.state.active_rules["community_counselor"] = RuleProposal(
        id="community_counselor",
        category="profession",
        name="Community counselor",
        description="Offers practical and social support.",
        impacts=[
            {"metric": "trust", "scope": "most_in_need", "amount": 2, "radius": 40},
            {"metric": "stress", "scope": "most_in_need", "amount": 5, "radius": 40},
        ],
        duration_ticks=30,
        activation_reason="People need coordinated care.",
    ).model_dump(mode="json")

    action = simulation._choose_dynamic_work(worker)

    assert social_target.id != stressed_target.id
    assert action is not None
    assert action.kind == ActionType.MOVE
    assert action.target_id == stressed_target.id


def test_settlement_defers_multiple_innovations_within_six_world_hours(empty_config) -> None:
    worker = AIWorker(FakeAIClient(), max_pending=2)
    manager = InnovationManager(worker)
    simulation = Simulation(empty_config, ai_worker=worker, innovation_manager=manager)
    actor = simulation.spawn_human()
    manager._last_activation_tick = 0
    simulation.state.tick = 1

    assert not manager.request_from_actor(simulation, actor)
    event = simulation.events[-1]
    assert event.event_type == "innovation_deferred"
    assert event.actor_id == actor.id
    assert event.payload["available_tick"] == empty_config.ticks_per_day // 4
