from dataclasses import dataclass, field
import random
from loguru import logger as lg

import pygame

from typing import Literal, Any

from game_of_life.data_classes.action import Action

GENDER_TYPE = Literal["male", "female"]
ALIGNMENT_TYPE = Literal["good", "neutral", "evil"]


def get_entity_by_id(entities, entity_id):
    for entity in entities:
        if entity.id == entity_id:
            return entity
    return None


@dataclass
class Entity:
    id: str = None
    x: int = 0
    y: int = 0
    world: Any = None

    def __post_init__(self):
        self.id = str(random.randint(0, 1000000))

    def draw(self, screen):
        raise NotImplemented("draw method must be implemented in subclasses")


@dataclass
class AliveEntity(Entity):
    gender: GENDER_TYPE = None
    age: int = 0
    hunger: int = 0
    attack: int = 0
    life: int = 100
    eye_sight: int = 10
    horny: int = 0
    speed: int = 1
    action: Action = field(default_factory=Action)
    alignment: ALIGNMENT_TYPE = "neutral"
    direction: tuple[int, int] = field(
        default_factory=lambda: (random.randint(-1, 1), random.randint(-1, 1))
    )

    def __post_init__(self):
        super().__post_init__()

    def update_movement(self, dx, dy, world_width, world_height):
        # Change direction with a probability of 1/100
        if random.random() < 0.01:
            self.direction = (random.randint(-1, 1), random.randint(-1, 1))

        new_x = self.x + self.direction[0] * dx * self.speed
        new_y = self.y + self.direction[1] * dy * self.speed

        # Ensure the entity does not move outside the screen boundaries
        if 50 <= new_x < world_width - 50:
            self.x = new_x
        else:
            lg.trace(f"Changing direction of {self.id} due to x boundary")
            self.direction = (-self.direction[0], self.direction[1])
            new_x = self.x + self.direction[0] * dx
            self.x = new_x

        if 50 <= new_y < world_height - 50:
            self.y = new_y
        else:
            lg.trace(f"Changing direction of {self.id} due to y boundary")
            self.direction = (self.direction[0], -self.direction[1])
            new_y = self.y + self.direction[1] * dy
            self.y = new_y

    def get_nearby_entities(self) -> dict:
        entity_dict = {}
        for entity in self.world.entities:
            if entity.id == self.id:
                continue
            if (
                abs(entity.x - self.x) < self.eye_sight
                and abs(entity.y - self.y) < self.eye_sight
            ):
                distance = ((entity.x - self.x) ** 2 + (entity.y - self.y) ** 2) ** 0.5
                entity_dict[entity.id] = distance
        return entity_dict
