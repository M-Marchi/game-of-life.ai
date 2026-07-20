from __future__ import annotations

from game_of_life.engine import Simulation
from game_of_life.models import Action, ActionType, AgentState, Entity, EntityKind, Position


def test_consolidation_forgets_routine_and_keeps_meaningful_memories() -> None:
    person = Entity("human-1", EntityKind.HUMAN, Position(10, 10))
    person.remember("I walked to a tree", tick=1, importance=0.2)
    person.remember(
        "Ada saved me during the storm",
        tick=2,
        category="relationship",
        importance=0.9,
        emotion="afraid",
        participants=["human-2"],
    )

    retained, forgotten = person.consolidate_memories(3)

    assert (retained, forgotten) == (1, 1)
    assert not person.short_term_memory
    assert [memory.summary for memory in person.long_term_memory] == [
        "Ada saved me during the storm"
    ]


def test_short_term_capacity_evicts_least_salient_memory() -> None:
    person = Entity("human-1", EntityKind.HUMAN, Position(10, 10))
    defining = person.remember("I founded the village", tick=1, importance=1.0, limit=3)
    for tick in range(2, 5):
        person.remember(f"Routine detail {tick}", tick=tick, importance=0.1, limit=3)

    assert len(person.short_term_memory) == 3
    assert defining in person.short_term_memory


def test_sleep_creates_dream_consolidates_and_wakes(empty_config) -> None:
    empty_config.sleep_duration_ticks = 4
    empty_config.dream_start_ticks = 2
    simulation = Simulation(empty_config)
    person = simulation.spawn_human()
    person.remember(
        "I built a shelter before the storm",
        tick=0,
        category="creation",
        importance=0.85,
        emotion="proud",
    )
    person.action = Action(ActionType.SLEEP)
    simulation._resolve(person)

    for _ in range(4):
        simulation._advance_sleep(person)

    assert person.state == AgentState.AWAKE
    assert person.last_dream
    assert person.long_term_memory
    event_types = {event.event_type for event in simulation.events}
    assert {"sleep_started", "memory_consolidated", "dream", "woke_up"} <= event_types


def test_human_population_cap_blocks_birth(empty_config) -> None:
    empty_config.max_humans = 2
    simulation = Simulation(empty_config)
    first = simulation.spawn_human(position=Position(100, 100), gender="male")
    second = simulation.spawn_human(position=Position(104, 100), gender="female")
    first.reproduction_drive = second.reproduction_drive = 100
    first.relationships[second.id] = second.relationships[first.id] = 100

    simulation._mate(first, second)

    assert len(simulation.state.living(EntityKind.HUMAN)) == 2
