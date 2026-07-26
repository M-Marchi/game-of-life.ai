from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from PIL import Image, ImageChops, ImageStat

from game_of_life.config import SimulationConfig
from game_of_life.models import EntityKind
from game_of_life.persistence import WorldStore
from game_of_life.ui import SimulationUI


def write_gif(
    path: Path,
    frames: list[pygame.Surface],
    *,
    delay_centiseconds: int = 14,
) -> None:
    if not frames:
        raise ValueError("at least one frame is required")
    images = [
        Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB"))
        for frame in frames
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=delay_centiseconds * 10,
        loop=0,
        disposal=2,
        optimize=True,
    )
    _validate_gif(path, images)


def _validate_gif(path: Path, references: list[Image.Image]) -> None:
    with Image.open(path) as rendered:
        if rendered.n_frames != len(references) or rendered.size != references[0].size:
            raise ValueError("rendered GIF has an incomplete frame sequence")
        checkpoints = {0, len(references) * 2 // 5, len(references) - 1}
        for index in checkpoints:
            rendered.seek(index)
            decoded = rendered.convert("RGB")
            difference = ImageChops.difference(decoded, references[index])
            mean_error = sum(ImageStat.Stat(difference).mean) / 3
            if mean_error > 12:
                raise ValueError(
                    f"rendered GIF frame {index} is visually corrupted (error {mean_error:.1f})"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the animated README demo")
    parser.add_argument("--database", type=Path, default=Path("saves/diagnostic-ai-final.db"))
    parser.add_argument("--output", type=Path, default=Path("docs/game-of-life-insight.gif"))
    parser.add_argument("--frames", type=int, default=28)
    args = parser.parse_args()

    config = SimulationConfig()
    with WorldStore(args.database) as store:
        simulation = store.load_latest(config)
    if simulation is None:
        raise ValueError(f"no snapshot in {args.database}")
    humans = simulation.state.living(EntityKind.HUMAN)
    selected = next(
        (human for human in humans if str(human.profession) in simulation.state.active_rules),
        max(humans, key=lambda human: len(human.social_bonds), default=None),
    )

    pygame.init()
    try:
        screen = pygame.display.set_mode(
            (simulation.state.width + config.panel_width, simulation.state.height)
        )
        ui = SimulationUI(simulation, screen, selected_id=selected.id if selected else None)
        frames: list[pygame.Surface] = []
        world_frames = max(8, args.frames * 2 // 5)
        for index in range(args.frames):
            for _ in range(10):
                simulation.step()
            ui.insight_mode = index >= world_frames
            ui.draw()
            frame = pygame.transform.smoothscale(screen, (960, 480))
            frames.append(frame.copy())
        write_gif(args.output, frames)
        print(f"{args.output} ({args.output.stat().st_size / 1_000_000:.2f} MB)")
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
