from __future__ import annotations

from game_of_life.engine import Simulation
from game_of_life.models import ActionType
from game_of_life.persistence import WorldStore


def test_snapshot_round_trip_preserves_continuation(empty_config, tmp_path) -> None:
    original = Simulation(empty_config)
    founder = original.spawn_human()
    original._form_faction(founder)
    founder.remember(
        "I promised to protect this settlement",
        tick=original.state.tick,
        category="identity",
        importance=0.9,
        emotion="hopeful",
    )
    for _ in range(30):
        original.step()

    with WorldStore(tmp_path / "world.db") as store:
        store.save_snapshot(original)
        restored = store.load_latest(empty_config)

    assert restored is not None
    assert restored.state.to_dict() == original.state.to_dict()
    restored_founder = restored.state.entities[founder.id]
    assert restored_founder.temperament.archetype == founder.temperament.archetype
    assert restored.state.factions[founder.faction_id].leader_id == founder.id
    original.step()
    restored.step()
    assert restored.state.to_dict() == original.state.to_dict()


def test_event_log_records_payload(empty_config, tmp_path) -> None:
    simulation = Simulation(empty_config)
    with WorldStore(tmp_path / "world.db") as store:
        simulation.add_event_sink(store.record_event)
        human = simulation.spawn_human()
        simulation.emit("custom", human.id, value=3)
        events = store.recent_events()

    assert events[-1].event_type == "custom"
    assert events[-1].payload == {"value": 3}


def test_ai_action_and_target_are_directly_queryable(empty_config, tmp_path) -> None:
    simulation = Simulation(empty_config)
    with WorldStore(tmp_path / "world.db") as store:
        simulation.add_event_sink(store.record_event)
        actor = simulation.spawn_human()
        target = simulation.spawn_human()
        simulation.emit(
            "ai_decision",
            actor.id,
            target.id,
            action=ActionType.TALK,
            explanation="Starting a conversation",
        )
        row = store.connection.execute(
            "SELECT action, actor_id, target_id FROM events WHERE action = 'talk'"
        ).fetchone()

    assert row == ("talk", actor.id, target.id)


def test_mental_history_preserves_identity_and_memories(empty_config, tmp_path) -> None:
    simulation = Simulation(empty_config)
    human = simulation.spawn_human()
    human.remember(
        "I discovered what kind of person I want to become",
        tick=0,
        category="identity",
        importance=0.9,
        emotion="hopeful",
    )
    human.consolidate_memories(0)
    human.last_dream = "A door opened onto a library."
    human.dreams.append(human.last_dream)

    with WorldStore(tmp_path / "world.db") as store:
        store.save_mental_states(simulation)
        human.stress = 42
        human.goal = "study the history of my community"
        simulation.state.tick = 120
        store.save_mental_states(simulation)
        history = store.mental_history(human.id)
        row = store.connection.execute(
            "SELECT profession, mood, goal, self_awareness, stress "
            "FROM mental_states WHERE entity_id = ? AND tick = 120",
            (human.id,),
        ).fetchone()

    assert [state["tick"] for state in history] == [0, 120]
    assert history[0]["long_term_memory"][0]["category"] == "identity"
    assert history[0]["dreams"] == ["A door opened onto a library."]
    assert history[1]["stress"] == 42
    assert row == (
        str(human.profession),
        human.mood,
        "study the history of my community",
        human.self_awareness,
        42,
    )


def test_mental_states_are_sampled_at_configured_interval(empty_config, tmp_path) -> None:
    from game_of_life.main import _run_headless

    empty_config.mental_snapshot_interval_ticks = 2
    simulation = Simulation(empty_config)
    simulation.spawn_human()
    with WorldStore(tmp_path / "world.db") as store:
        store.save_mental_states(simulation)
        _run_headless(simulation, 5, store)
        store.save_mental_states(simulation)
        ticks = [
            row[0]
            for row in store.connection.execute(
                "SELECT DISTINCT tick FROM mental_states ORDER BY tick"
            )
        ]

    assert ticks == [0, 2, 4, 5]
