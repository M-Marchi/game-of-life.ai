from __future__ import annotations


def test_pygame_can_render_headless(empty_config, monkeypatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")

    import pygame

    from game_of_life.engine import Simulation
    from game_of_life.ui import SimulationUI

    pygame.init()
    try:
        simulation = Simulation(empty_config)
        simulation.spawn_human()
        screen = pygame.display.set_mode(
            (empty_config.width + empty_config.panel_width, empty_config.height)
        )
        ui = SimulationUI(simulation, screen)
        ui.draw()
        assert screen.get_size() == (
            empty_config.width + empty_config.panel_width,
            empty_config.height,
        )
    finally:
        pygame.quit()
