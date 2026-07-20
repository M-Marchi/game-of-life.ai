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


def test_death_is_idempotent(empty_config) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human()

    simulation._kill(human)
    simulation._kill(human)

    assert len([event for event in simulation.events if event.event_type == "death"]) == 1


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
