from dataclasses import dataclass, field
import pygame

from typing import Literal

GENDER_TYPE = Literal["male", "female"]
ALIGNMENT_TYPE = Literal["good", "neutral", "evil"]

@dataclass
class Entity:
    x: int
    y: int
    sprite_path: str
    size: int
    sprite: pygame.Surface = field(init=False)

    def __post_init__(self):
        self.sprite = pygame.image.load(self.sprite_path)
        self.sprite = pygame.transform.scale(self.sprite, (self.size, self.size))

    def draw(self, screen, zoom_level=1.0, offset_x=0, offset_y=0):
        scaled_sprite = pygame.transform.scale(self.sprite, (int(self.size * zoom_level), int(self.size * zoom_level)))
        screen.blit(scaled_sprite, ((self.x - offset_x) * zoom_level, (self.y - offset_y) * zoom_level))

@dataclass
class AliveEntity(Entity):
    gender: GENDER_TYPE
    hunger: int = 0
    attack: int = 0
    life: int = 0
    alignment: ALIGNMENT_TYPE = "neutral"

    def update(self, dx, dy):
        self.x += dx
        self.y += dy
