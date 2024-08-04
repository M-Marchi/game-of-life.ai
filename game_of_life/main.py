import pygame
import sys

from game_of_life.config import *
from game_of_life.world import World

# Initialize Pygame
pygame.init()

# Set up the game window
screen_width, screen_height = 1920, 1080
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Game of Life")

# Create the world
world = World(
    screen_width * 10,
    screen_height * 10,
    screen_width,
    screen_height,
    NUM_TREES,
    NUM_LAKES,
)

# Define colors
BLACK = (0, 0, 0)

# Main game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEWHEEL:
            world.handle_mouse_wheel(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                world.start_drag(*event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # Left mouse button
                world.end_drag()
        elif event.type == pygame.MOUSEMOTION:
            if world.dragging:
                world.drag(*event.pos)

    # Update game state
    # (Add game logic here)

    # Draw everything
    screen.fill(BLACK)
    world.draw(screen)

    # Update the display
    pygame.display.flip()

# Quit Pygame
pygame.quit()
sys.exit()