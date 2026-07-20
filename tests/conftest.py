from __future__ import annotations

import pytest

from game_of_life.config import SimulationConfig


@pytest.fixture
def empty_config() -> SimulationConfig:
    return SimulationConfig(
        width=320,
        height=240,
        initial_humans=0,
        initial_cows=0,
        initial_trees=0,
        initial_rocks=0,
        initial_lakes=0,
    )
