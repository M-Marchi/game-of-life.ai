from dataclasses import dataclass, field

import pygame

from game_of_life.constants import COW_SPRITE
from game_of_life.data_classes.entity import AliveEntity


@dataclass
class Cow(AliveEntity):
    meat: int = 10

    def __post_init__(self):
        super().__post_init__()

    def draw(self, screen):
        # Draw the white body of the cow as a rectangle
        pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(self.x, self.y, 10, 10))

        # Add black pixels inside the cow
        black_pixels = [
            (self.x + 2, self.y + 2),
            (self.x + 4, self.y + 4),
            (self.x + 6, self.y + 6)
        ]
        for pixel in black_pixels:
            screen.set_at(pixel, (0, 0, 0))
