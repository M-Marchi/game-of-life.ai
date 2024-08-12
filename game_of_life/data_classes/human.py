# game_of_life/data_classes/human.py
from dataclasses import dataclass, field
from typing import Literal
import numpy as np

from game_of_life.ai.brain import Brain
from game_of_life.ai.langchain_handler import LangchainHandler
from game_of_life.ai.prompt import NEW_BACKGROUND_PROMPT
from game_of_life.constants import (
    MALE_NAMES,
    FEMALE_NAMES,
    GENERIC_MALE_SPRITE,
    GENERIC_FEMALE_SPRITE,
)
from game_of_life.data_classes.entity import AliveEntity
import random
import pygame

FACTIONS = Literal["red", "blue"]


@dataclass
class Human(AliveEntity):
    name: str = None
    background: str = ""
    faction: FACTIONS = "red"
    brain: Brain = field(default_factory=Brain)
    langchain_handler: LangchainHandler = None

    def __post_init__(self):
        super().__post_init__()

        # Generate a name
        self._generate_name()

        # Generate IQ
        self._generate_IQ()

        # Generate the background
        self._generate_background()

        # Initialize Brain
        self.brain = Brain(IQ=self.IQ, LTM=[self.background], STM=[])

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

    def _generate_name(self):
        # Generate a name based on gender
        if self.gender == "male":
            self.name = random.choice(MALE_NAMES)
        elif self.gender == "female":
            self.name = random.choice(FEMALE_NAMES)

    def _generate_IQ(self):
        # Get a IQ value from normal distribution
        self.IQ = int(np.random.normal(100, 15))

    def _generate_background(self):
        prompt = NEW_BACKGROUND_PROMPT.format(
            name=self.name,
            IQ=self.IQ,
            gender=self.gender,
            faction_name=self.faction,
            attack=self.attack,
            age=self.age,
        )
        self.background = self.langchain_handler.call_model(prompt)



class GenericMale(Human):
    def __init__(self, x, y, size, langchain_handler):
        super().__init__(x=x, y=y, sprite_path=GENERIC_FEMALE_SPRITE, size=size, langchain_handler=langchain_handler)
        self.gender = "male"


class GenericFemale(Human):
    def __init__(self, x, y, size, langchain_handler):
        super().__init__(x=x, y=y, sprite_path=GENERIC_FEMALE_SPRITE, size=size, langchain_handler=langchain_handler)
        self.gender = "female"
