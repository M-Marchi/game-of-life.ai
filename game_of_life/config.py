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
    decision_cooldown_ticks: int = 240
    max_pending_requests: int = 4


@dataclass(slots=True)
class SimulationConfig:
    width: int = 960
    height: int = 640
    panel_width: int = 320
    fps: int = 30
    ticks_per_second: int = 10
    seed: int = 42
    initial_humans: int = 8
    max_humans: int = 24
    initial_cows: int = 10
    max_cows: int = 36
    initial_trees: int = 90
    initial_rocks: int = 24
    initial_lakes: int = 5
    autosave_interval_ticks: int = 500
    world_event_interval_ticks: int = 1_200
    sleep_duration_ticks: int = 160
    dream_start_ticks: int = 80
    vocation_review_interval_ticks: int = 300
    ai: AIConfig = field(default_factory=AIConfig)


def load_config(*, ai_enabled: bool | None = None, seed: int | None = None) -> SimulationConfig:
    config = SimulationConfig()
    config.seed = seed if seed is not None else int(os.getenv("GOL_SEED", config.seed))
    config.ai.model = os.getenv("GOL_OLLAMA_MODEL", config.ai.model)
    config.ai.endpoint = os.getenv("GOL_OLLAMA_ENDPOINT", config.ai.endpoint)
    if ai_enabled is None:
        value = os.getenv("GOL_AI_ENABLED", "true").lower()
        config.ai.enabled = value not in {"0", "false", "no", "off"}
    else:
        config.ai.enabled = ai_enabled
    return config
