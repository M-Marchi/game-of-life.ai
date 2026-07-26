from __future__ import annotations

from game_of_life.diagnostics import analyze_database, format_report
from game_of_life.engine import Simulation
from game_of_life.models import ActionType
from game_of_life.persistence import WorldStore


def test_diagnostic_report_separates_routine_from_emergent_events(
    empty_config, tmp_path
) -> None:
    path = tmp_path / "diagnostic.db"
    simulation = Simulation(empty_config)
    actor = simulation.spawn_human()
    target = simulation.spawn_human()
    with WorldStore(path) as store:
        simulation.add_event_sink(store.record_event)
        simulation.emit("gather", actor.id, resource="wood")
        simulation.emit("gather", actor.id, resource="wood")
        simulation.emit("ai_thinking", actor.id, goal="understand the forest")
        simulation.emit(
            "ai_decision",
            actor.id,
            action=ActionType.EXPLORE,
            goal="understand the forest",
            explanation="I want to map what lies beyond the settlement.",
            age_ticks=12,
        )
        simulation.emit("talk", actor.id, target.id, topic="freedom")
        simulation.emit(
            "dream",
            actor.id,
            dream="A path became a river of stars.",
            generated_by="qwen3:8b",
        )
        simulation.emit(
            "work",
            actor.id,
            rule_id="forest_listener",
            impacts=[{"metric": "trust", "actual_amount": 2.5}],
        )

    report = analyze_database(path)

    assert report["integrity"] == "ok"
    assert report["storage"]["routine_actions_aggregated"] == 2
    assert report["storage"]["routine_rows"] == 1
    assert report["ai"]["valid_decisions"] == 1
    assert report["emergence"]["conversations"] == 1
    assert report["emergence"]["qwen_dreams"] == 1
    assert report["emergence"]["real_impact_total"] == 2.5
    assert "eventi narrativi" in format_report(report)
