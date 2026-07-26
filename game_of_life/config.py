from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class AIConfig:
    enabled: bool = True
    model: str = "qwen3:8b"
    endpoint: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 120.0
    decision_interval_ticks: int = 20
    decision_cooldown_ticks: int = 1_200
    max_pending_requests: int = 4
    result_max_age_ticks: int = 600


@dataclass(slots=True)
class SimulationConfig:
    width: int = 960
    height: int = 640
    panel_width: int = 320
    fps: int = 30
    ticks_per_second: int = 10
    day_length_minutes: float = 4.0
    day_start_hour: float = 6.0
    daylight_start_hour: float = 6.0
    night_start_hour: float = 22.0
    sleep_hours: float = 8.0
    seed: int = 42
    initial_humans: int = 8
    max_humans: int = 24
    initial_cows: int = 10
    max_cows: int = 36
    initial_trees: int = 90
    initial_rocks: int = 24
    initial_lakes: int = 5
    autosave_interval_ticks: int = 500
    world_event_interval_ticks: int = 2_400
    sleep_duration_ticks: int | None = None
    dream_start_ticks: int | None = None
    vocation_review_interval_ticks: int = 2_400
    purposeful_action_cooldown_ticks: int = 300
    mental_snapshot_interval_ticks: int = 1_800
    ai: AIConfig = field(default_factory=AIConfig)

    @property
    def ticks_per_day(self) -> int:
        return max(24, round(self.day_length_minutes * 60 * self.ticks_per_second))

    @property
    def resolved_sleep_duration_ticks(self) -> int:
        if self.sleep_duration_ticks is not None:
            return max(1, self.sleep_duration_ticks)
        return max(1, round(self.ticks_per_day * self.sleep_hours / 24))

    @property
    def resolved_dream_start_ticks(self) -> int:
        if self.dream_start_ticks is not None:
            return max(0, self.dream_start_ticks)
        return self.resolved_sleep_duration_ticks // 2


def load_config(*, ai_enabled: bool | None = None, seed: int | None = None) -> SimulationConfig:
    config = SimulationConfig()
    config.seed = seed if seed is not None else int(os.getenv("GOL_SEED", config.seed))
    config.ai.model = os.getenv("GOL_OLLAMA_MODEL", config.ai.model)
    config.ai.endpoint = os.getenv("GOL_OLLAMA_ENDPOINT", config.ai.endpoint)
    mental_minutes = float(os.getenv("GOL_MENTAL_SNAPSHOT_MINUTES", "3"))
    config.mental_snapshot_interval_ticks = max(
        0, round(mental_minutes * 60 * config.ticks_per_second)
    )
    if ai_enabled is None:
        value = os.getenv("GOL_AI_ENABLED", "true").lower()
        config.ai.enabled = value not in {"0", "false", "no", "off"}
    else:
        config.ai.enabled = ai_enabled
    return config
