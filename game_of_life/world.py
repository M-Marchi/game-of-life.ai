from dataclasses import dataclass, field
import pygame
import random

from game_of_life.ai.langchain_handler import LangchainHandler
from game_of_life.constants import (
    GENERIC_MALE_SPRITE,
    GENERIC_FEMALE_SPRITE,
    MODEL_NAME,
)
from game_of_life.data_classes.animal import Cow
from game_of_life.data_classes.human import Human, GenericMale, GenericFemale
from game_of_life.data_classes.world_entity import Tree, Lake


@dataclass
class World:
    width: int
    height: int
    zoom_level: float = 1.0
    offset_x: int = 0
    offset_y: int = 0
    entities: list = field(init=False)
    langchain_handler: LangchainHandler = field(init=False)

    def __post_init__(self):
        self.langchain_handler = LangchainHandler(model_name=MODEL_NAME)
        self.entities = []

    def draw_background(self, screen):
        light_green = (51, 204, 51)  # Light green color
        screen.fill(light_green)

    def spawn_humans(self, count):
        for _ in range(count):
            x = random.randint(0, self.width - 10)
            y = random.randint(0, self.height - 10)
            gender = random.choice(["male", "female"])
            age = random.randint(18, 80)
            if gender == "male":
                human = GenericMale(
                    x=x,
                    y=y,
                    age=age,
                    langchain_handler=self.langchain_handler,
                    world=self,
                )
            else:
                human = GenericFemale(
                    x=x,
                    y=y,
                    age=age,
                    langchain_handler=self.langchain_handler,
                    world=self,
                )
            human.start_thread()
            self.entities.append(human)

    def spawn_cows(self, count):
        for _ in range(count):
            x = random.randint(0, self.width - 10)
            y = random.randint(0, self.height - 10)
            gender = random.choice(["male", "female"])
            cow = Cow(gender=gender, x=x, y=y, world=self)
            self.entities.append(cow)

    def update_humans(self):
        for entity in self.entities:
            if isinstance(entity, Human):
                dx = 1
                dy = 1
                entity.update_movement(dx, dy)

    def update_cow(self):
        for entity in self.entities:
            if isinstance(entity, Cow):
                entity.think()
                entity.interact(entity.action)
                entity.update_stats()

    def spawn_trees(self, count):
        for _ in range(count):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            tree = Tree(x=x, y=y)
            self.entities.append(tree)

    def spawn_lakes(self, count):
        for _ in range(count):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            lake = Lake(x=x, y=y)
            self.entities.append(lake)

    def draw(self, screen):
        self.draw_background(screen)
        for entity in self.entities:
            entity.draw(screen)

    def add_entity(self, entity):
        self.entities.append(entity)

    def remove_entity_by_id(self, entity_id):
        for entity in self.entities:
            if entity.id == entity_id:
                self.entities.remove(entity)
                break
