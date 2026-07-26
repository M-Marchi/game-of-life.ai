from __future__ import annotations

import argparse
import os
import struct
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game_of_life.config import SimulationConfig
from game_of_life.models import EntityKind
from game_of_life.persistence import WorldStore
from game_of_life.ui import SimulationUI


def _palette() -> bytes:
    colors = bytearray()
    for index in range(256):
        red = ((index >> 5) & 0x07) * 255 // 7
        green = ((index >> 2) & 0x07) * 255 // 7
        blue = (index & 0x03) * 255 // 3
        colors.extend((red, green, blue))
    return bytes(colors)


def _indexed_pixels(surface: pygame.Surface) -> bytes:
    rgb = pygame.image.tobytes(surface, "RGB")
    indexed = bytearray(len(rgb) // 3)
    output_index = 0
    for offset in range(0, len(rgb), 3):
        indexed[output_index] = (
            ((rgb[offset] >> 5) << 5) | ((rgb[offset + 1] >> 5) << 2) | (rgb[offset + 2] >> 6)
        )
        output_index += 1
    return bytes(indexed)


def _lzw_encode(pixels: bytes) -> bytes:
    clear_code = 256
    end_code = 257
    dictionary = {bytes((value,)): value for value in range(256)}
    next_code = 258
    code_size = 9
    bit_buffer = 0
    bit_count = 0
    encoded = bytearray()

    def emit(code: int) -> None:
        nonlocal bit_buffer, bit_count
        bit_buffer |= code << bit_count
        bit_count += code_size
        while bit_count >= 8:
            encoded.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8

    emit(clear_code)
    prefix = bytes((pixels[0],))
    for value in pixels[1:]:
        candidate = prefix + bytes((value,))
        if candidate in dictionary:
            prefix = candidate
            continue
        emit(dictionary[prefix])
        if next_code < 4096:
            dictionary[candidate] = next_code
            next_code += 1
            if next_code == 1 << code_size and code_size < 12:
                code_size += 1
        else:
            emit(clear_code)
            dictionary = {bytes((item,)): item for item in range(256)}
            next_code = 258
            code_size = 9
        prefix = bytes((value,))
    emit(dictionary[prefix])
    emit(end_code)
    if bit_count:
        encoded.append(bit_buffer & 0xFF)
    return bytes(encoded)


def _sub_blocks(data: bytes) -> bytes:
    blocks = bytearray()
    for offset in range(0, len(data), 255):
        block = data[offset : offset + 255]
        blocks.append(len(block))
        blocks.extend(block)
    blocks.append(0)
    return bytes(blocks)


def write_gif(
    path: Path,
    frames: list[pygame.Surface],
    *,
    delay_centiseconds: int = 14,
) -> None:
    if not frames:
        raise ValueError("at least one frame is required")
    width, height = frames[0].get_size()
    payload = bytearray(b"GIF89a")
    payload.extend(struct.pack("<HHBBB", width, height, 0xF7, 0, 0))
    payload.extend(_palette())
    payload.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")
    for frame in frames:
        payload.extend(b"\x21\xf9\x04\x04")
        payload.extend(struct.pack("<H", delay_centiseconds))
        payload.extend(b"\x00\x00")
        payload.extend(b"\x2c\x00\x00\x00\x00")
        payload.extend(struct.pack("<HHB", width, height, 0))
        payload.append(8)
        payload.extend(_sub_blocks(_lzw_encode(_indexed_pixels(frame))))
    payload.append(0x3B)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


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
