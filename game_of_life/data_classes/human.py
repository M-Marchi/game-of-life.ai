# game_of_life/data_classes/human.py
import threading
from dataclasses import dataclass, field
from typing import Literal
import numpy as np

from game_of_life.ai.brain import Brain
from game_of_life.ai.langchain_handler import LangchainHandler
from game_of_life.constants import (
    MALE_NAMES,
    FEMALE_NAMES,
)
from game_of_life.data_classes.action import Action, ActionType
from game_of_life.data_classes.animal import Cow
from game_of_life.data_classes.entity import AliveEntity, get_entity_by_id
import random
import pygame

from game_of_life.regex import get_dictionary_from_response

from loguru import logger as lg


@dataclass
class Human(AliveEntity):
    name: str = None
    background: dict = None
    brain: Brain = field(default_factory=Brain)
    color: tuple[int, int, int] = (255, 255, 255)
    langchain_handler: LangchainHandler = None
    thread: threading.Thread = field(init=False, default=None)

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, pygame.Rect(self.x, self.y, 2, 2))

        # Draw name on top of the human
        font = pygame.font.Font(None, 11)
        text = font.render(self.name, True, (255, 255, 255))
        screen.blit(text, (self.x - 10, self.y - 10))

    def start_thread_initialize(self):
        self.thread = threading.Thread(target=self.initialize)
        self.thread.start()

    def start_thread_think(self):
        self.thread = threading.Thread(target=self.think)
        self.thread.start()

    def start_thread_sleep(self):
        self.thread = threading.Thread(target=self.sleep)
        self.thread.start()

    def initialize(self):

        # Initialize Action
        self.action = Action(action_type=ActionType.IDLE)

        # Generate a name
        self._generate_name()

        # Generate IQ
        self._generate_IQ()

        # Generate the background
        self._generate_background()

        # Initialize Brain
        self.brain = Brain(IQ=self.IQ, LTM={}, STM=[], host=self)
        self._initialize_long_term_memory()

    def think(self) -> Action:
        # Process information
        self.brain.process()
        return self.action

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
        self.background = {
            "name": self.name,
            "IQ": self.IQ,
            "gender": self.gender,
            "attack": self.power,
            "age": self.age,
        }

    def _initialize_long_term_memory(self):
        LTM = {
            "background": self.background,
            "friends": [],
            "enemies": [],
            "important_memories": [],
        }
        self.brain.LTM = LTM

    def find_food(self, entities_dict: dict, target_distance: int) -> Action:
        for entity_id, distance in entities_dict.items():
            entity = get_entity_by_id(self.world.entities, entity_id)
            if isinstance(entity, Cow):
                if distance < 2:
                    lg.info(f"Cow {self.id} is eating")
                    self.hunger = 0
                    self.brain.STM.append(self.action.explanation)
                    return Action(action_type=ActionType.IDLE)
                elif distance < self.eye_sight:
                    if target_distance > distance:
                        target_distance = distance
                        self.speed = 2
                        return Action(action_type=ActionType.MOVE, target_id=entity_id)
        self.speed = 2
        return Action(action_type=ActionType.FIND_FOOD)

    def find_partner(self, entities_dict, target_distance) -> Action:
        for entity_id, distance in entities_dict.items():
            entity = get_entity_by_id(self.world.entities, entity_id)
            if issubclass(entity, Human) and entity.gender != self.gender:
                if distance < 2:
                    self.horny = 0
                    entity.horny = 0
                    baby_id = self.gave_birth()
                    child_id = self.world.spawn_humans(1)
                    self.brain.STM.append(
                        f"I found a partner {entity_id} and gave birth to {child_id} because: {self.action.explanation}"
                    )
                    return Action(action_type=ActionType.IDLE)
                elif distance < self.eye_sight:
                    if target_distance > distance:
                        target_distance = distance
                        self.speed = 2
                        return Action(action_type=ActionType.MOVE, target_id=entity_id)
        self.speed = 2
        return Action(action_type=ActionType.FIND_PARTNER)

    def sleep(self):
        self.brain.consolidate_memory()

    def gave_birth(self):
        child_id = self.world.spawn_humans(1)
        return child_id[0]
