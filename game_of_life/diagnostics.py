from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from game_of_life.config import SimulationConfig
from game_of_life.main import main as simulation_main

CONVERSATION_EVENTS = {
    "talk",
    "story_told",
    "teach",
    "inspire",
    "affection",
    "forgive",
    "peace_made",
    "peace_rejected",
}


def analyze_database(path: str | Path) -> dict[str, Any]:
    database_path = Path(path)
    connection = sqlite3.connect(database_path)
    try:
        run_row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'current_run_id'"
        ).fetchone()
        if not run_row:
            raise ValueError("database has no current run")
        run_id = str(run_row[0])
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        event_counts = dict(
            connection.execute(
                "SELECT event_type, count(*) FROM events WHERE run_id = ? GROUP BY event_type",
                (run_id,),
            ).fetchall()
        )
        routine_counts = dict(
            connection.execute(
                "SELECT activity, sum(count) FROM routine_activity "
                "WHERE run_id = ? GROUP BY activity",
                (run_id,),
            ).fetchall()
        )
        max_tick = int(
            connection.execute(
                "SELECT max(tick) FROM snapshots WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            or 0
        )
        days = max(1, math.ceil(max_tick / SimulationConfig().ticks_per_day))

        decision_rows = connection.execute(
            "SELECT actor_id, action, payload_json FROM events "
            "WHERE run_id = ? AND event_type = 'ai_decision' ORDER BY sequence",
            (run_id,),
        ).fetchall()
        actions = Counter(str(row[1]) for row in decision_rows)
        goals = Counter(
            str(json.loads(row[2]).get("goal", "")) for row in decision_rows if row[2]
        )
        ai_started = int(event_counts.get("ai_thinking", 0))
        ai_terminal = sum(
            int(event_counts.get(event_type, 0))
            for event_type in ("ai_decision", "ai_error", "ai_rejected", "ai_cancelled")
        )
        ai_valid = int(event_counts.get("ai_decision", 0))
        completion_rate = ai_terminal / ai_started if ai_started else None
        valid_rate = ai_valid / ai_started if ai_started else None
        dominant_action_share = max(actions.values(), default=0) / ai_valid if ai_valid else None

        conversations = sum(int(event_counts.get(name, 0)) for name in CONVERSATION_EVENTS)
        dreams = int(event_counts.get("dream", 0))
        qwen_dreams = connection.execute(
            "SELECT count(*) FROM events WHERE run_id = ? AND event_type = 'dream' "
            "AND json_extract(payload_json, '$.generated_by') = 'qwen3:8b'",
            (run_id,),
        ).fetchone()[0]
        active_rules = connection.execute(
            "SELECT count(*) FROM rule_versions WHERE run_id = ? AND active = 1",
            (run_id,),
        ).fetchone()[0]
        active_rule_ids = {
            str(row[0])
            for row in connection.execute(
                "SELECT rule_id FROM rule_versions WHERE run_id = ? AND active = 1", (run_id,)
            ).fetchall()
        }
        latest_mental_tick = connection.execute(
            "SELECT max(tick) FROM mental_states WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        generated_workers = [
            {
                "entity_id": entity_id,
                "name": name,
                "profession": profession,
                "current_action": json.loads(mental_json).get("current_action", {}),
                "needs": json.loads(mental_json).get("needs", {}),
            }
            for entity_id, name, profession, mental_json in connection.execute(
                "SELECT entity_id, name, profession, mental_json FROM mental_states "
                "WHERE run_id = ? AND tick = ?",
                (run_id, latest_mental_tick),
            ).fetchall()
            if profession in active_rule_ids
        ]
        work_payloads = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT payload_json FROM events WHERE run_id = ? AND event_type = 'work'",
                (run_id,),
            ).fetchall()
        ]
        generated_work = [item for item in work_payloads if item.get("rule_id")]
        actual_impacts = [
            float(impact.get("actual_amount", 0))
            for work in generated_work
            for impact in work.get("impacts", [])
            if float(impact.get("actual_amount", 0)) > 0
        ]
        narrative_events = sum(event_counts.values()) - ai_started
        routine_events = sum(int(value) for value in routine_counts.values())
        protagonists = connection.execute(
            "SELECT actor_id, count(*) AS total FROM events "
            "WHERE run_id = ? AND actor_id IS NOT NULL AND event_type != 'ai_thinking' "
            "GROUP BY actor_id ORDER BY total DESC, actor_id LIMIT 5",
            (run_id,),
        ).fetchall()
        samples = {
            "decisions": [
                {
                    "actor_id": actor_id,
                    "action": action,
                    **{
                        key: payload.get(key)
                        for key in ("day", "hour", "goal", "explanation", "age_ticks")
                    },
                }
                for actor_id, action, raw_payload in decision_rows[-8:]
                for payload in [json.loads(raw_payload)]
            ],
            "ai_failures": [
                {"event_type": event_type, **json.loads(raw_payload)}
                for event_type, raw_payload in connection.execute(
                    "SELECT event_type, payload_json FROM events WHERE run_id = ? "
                    "AND event_type IN ('ai_error', 'ai_rejected', 'ai_cancelled') "
                    "ORDER BY sequence DESC LIMIT 8",
                    (run_id,),
                ).fetchall()
            ],
            "dreams": [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload_json FROM events WHERE run_id = ? AND event_type = 'dream' "
                    "ORDER BY sequence DESC LIMIT 4",
                    (run_id,),
                ).fetchall()
            ],
            "innovations": [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload_json FROM events WHERE run_id = ? "
                    "AND event_type = 'rule_activated' ORDER BY sequence DESC LIMIT 4",
                    (run_id,),
                ).fetchall()
            ],
        }

        warnings: list[str] = []
        if completion_rate is not None and completion_rate < 0.95:
            warnings.append("some AI requests have no terminal outcome")
        if valid_rate is not None and valid_rate < 0.75:
            warnings.append("too many AI decisions are rejected or fail")
        if dominant_action_share is not None and dominant_action_share > 0.6:
            warnings.append("AI behavior is dominated by one action")
        if ai_valid >= 5 and len(actions) < 3:
            warnings.append("AI action variety is low")
        if days >= 2 and conversations == 0:
            warnings.append("no meaningful conversations emerged")
        if days >= 2 and dreams == 0:
            warnings.append("no dreams were persisted")
        if active_rules and not generated_work:
            warnings.append("a generated profession exists but has not worked yet")
        if active_rules and generated_work and not actual_impacts:
            warnings.append("generated professions are working without changing the world")

        return {
            "database": str(database_path),
            "run_id": run_id,
            "integrity": integrity,
            "days_observed": days,
            "storage": {
                "database_bytes": database_path.stat().st_size,
                "event_rows": sum(event_counts.values()),
                "narrative_rows": narrative_events,
                "routine_rows": connection.execute(
                    "SELECT count(*) FROM routine_activity WHERE run_id = ?", (run_id,)
                ).fetchone()[0],
                "routine_actions_aggregated": routine_events,
                "routine_rows_avoided": routine_events
                - connection.execute(
                    "SELECT count(*) FROM routine_activity WHERE run_id = ?", (run_id,)
                ).fetchone()[0],
            },
            "ai": {
                "started": ai_started,
                "terminal": ai_terminal,
                "valid_decisions": ai_valid,
                "completion_rate": completion_rate,
                "valid_rate": valid_rate,
                "outcomes": {
                    event_type: int(event_counts.get(event_type, 0))
                    for event_type in (
                        "ai_decision",
                        "ai_error",
                        "ai_rejected",
                        "ai_cancelled",
                    )
                },
                "actions": dict(actions.most_common()),
                "unique_goals": len(goals),
                "dominant_action_share": dominant_action_share,
            },
            "emergence": {
                "conversations": conversations,
                "dreams": dreams,
                "qwen_dreams": int(qwen_dreams),
                "active_generated_rules": int(active_rules),
                "generated_work_cycles": len(generated_work),
                "real_impact_count": len(actual_impacts),
                "real_impact_total": round(sum(actual_impacts), 3),
                "generated_workers": generated_workers,
                "protagonists": [
                    {"actor_id": actor_id, "narrative_events": total}
                    for actor_id, total in protagonists
                ],
            },
            "routine": routine_counts,
            "samples": samples,
            "warnings": warnings,
            "interesting": not warnings,
        }
    finally:
        connection.close()


