from dataclasses import dataclass, field
import pygame
import random

from game_of_life.ai.langchain_handler import LangchainHandler
from game_of_life.constants import (
    MODEL_NAME,
)
from game_of_life.data_classes.animal import Cow
from game_of_life.data_classes.human import Human
from game_of_life.data_classes.world_entity import Tree, Lake

from loguru import logger as lg


@dataclass
class World:
    width: int
    height: int
    zoom_level: float = 1.0
    offset_x: int = 0
    offset_y: int = 0
    entities: list = field(default_factory=list)
    buildings: list = field(default_factory=list)
    langchain_handler: LangchainHandler = field(init=False)

    def __post_init__(self):
        self.langchain_handler = LangchainHandler(model_name=MODEL_NAME)

    def draw_background(self, screen):
        light_green = (51, 204, 51)  # Light green color
        screen.fill(light_green)

    def spawn_humans(self, count):
        ids = []
        for i in range(count):
            x = random.randint(0, self.width - 10)
            y = random.randint(0, self.height - 10)
            gender = random.choice(["male", "female"])
            age = random.randint(18, 80)
            if gender == "male":
                human = Human(
                    x=x,
                    y=y,
                    age=age,
                    gender="male",
                    color=(173, 216, 230),
                    power=random.randint(50, 100),
                    langchain_handler=self.langchain_handler,
                    world=self,
                )
            else:
                human = Human(
                    x=x,
                    y=y,
                    age=age,
                    gender="female",
                    color=(255, 105, 180),
                    power=random.randint(0, 50),
                    langchain_handler=self.langchain_handler,
                    world=self,
                )

            ids.append(human.id)
            lg.info(f"New human {human.id} was born")
            human.start_thread_initialize()
            self.entities.append(human)
        return ids

    def spawn_cows(self, count):
        for _ in range(count):
            x = random.randint(0, self.width - 10)
            y = random.randint(0, self.height - 10)
            gender = random.choice(["male", "female"])
            cow = Cow(gender=gender, x=x, y=y, world=self)
            lg.info(f"New cow {cow.id} was born")
            self.entities.append(cow)

    def update_humans(self):
        for entity in self.entities:
            if isinstance(entity, Human):
                if entity.thread is None or not entity.thread.is_alive():
                    entity.start_thread_think()
                    entity.interact(entity.action)
                entity.update_stats()

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
            tree = Tree(x=x, y=y, world=self)
            self.entities.append(tree)

    def spawn_lakes(self, count):
        for _ in range(count):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            lake = Lake(x=x, y=y, world=self)
            self.entities.append(lake)

    def draw(self, screen):
        self.draw_background(screen)
        for entity in self.entities:
            entity.draw(screen)

        for building in self.buildings:
            try:
                exec(building)
            except Exception as e:
                lg.error(f"Error while drawing building: {building}")

    def add_entity(self, entity):
        self.entities.append(entity)

    def remove_entity_by_id(self, entity_id):
        for entity in self.entities:
            if entity.id == entity_id:
                self.entities.remove(entity)
                break
