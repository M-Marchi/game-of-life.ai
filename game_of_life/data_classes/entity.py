from dataclasses import dataclass, field
import random
from loguru import logger as lg

import pygame

from typing import Literal

GENDER_TYPE = Literal["male", "female"]
ALIGNMENT_TYPE = Literal["good", "neutral", "evil"]


@dataclass
class Entity:
    x: int = 0
    y: int = 0
    sprite_path: str = None
    size: int = 50
    sprite: pygame.Surface = None

    def __post_init__(self):
        self.sprite = pygame.image.load(self.sprite_path)
        self.sprite = pygame.transform.scale(self.sprite, (self.size, self.size))

    def draw(self, screen, zoom_level=1.0, offset_x=0, offset_y=0):
        scaled_sprite = pygame.transform.scale(
            self.sprite, (int(self.size * zoom_level), int(self.size * zoom_level))
        )
        screen.blit(
            scaled_sprite,
            ((self.x - offset_x) * zoom_level, (self.y - offset_y) * zoom_level),
        )


@dataclass
class AliveEntity(Entity):
    id: str = None
    gender: GENDER_TYPE = None
    age: int = 0
    hunger: int = 0
    attack: int = 0
    life: int = 0
    energy: int = 0
    alignment: ALIGNMENT_TYPE = "neutral"
    direction: tuple[int, int] = field(
        default_factory=lambda: (random.randint(-1, 1), random.randint(-1, 1))
    )

    def __post_init__(self):
        super().__post_init__()
        self.id = str(random.randint(0, 1000000))

    def update(self, dx, dy, world_width, world_height):
        # Change direction with a probability of 1/100
        if random.random() < 0.01:
            self.direction = (random.randint(-1, 1), random.randint(-1, 1))

        new_x = self.x + self.direction[0] * dx
        new_y = self.y + self.direction[1] * dy

        # Ensure the entity does not move outside the screen boundaries
        if 50 <= new_x < world_width - self.size - 50:
            self.x = new_x
        else:
            lg.trace(f"Changing direction of {self.name} due to x boundary")
            self.direction = (-self.direction[0], self.direction[1])
            new_x = self.x + self.direction[0] * dx
            self.x = new_x

        if 50 <= new_y < world_height - self.size - 50:
            self.y = new_y
        else:
            lg.trace(f"Changing direction of {self.name} due to y boundary")
            self.direction = (self.direction[0], -self.direction[1])
            new_y = self.y + self.direction[1] * dy
            self.y = new_y
