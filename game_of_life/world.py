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
    trees: list = field(init=False)
    lakes: list = field(init=False)
    humans: list = field(init=False)
    cows: list = field(init=False)
    langchain_handler: LangchainHandler = field(init=False)

    def __post_init__(self):
        self.langchain_handler = LangchainHandler(model_name=MODEL_NAME)

        self.trees = []
        self.lakes = []
        self.humans = []
        self.cows = []

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
                )
            else:
                human = GenericFemale(
                    x=x,
                    y=y,
                    age=age,
                    langchain_handler=self.langchain_handler,
                )
            human.start_thread()
            self.humans.append(human)

    def update_humans(self):
        for human in self.humans:
            dx = random.randint(0, 2)
            dy = random.randint(0, 2)
            human.update(dx, dy, self.width, self.height)

    def update_cow(self):
        for cow in self.cows:
            dx = random.randint(0, 2)
            dy = random.randint(0, 2)
            cow.update(dx, dy, self.width, self.height)

    def draw_humans(self, screen):
        for human in self.humans:
            human.draw(screen,)

    def spawn_cows(self, count):
        for _ in range(count):
            x = random.randint(0, self.width - 10)
            y = random.randint(0, self.height - 10)
            cow = Cow(x=x, y=y)
            self.cows.append(cow)

    def draw_cows(self, screen):
        for cow in self.cows:
            cow.draw(screen)

    def spawn_trees(self, count):
        for _ in range(count):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            tree = Tree(x=x, y=y)
            self.trees.append(tree)

    def spawn_lakes(self, count):
        for _ in range(count):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            lake = Lake(x=x, y=y)
            self.lakes.append(lake)

    def draw_trees(self, screen):
        for tree in self.trees:
            tree.draw(screen)

    def draw_lakes(self, screen):
        for lake in self.lakes:
            lake.draw(screen)


    def draw(self, screen):
        self.draw_background(screen)
        self.draw_trees(screen)
        self.draw_lakes(screen)
        self.draw_humans(screen)
        self.draw_cows(screen)
