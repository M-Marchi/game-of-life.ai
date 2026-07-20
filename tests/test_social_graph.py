from __future__ import annotations

from game_of_life.engine import Simulation
from game_of_life.models import Position, SocialBond
from game_of_life.persistence import WorldStore


def test_social_bond_classifies_love_hate_and_family() -> None:
    assert SocialBond("person-b", affinity=50, trust=45, attraction=70).label == "love"
    assert SocialBond("person-b", affinity=-60, fear=80).label == "hate"
    assert SocialBond("person-b", roles=["sibling"]).label == "family"


def test_conversation_creates_a_bidirectional_acquaintance(empty_config) -> None:
    simulation = Simulation(empty_config)
    actor = simulation.spawn_human(position=Position(80, 80))
    target = simulation.spawn_human(position=Position(82, 80))

    simulation._talk(actor, target)

    assert actor.social_bonds[target.id].label == "acquaintance"
    assert target.social_bonds[actor.id].label == "acquaintance"
    edges = simulation.social_graph()["edges"]
    assert {(edge["source"], edge["target"]) for edge in edges} == {
        (actor.id, target.id),
        (target.id, actor.id),
    }
    assert all(edge["interaction_count"] == 1 for edge in edges)


def test_returned_affection_can_create_love(empty_config) -> None:
    simulation = Simulation(empty_config)
    actor = simulation.spawn_human(position=Position(80, 80))
    target = simulation.spawn_human(position=Position(82, 80))
    simulation._update_bond(
        actor,
        target,
        affinity=40,
        trust=50,
        attraction=60,
        event="grew close",
    )
    simulation._update_bond(
        target,
        actor,
        affinity=40,
        trust=50,
        attraction=60,
        event="grew close",
    )
    events = []
    simulation.add_event_sink(events.append)
    simulation.random.seed(1)

    simulation._express_affection(actor, target)

    assert actor.social_bonds[target.id].label == "love"
    assert target.social_bonds[actor.id].label == "love"
    assert any(event.event_type == "affection" and event.payload["accepted"] for event in events)


def test_social_graph_history_is_directly_queryable(empty_config, tmp_path) -> None:
    simulation = Simulation(empty_config)
    actor = simulation.spawn_human(position=Position(80, 80))
    target = simulation.spawn_human(position=Position(82, 80))
    simulation._talk(actor, target)

    with WorldStore(tmp_path / "world.db") as store:
        store.save_mental_states(simulation)
        simulation.state.tick = 120
        actor.action_cooldown = 0
        simulation._talk(actor, target)
        store.save_mental_states(simulation)
        history = store.social_history(actor.id, target.id)
        row = store.connection.execute(
            "SELECT relationship, affinity, trust, familiarity, interaction_count "
            "FROM social_edges WHERE source_id = ? AND target_id = ? AND tick = 120",
            (actor.id, target.id),
        ).fetchone()

    assert [edge["tick"] for edge in history] == [0, 120]
    assert row is not None
    assert row[0] == "acquaintance"
    assert row[4] == 2
