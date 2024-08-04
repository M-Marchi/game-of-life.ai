# game_of_life/data_classes/human.py
from dataclasses import dataclass, field
from typing import Literal

from game_of_life.constants import MALE_NAMES, FEMALE_NAMES
from game_of_life.data_classes.entity import AliveEntity
import random
import pygame

FACTIONS = Literal["red", "blue"]


@dataclass
class Human(AliveEntity):
    name: str = field(init=False)
    backstory: str = ""
    faction: FACTIONS = "red"

    def __post_init__(self):
        super().__post_init__()
        if self.gender == "male":
            self.name = random.choice(MALE_NAMES)
        elif self.gender == "female":
            self.name = random.choice(FEMALE_NAMES)

    def draw(self, screen, zoom_level=1.0, offset_x=0, offset_y=0):
        super().draw(screen, zoom_level, offset_x, offset_y)
        font = pygame.font.Font(None, 24)
        text_surface = font.render(self.name, True, (255, 255, 255))
        text_rect = text_surface.get_rect(
            center=(
                (self.x - offset_x) * zoom_level,
                (self.y - 10 - offset_y) * zoom_level,
            )
        )
        screen.blit(text_surface, text_rect)
