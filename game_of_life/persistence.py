from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
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
    SocialBond,
    Temperament,
    WorldEvent,
    WorldState,
)

SCHEMA_VERSION = 9
ROUTINE_EVENT_TYPES = {
    "eat",
    "drink",
    "gather",
    "study",
    "sleep_started",
    "woke_up",
    "temperament_changed",
}


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
                run_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                rng_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, tick)
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                action TEXT,
                actor_id TEXT,
                target_id TEXT,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_action ON events(run_id, action);
            CREATE INDEX IF NOT EXISTS idx_events_actor_action
                ON events(run_id, actor_id, action);
            CREATE TABLE IF NOT EXISTS mental_states (
                run_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                entity_id TEXT NOT NULL,
                name TEXT NOT NULL,
                profession TEXT NOT NULL,
                mood TEXT NOT NULL,
                goal TEXT NOT NULL,
                self_awareness REAL NOT NULL,
                stress REAL NOT NULL,
                mental_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, entity_id, tick)
            );
            CREATE INDEX IF NOT EXISTS idx_mental_states_tick ON mental_states(run_id, tick);
            CREATE INDEX IF NOT EXISTS idx_mental_states_profession
                ON mental_states(run_id, profession, tick);
            CREATE TABLE IF NOT EXISTS social_edges (
                run_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relationship TEXT NOT NULL,
                affinity REAL NOT NULL,
                trust REAL NOT NULL,
                attraction REAL NOT NULL,
                respect REAL NOT NULL,
                fear REAL NOT NULL,
                familiarity REAL NOT NULL,
                interaction_count INTEGER NOT NULL,
                last_interaction_tick INTEGER NOT NULL,
                roles_json TEXT NOT NULL,
                edge_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, source_id, target_id, tick)
            );
            CREATE INDEX IF NOT EXISTS idx_social_edges_tick ON social_edges(run_id, tick);
            CREATE INDEX IF NOT EXISTS idx_social_edges_relationship
                ON social_edges(run_id, relationship, tick);
            CREATE INDEX IF NOT EXISTS idx_social_edges_target
                ON social_edges(run_id, target_id, tick);
            CREATE TABLE IF NOT EXISTS rule_versions (
                run_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                active INTEGER NOT NULL,
                definition_json TEXT NOT NULL,
                PRIMARY KEY (run_id, rule_id, version)
            );
            CREATE TABLE IF NOT EXISTS routine_activity (
                run_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                entity_id TEXT NOT NULL,
                activity TEXT NOT NULL,
                detail TEXT NOT NULL,
                count INTEGER NOT NULL,
                first_tick INTEGER NOT NULL,
                last_tick INTEGER NOT NULL,
                last_payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, day, entity_id, activity, detail)
            );
            CREATE INDEX IF NOT EXISTS idx_routine_activity_day
                ON routine_activity(run_id, day, activity);
            """
        )
        self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        row = self.connection.execute(
            "SELECT value FROM metadata WHERE key = 'current_run_id'"
        ).fetchone()
        self.run_id = str(row[0]) if row else self._new_run_id()
        if not row:
            self.connection.execute(
                "INSERT INTO metadata(key, value) VALUES('current_run_id', ?)",
                (self.run_id,),
            )
        self.connection.commit()

    @staticmethod
    def _new_run_id() -> str:
        return f"run-{uuid.uuid4().hex[:12]}"

    @classmethod
    def recreate(cls, path: str | Path) -> None:
        database_path = Path(path)
        for candidate in (
            database_path,
            Path(f"{database_path}-wal"),
            Path(f"{database_path}-shm"),
        ):
            candidate.unlink(missing_ok=True)

    def record_event(self, event: WorldEvent) -> None:
        if event.event_type in ROUTINE_EVENT_TYPES:
            self._record_routine_activity(event)
            return
        action = event.payload.get("action")
        if hasattr(action, "value"):
            action = action.value
        self.connection.execute(
            "INSERT INTO events("
            "run_id, tick, event_type, action, actor_id, target_id, payload_json) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (
                self.run_id,
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
                "UPDATE rule_versions SET active = 0 WHERE run_id = ? AND rule_id = ?",
                (self.run_id, str(event.payload["rule_id"])),
            )
        if self._pending_events >= 100 or event.event_type.startswith("rule_"):
            self.connection.commit()
            self._pending_events = 0

    def _record_routine_activity(self, event: WorldEvent) -> None:
        detail_value = (
            event.payload.get("resource")
            or event.payload.get("field")
            or event.payload.get("rest_type")
            or event.payload.get("source")
            or ""
        )
        self.connection.execute(
            "INSERT INTO routine_activity("
            "run_id, day, entity_id, activity, detail, count, first_tick, last_tick, "
            "last_payload_json) VALUES(?, ?, ?, ?, ?, 1, ?, ?, ?) "
            "ON CONFLICT(run_id, day, entity_id, activity, detail) DO UPDATE SET "
            "count = count + 1, last_tick = excluded.last_tick, "
            "last_payload_json = excluded.last_payload_json",
            (
                self.run_id,
                int(event.payload.get("day", 1)),
                event.actor_id or "world",
                event.event_type,
                str(detail_value),
                event.tick,
                event.tick,
                json.dumps(event.payload, sort_keys=True),
            ),
        )
        self._pending_events += 1
        if self._pending_events >= 100:
            self.connection.commit()
            self._pending_events = 0

    def save_snapshot(self, simulation: Simulation) -> None:
        state_json = json.dumps(simulation.state.to_dict(), sort_keys=True)
        rng_json = json.dumps(simulation.random.getstate())
        self.connection.execute(
            "INSERT OR REPLACE INTO snapshots(run_id, tick, state_json, rng_json) "
            "VALUES(?, ?, ?, ?)",
            (self.run_id, simulation.state.tick, state_json, rng_json),
        )
        self.connection.commit()

    def save_mental_states(self, simulation: Simulation) -> None:
        rows = []
        for human in simulation.state.living(EntityKind.HUMAN):
            mental_state = {
                "tick": simulation.state.tick,
                "world_time": simulation.world_time(),
                "entity_id": human.id,
                "name": human.name,
                "age_years": round(human.age_years, 4),
                "state": human.state,
                "mood": human.mood,
                "goal": human.goal,
                "aspirations": human.aspirations,
                "profession": str(human.profession),
                "profession_satisfaction": round(human.profession_satisfaction, 3),
                "temperament": asdict(human.temperament),
                "values": human.values,
                "self_awareness": round(human.self_awareness, 3),
                "growth_drive": round(human.growth_drive, 3),
                "confidence": round(human.confidence, 3),
                "stress": round(human.stress, 3),
                "aesthetic_need": round(human.aesthetic_need, 3),
                "appearance": {
                    "style": human.appearance_style,
                    "hue": human.appearance_hue,
                    "accessory": human.accessory,
                },
                "knowledge": human.knowledge,
                "skills": human.skills,
                "relationships": human.relationships,
                "social_bonds": {
                    target_id: {**asdict(bond), "relationship": bond.label}
                    for target_id, bond in human.social_bonds.items()
                },
                "needs": {
                    "health": round(human.health, 3),
                    "hunger": round(human.hunger, 3),
                    "thirst": round(human.thirst, 3),
                    "energy": round(human.energy, 3),
                    "social": round(human.social, 3),
                },
                "current_action": asdict(human.action),
                "short_term_memory": [asdict(memory) for memory in human.short_term_memory],
                "long_term_memory": [asdict(memory) for memory in human.long_term_memory],
                "dreams": human.dreams,
                "last_dream": human.last_dream,
            }
            rows.append(
                (
                    self.run_id,
                    simulation.state.tick,
                    human.id,
                    human.name,
                    str(human.profession),
                    human.mood,
                    human.goal,
                    human.self_awareness,
                    human.stress,
                    json.dumps(mental_state, sort_keys=True),
                )
            )
        self.connection.executemany(
            "INSERT OR REPLACE INTO mental_states("
            "run_id, tick, entity_id, name, profession, mood, goal, self_awareness, stress, "
            "mental_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.save_social_graph(simulation, commit=False)
        self.connection.commit()

    def save_social_graph(self, simulation: Simulation, *, commit: bool = True) -> None:
        graph = simulation.social_graph()
        rows = [
            (
                self.run_id,
                simulation.state.tick,
                edge["source"],
                edge["target"],
                edge["relationship"],
                edge["affinity"],
                edge["trust"],
                edge["attraction"],
                edge["respect"],
                edge["fear"],
                edge["familiarity"],
                edge["interaction_count"],
                edge["last_interaction_tick"],
                json.dumps(edge["roles"], sort_keys=True),
                json.dumps({**edge, "tick": simulation.state.tick}, sort_keys=True),
            )
            for edge in graph["edges"]
        ]
        self.connection.executemany(
            "INSERT OR REPLACE INTO social_edges("
            "run_id, tick, source_id, target_id, relationship, affinity, trust, attraction, "
            "respect, "
            "fear, familiarity, interaction_count, last_interaction_tick, roles_json, edge_json) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        if commit:
            self.connection.commit()

    def mental_history(self, entity_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT mental_json FROM mental_states WHERE run_id = ? AND entity_id = ? "
            "ORDER BY tick DESC LIMIT ?",
            (self.run_id, entity_id, limit),
        ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def social_history(
        self, source_id: str, target_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT edge_json FROM social_edges "
            "WHERE run_id = ? AND source_id = ? AND target_id = ? "
            "ORDER BY tick DESC LIMIT ?",
            (self.run_id, source_id, target_id, limit),
        ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def load_latest(
        self, config: SimulationConfig, *, ai_worker: Any = None, innovation_manager: Any = None
    ) -> Simulation | None:
        row = self.connection.execute(
            "SELECT state_json, rng_json FROM snapshots WHERE run_id = ? "
            "ORDER BY tick DESC LIMIT 1",
            (self.run_id,),
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
        simulation.events = self.recent_events(limit=250)
        return simulation

    def recent_events(self, limit: int = 100) -> list[WorldEvent]:
        rows = self.connection.execute(
            "SELECT tick, event_type, actor_id, target_id, payload_json "
            "FROM events WHERE run_id = ? ORDER BY sequence DESC LIMIT ?",
            (self.run_id, limit),
        ).fetchall()
        return [
            WorldEvent(row[0], row[1], row[2], row[3], json.loads(row[4])) for row in reversed(rows)
        ]

    def save_rule(
        self, rule_id: str, version: int, definition: dict[str, Any], *, active: bool
    ) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO rule_versions"
            "(run_id, rule_id, version, active, definition_json) VALUES(?, ?, ?, ?, ?)",
            (self.run_id, rule_id, version, int(active), json.dumps(definition, sort_keys=True)),
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
        item["social_bonds"] = {
            target_id: SocialBond(**bond)
            for target_id, bond in item.get("social_bonds", {}).items()
        }
        action = item.get("action", {})
        action["kind"] = ActionType(action.get("kind", ActionType.IDLE))
        item["action"] = Action(**action)
        state.entities[entity_id] = Entity(**item)
    return state


def _as_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_as_tuple(item) for item in value)
    return value
