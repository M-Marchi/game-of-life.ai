# game_of_life/main.py
import pygame
import sys
import threading

from game_of_life.config import *
from game_of_life.world import World

from loguru import logger as lg

lg.remove()
lg.add(sys.stderr, level="DEBUG")
lg.success("Game of Life started")

# Initialize Pygame
pygame.init()

# Set up the game window
screen_width, screen_height = 1600, 800
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Game of Life")

# Create the world
world = World(
    screen_width,
    screen_height,
    NUM_TREES,
    NUM_LAKES,
)

# Spawn entities
world.spawn_lakes(3)
world.spawn_trees(50)
world.spawn_humans(2)
world.spawn_cows(10)

# Define colors
BLACK = (0, 0, 0)

# Set up the clock for managing the frame rate
clock = pygame.time.Clock()

# Main game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Update game state
    world.update_humans()
    world.update_cow()

    # Draw everything
    screen.fill(BLACK)
    world.draw(screen)

    # Update the display
    pygame.display.flip()

    # Cap the frame rate at 10 fps
    clock.tick(10)

# Quit Pygame
pygame.quit()
sys.exit()
