from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from game_of_life.config import SimulationConfig
from game_of_life.engine import Simulation
from game_of_life.models import (
    Action,
    ActionType,
    AgentState,
    Entity,
    EntityKind,
    Faction,
    MemoryEntry,
    Position,
    Temperament,
    WorldEvent,
    WorldState,
)

SCHEMA_VERSION = 4


class WorldStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self._pending_events = 0
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                tick INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                rng_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                action TEXT,
                actor_id TEXT,
                target_id TEXT,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);
            CREATE INDEX IF NOT EXISTS idx_events_actor_action ON events(actor_id, action);
            CREATE TABLE IF NOT EXISTS rule_versions (
                rule_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                active INTEGER NOT NULL,
                definition_json TEXT NOT NULL,
                PRIMARY KEY (rule_id, version)
            );
            """
        )
        self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.connection.commit()

    def record_event(self, event: WorldEvent) -> None:
        action = event.payload.get("action")
        if hasattr(action, "value"):
            action = action.value
        self.connection.execute(
            "INSERT INTO events(tick, event_type, action, actor_id, target_id, payload_json) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (
                event.tick,
                event.event_type,
                action,
                event.actor_id,
                event.target_id,
                json.dumps(event.payload, sort_keys=True),
            ),
        )
        self._pending_events += 1
        if event.event_type == "rule_activated" and "definition" in event.payload:
            definition = event.payload["definition"]
            self.save_rule(
                str(event.payload["rule_id"]),
                int(definition["version"]),
                definition,
                active=True,
            )
        elif event.event_type == "rule_rollback":
            self.connection.execute(
                "UPDATE rule_versions SET active = 0 WHERE rule_id = ?",
                (str(event.payload["rule_id"]),),
            )
        if self._pending_events >= 100 or event.event_type.startswith("rule_"):
            self.connection.commit()
            self._pending_events = 0

    def save_snapshot(self, simulation: Simulation) -> None:
        state_json = json.dumps(simulation.state.to_dict(), sort_keys=True)
        rng_json = json.dumps(simulation.random.getstate())
        self.connection.execute(
            "INSERT OR REPLACE INTO snapshots(tick, state_json, rng_json) VALUES(?, ?, ?)",
            (simulation.state.tick, state_json, rng_json),
        )
        self.connection.commit()

    def load_latest(
        self, config: SimulationConfig, *, ai_worker: Any = None, innovation_manager: Any = None
    ) -> Simulation | None:
        row = self.connection.execute(
            "SELECT state_json, rng_json FROM snapshots ORDER BY tick DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        state_data = json.loads(row[0])
        simulation = Simulation(
            config,
            ai_worker=ai_worker,
            innovation_manager=innovation_manager,
            initialize=False,
        )
        simulation.state = _world_from_dict(state_data)
        simulation.random.setstate(_as_tuple(json.loads(row[1])))
        return simulation

    def recent_events(self, limit: int = 100) -> list[WorldEvent]:
        rows = self.connection.execute(
            "SELECT tick, event_type, actor_id, target_id, payload_json "
            "FROM events ORDER BY sequence DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            WorldEvent(row[0], row[1], row[2], row[3], json.loads(row[4])) for row in reversed(rows)
        ]

    def save_rule(
        self, rule_id: str, version: int, definition: dict[str, Any], *, active: bool
    ) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO rule_versions"
            "(rule_id, version, active, definition_json) VALUES(?, ?, ?, ?)",
            (rule_id, version, int(active), json.dumps(definition, sort_keys=True)),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.commit()
        self.connection.close()

    def __enter__(self) -> WorldStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _world_from_dict(data: dict[str, Any]) -> WorldState:
    state = WorldState(
        width=data["width"],
        height=data["height"],
        seed=data["seed"],
        tick=data["tick"],
        next_id=data["next_id"],
        active_rules=data.get("active_rules", {}),
        factions={
            faction_id: Faction(**definition)
            for faction_id, definition in data.get("factions", {}).items()
        },
    )
    for entity_id, item in data["entities"].items():
        item = dict(item)
        item["kind"] = EntityKind(item["kind"])
        item["position"] = Position(**item["position"])
        item["temperament"] = Temperament(**item.get("temperament", {}))
        item["state"] = AgentState(item.get("state", AgentState.AWAKE))
        item["short_term_memory"] = [
            MemoryEntry(**memory) for memory in item.get("short_term_memory", [])
        ]
        item["long_term_memory"] = [
            MemoryEntry(**memory) for memory in item.get("long_term_memory", [])
        ]
        action = item.get("action", {})
        action["kind"] = ActionType(action.get("kind", ActionType.IDLE))
        item["action"] = Action(**action)
        state.entities[entity_id] = Entity(**item)
    return state


def _as_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_as_tuple(item) for item in value)
    return value
