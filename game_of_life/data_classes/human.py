from dataclasses import dataclass, field
from typing import Literal

import pygame

# define GENDER_TYPE as literal of 'male' and 'female'

GENDER_TYPE = Literal['male', 'female']

@dataclass
class Human:
    x: int
    y: int
    sprite_path: str
    size: int
    gender: GENDER_TYPE
    attack: int = 0
    life: int = 100
    sprite: pygame.Surface = field(init=False)

    def __post_init__(self):
        self.sprite = pygame.image.load(self.sprite_path)
        self.sprite = pygame.transform.scale(self.sprite, (self.size, self.size))

    def draw(self, screen):
        screen.blit(self.sprite, (self.x, self.y))

    def update(self, dx, dy):
        self.x += dx
        self.y += dy
