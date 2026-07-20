from __future__ import annotations

from game_of_life.engine import Simulation
from game_of_life.persistence import WorldStore


def test_snapshot_round_trip_preserves_continuation(empty_config, tmp_path) -> None:
    original = Simulation(empty_config)
    original.spawn_human()
    for _ in range(30):
        original.step()

    with WorldStore(tmp_path / "world.db") as store:
        store.save_snapshot(original)
        restored = store.load_latest(empty_config)

    assert restored is not None
    assert restored.state.to_dict() == original.state.to_dict()
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
