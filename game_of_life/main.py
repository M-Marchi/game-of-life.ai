from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from game_of_life.ai.client import OllamaAIClient
from game_of_life.ai.scheduler import AIWorker
from game_of_life.config import SimulationConfig, load_config
from game_of_life.engine import Simulation
from game_of_life.innovation import InnovationManager
from game_of_life.persistence import WorldStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Game of Life AI society sandbox")
    parser.add_argument(
        "--no-ai", action="store_true", help="run with deterministic local cognition only"
    )
    parser.add_argument("--headless", action="store_true", help="run without opening Pygame")
    parser.add_argument(
        "--ticks", type=int, default=1_000, help="ticks to execute in headless mode"
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--save", type=Path, default=Path("saves/world.db"))
    parser.add_argument("--load", action="store_true", help="resume the latest snapshot")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(ai_enabled=not args.no_ai, seed=args.seed)
    ai_worker = _start_ai(config) if config.ai.enabled else None
    innovation_manager = InnovationManager(ai_worker) if ai_worker else None

    with WorldStore(args.save) as store:
        simulation = (
            store.load_latest(
                config,
                ai_worker=ai_worker,
                innovation_manager=innovation_manager,
            )
            if args.load
            else None
        )
        simulation = simulation or Simulation(
            config,
            ai_worker=ai_worker,
            innovation_manager=innovation_manager,
        )
        simulation.add_event_sink(store.record_event)
        if args.headless:
            _run_headless(simulation, args.ticks, store)
        else:
            _run_pygame(simulation, store)
        store.save_snapshot(simulation)

    if ai_worker:
        ai_worker.stop()
    stats = simulation.statistics()
    logger.info(
        "Stopped at tick {} with {} humans and {} cows",
        simulation.state.tick,
        stats["humans"],
        stats["cows"],
    )
    return 0


def _start_ai(config: SimulationConfig) -> AIWorker | None:
    client = OllamaAIClient(config.ai)
    if not client.healthcheck():
        logger.warning("Ollama model {} is unavailable; using local cognition", config.ai.model)
        return None
    worker = AIWorker(client, config.ai.max_pending_requests)
    worker.start()
    logger.info("Connected to Ollama model {}", config.ai.model)
    return worker


def _run_headless(simulation: Simulation, ticks: int, store: WorldStore) -> None:
    for _ in range(max(0, ticks)):
        simulation.step()
        if simulation.state.tick % simulation.config.autosave_interval_ticks == 0:
            store.save_snapshot(simulation)


def _run_pygame(simulation: Simulation, store: WorldStore) -> None:
    import pygame

    from game_of_life.ui import SimulationUI

    pygame.init()
    screen = pygame.display.set_mode(
        (simulation.config.width + simulation.config.panel_width, simulation.config.height)
    )
    pygame.display.set_caption("Game of Life AI")
    ui = SimulationUI(simulation, screen)
    clock = pygame.time.Clock()
    tick_accumulator = 0.0
    running = True
    last_saved_tick = simulation.state.tick
    while running:
        elapsed_seconds = clock.tick(simulation.config.fps) / 1_000
        for event in pygame.event.get():
            running = ui.handle_event(event)
        if not ui.paused:
            tick_accumulator += elapsed_seconds * simulation.config.ticks_per_second * ui.speed
            while tick_accumulator >= 1:
                simulation.step()
                tick_accumulator -= 1
        ui.draw()
        if (
            simulation.state.tick != last_saved_tick
            and simulation.state.tick % simulation.config.autosave_interval_ticks == 0
        ):
            store.save_snapshot(simulation)
            last_saved_tick = simulation.state.tick
    pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