def format_report(report: dict[str, Any]) -> str:
    ai = report["ai"]
    emergence = report["emergence"]
    storage = report["storage"]
    lines = [
        f"Run {report['run_id']} — {report['days_observed']} giorni — DB {report['integrity']}",
        (
            f"Storage: {storage['narrative_rows']} eventi narrativi; "
            f"{storage['routine_actions_aggregated']} attività di routine in "
            f"{storage['routine_rows']} righe aggregate "
            f"({storage['routine_rows_avoided']} righe evitate)"
        ),
        (
            f"AI: {ai['valid_decisions']}/{ai['started']} decisioni valide; "
            f"azioni={ai['actions']}; obiettivi unici={ai['unique_goals']}"
        ),
        (
            f"Emergenza: conversazioni={emergence['conversations']}; "
            f"sogni={emergence['dreams']} (Qwen {emergence['qwen_dreams']}); "
            f"regole attive={emergence['active_generated_rules']}; "
            f"impatti reali={emergence['real_impact_count']}"
        ),
    ]
    if report["warnings"]:
        lines.append("Da indagare: " + "; ".join(report["warnings"]))
    else:
        lines.append("Esito: segnali emergenti vari e pipeline sana nel campione osservato.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run and diagnose an emergent society sample")
    parser.add_argument("--mode", choices=("offline", "ai"), default="offline")
    parser.add_argument(
        "--analyze-only", action="store_true", help="analyze an existing diagnostic database"
    )
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--settle-ticks",
        type=int,
        default=1_200,
        help="offline consequence ticks after an AI sample (default: 1200)",
    )
    parser.add_argument("--save", type=Path, default=Path("saves/diagnostic.db"))
    parser.add_argument("--report", type=Path, default=Path("saves/diagnostic-report.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ticks = args.ticks
    if ticks is None:
        ticks = 300 if args.mode == "ai" else SimulationConfig().ticks_per_day * max(1, args.days)
    command = [
        "--headless",
        "--ticks",
        str(ticks),
        "--seed",
        str(args.seed),
        "--save",
        str(args.save),
    ]
    if args.mode == "offline":
        command.append("--no-ai")
    result = 0
    if not args.analyze_only:
        result = simulation_main(command)
        if args.mode == "ai" and args.settle_ticks > 0:
            result = simulation_main(
                [
                    "--headless",
                    "--no-ai",
                    "--load",
                    "--ticks",
                    str(args.settle_ticks),
                    "--seed",
                    str(args.seed),
                    "--save",
                    str(args.save),
                ]
            )
    report = analyze_database(args.save)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(format_report(report))
    print(f"Report JSON: {args.report}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
