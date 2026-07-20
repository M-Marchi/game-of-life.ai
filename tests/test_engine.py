from __future__ import annotations

from game_of_life.engine import Simulation
from game_of_life.models import Action, ActionType, EntityKind, Position


def test_same_seed_produces_same_world(empty_config) -> None:
    first = Simulation(empty_config)
    second = Simulation(empty_config)
    for simulation in (first, second):
        simulation.spawn_resource(EntityKind.TREE)
        simulation.spawn_resource(EntityKind.LAKE)
        simulation.spawn_human()
        simulation.spawn_cow()
        for _ in range(250):
            simulation.step()
    assert first.state.to_dict() == second.state.to_dict()


def test_eating_consumes_inventory(empty_config) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human()
    human.hunger = 80
    human.inventory["food"] = 1

    simulation.step()

    assert human.inventory["food"] == 0
    assert human.hunger < 50


def test_reproduction_creates_exactly_one_child(empty_config) -> None:
    simulation = Simulation(empty_config)
    first = simulation.spawn_human(position=Position(100, 100), gender="male")
    second = simulation.spawn_human(position=Position(104, 100), gender="female")
    first.reproduction_drive = second.reproduction_drive = 100
    first.relationships[second.id] = 20
    second.relationships[first.id] = 20

    simulation.step()

    humans = simulation.state.living(EntityKind.HUMAN)
    assert len(humans) == 3
    assert len([event for event in simulation.events if event.event_type == "reproduction"]) == 1


def test_attack_kills_cow_and_produces_meat(empty_config) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human(position=Position(100, 100))
    cow = simulation.spawn_cow(position=Position(103, 100))
    human.attack = 20
    cow.health = 5
    human.action = Action(ActionType.ATTACK, cow.id)

    simulation._resolve(human)

    assert not cow.alive
    assert human.inventory["meat"] == 8


def test_attack_is_a_single_strike_instead_of_a_locked_massacre(empty_config) -> None:
    simulation = Simulation(empty_config)
    attacker = simulation.spawn_human(position=Position(100, 100))
    target = simulation.spawn_human(position=Position(103, 100))
    attacker.attack = 12
    attacker.action = Action(ActionType.ATTACK, target.id)
    attacker.decision_lock_ticks = 90

    simulation._resolve(attacker)
    attacks_after_strike = len(
        [event for event in simulation.events if event.event_type == "attack"]
    )
    simulation.step()

    assert attacker.decision_lock_ticks == 0
    assert len([event for event in simulation.events if event.event_type == "attack"]) == (
        attacks_after_strike
    )


def test_peaceful_agent_cannot_attack_a_stranger(empty_config) -> None:
    simulation = Simulation(empty_config)
    actor = simulation.spawn_human(position=Position(100, 100))
    stranger = simulation.spawn_human(position=Position(103, 100))
    actor.temperament.aggression = 0.4
    actor.temperament.empathy = 0.7

    assert ActionType.ATTACK.value not in simulation._legal_actions_for(actor, [stranger])
    assert (
        simulation._validate_action(actor, Action(ActionType.ATTACK, stranger.id), stranger)
        is not None
    )

    actor.relationships[stranger.id] = -30
    assert ActionType.ATTACK.value in simulation._legal_actions_for(actor, [stranger])
    assert (
        simulation._validate_action(actor, Action(ActionType.ATTACK, stranger.id), stranger) is None
    )


def test_hostile_ai_intent_is_rejected_for_a_peaceful_stranger(empty_config) -> None:
    from game_of_life.ai.client import AgentIntent
    from game_of_life.ai.scheduler import DecisionResult

    class ResultQueue:
        pending_count = 0

        @staticmethod
        def drain_reflections():
            return []

        def drain(self):
            results = list(self.results)
            self.results.clear()
            return results

    worker = ResultQueue()
    simulation = Simulation(empty_config, ai_worker=worker)
    actor = simulation.spawn_human(position=Position(100, 100))
    stranger = simulation.spawn_human(position=Position(103, 100))
    actor.temperament.aggression = 0.4
    actor.temperament.empathy = 0.8
    worker.results = [
        DecisionResult(
            actor.id,
            AgentIntent(
                action=ActionType.ATTACK,
                target_id=stranger.id,
                explanation="I attack a stranger without a reason.",
                goal="cause chaos",
                mood="angry",
            ),
        )
    ]

    simulation._apply_ai_results()

    assert actor.action.kind != ActionType.ATTACK
    assert any(event.event_type == "ai_rejected" for event in simulation.events)


def test_urgent_need_interrupts_an_ai_decision_lock(empty_config) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human(position=Position(100, 100))
    human.action = Action(ActionType.IDLE, explanation="AI asked me to wait")
    human.decision_lock_ticks = 90
    human.hunger = 80
    human.inventory["food"] = 1

    simulation.step()

    assert human.inventory["food"] == 0
    assert human.hunger < 55
    assert human.decision_lock_ticks == 0


def test_exhausted_cow_rests_without_dreaming(empty_config) -> None:
    empty_config.sleep_duration_ticks = 2
    simulation = Simulation(empty_config)
    cow = simulation.spawn_cow()
    cow.energy = 20

    simulation.step()
    simulation.step()
    simulation.step()

    assert cow.alive
    assert cow.energy >= 92
    assert not cow.dreams
    assert any(event.event_type == "woke_up" for event in simulation.events)


def test_death_is_idempotent(empty_config) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human()

    simulation._kill(human)
    simulation._kill(human)

    assert len([event for event in simulation.events if event.event_type == "death"]) == 1


def test_death_event_records_the_cause(empty_config) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human()
    human.health = 0.1
    human.thirst = 110

    simulation._update_needs(human)

    death = next(event for event in simulation.events if event.event_type == "death")
    assert death.target_id == human.id
    assert death.payload["cause"] == "dehydration"


def test_building_consumes_resources_and_has_owner(empty_config) -> None:
    simulation = Simulation(empty_config)
    builder = simulation.spawn_human(position=Position(100, 100))
    builder.inventory = {"wood": 10, "stone": 3}
    builder.action = Action(ActionType.BUILD, resource="house")

    simulation._resolve(builder)

    buildings = [
        item for item in simulation.state.entities.values() if item.kind == EntityKind.BUILDING
    ]
    assert len(buildings) == 1
    assert buildings[0].owner_id == builder.id
    assert builder.home_id == buildings[0].id
    assert builder.inventory == {"wood": 0, "stone": 0}


def test_generated_recipe_changes_world_without_code(empty_config) -> None:
    simulation = Simulation(empty_config)
    worker = simulation.spawn_human()
    worker.profession = "toolmaker"
    worker.inventory = {"wood": 2, "stone": 1}
    simulation.state.active_rules["toolmaker"] = {
        "id": "toolmaker",
        "category": "profession",
        "name": "Toolmaker",
        "requirements": {"wood": 2, "stone": 1},
        "outputs": {"tools": 1},
        "duration_ticks": 10,
    }

    action = simulation._choose_dynamic_work(worker)
    assert action is not None
    worker.action = action
    simulation._resolve(worker)

    assert worker.inventory == {"wood": 0, "stone": 0, "tools": 1}
