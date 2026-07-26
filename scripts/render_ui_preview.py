from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game_of_life.config import SimulationConfig
from game_of_life.engine import Simulation
from game_of_life.models import EntityKind
from game_of_life.persistence import WorldStore
from game_of_life.ui import SimulationUI


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a UI screenshot without opening a window")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--output", type=Path, default=Path("saves/ui-preview.png"))
    parser.add_argument("--insight", action="store_true")
    args = parser.parse_args()

    config = SimulationConfig()
    simulation = None
    if args.database and args.database.exists():
        with WorldStore(args.database) as store:
            simulation = store.load_latest(config)
    simulation = simulation or Simulation(config)
    humans = simulation.state.living(EntityKind.HUMAN)
    selected = next(
        (human for human in humans if str(human.profession) in simulation.state.active_rules),
        None,
    )
    selected = selected or max(
        humans,
        key=lambda human: (
            bool(human.last_dream),
            len(human.social_bonds),
            len(human.long_term_memory),
        ),
        default=None,
    )

    pygame.init()
    try:
        screen = pygame.display.set_mode(
            (simulation.state.width + config.panel_width, simulation.state.height)
        )
        ui = SimulationUI(
            simulation,
            screen,
            selected_id=selected.id if selected else None,
        )
        if hasattr(ui, "insight_mode"):
            ui.insight_mode = args.insight
        else:
            ui.graph_mode = args.insight
        ui.draw()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(screen, args.output)
        print(args.output)
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
