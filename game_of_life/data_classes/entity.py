from dataclasses import dataclass, field
import random
import math
from loguru import logger as lg

import pygame

from typing import Literal, Any

from game_of_life.data_classes.action import Action, ActionType

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
        self.id = self.__class__.__name__ + str(random.randint(0, 100000))

    def draw(self, screen):
        raise NotImplemented("draw method must be implemented in subclasses")


@dataclass
class AliveEntity(Entity):
    iteration: int = 0
    gender: GENDER_TYPE = None
    age: int = 0
    hunger: int = 0
    attack: int = 0
    life: int = 100
    eye_sight: int = 100
    horny: int = 0
    speed: int = 1
    action: Action = field(default_factory=Action)
    alignment: ALIGNMENT_TYPE = "neutral"
    direction: tuple[int, int] = field(
        default_factory=lambda: (random.randint(-1, 1), random.randint(-1, 1))
    )

    def __post_init__(self):
        super().__post_init__()

    def think(self) -> Action:
        raise NotImplemented("think method must be implemented in subclasses")

    def interact(self, action: Action):
        if action.action_type == ActionType.MOVE:
            self.move(action.target_id)
        elif action.action_type == ActionType.FIND_FOOD:
            self.update_movement()
        elif action.action_type == ActionType.FIND_PARTNER:
            self.update_movement()
        elif action.action_type == ActionType.IDLE:
            self.idle()

    def move(self, target_id):
        target = get_entity_by_id(self.world.entities, target_id)
        if target:
            direction = (target.x - self.x, target.y - self.y)
            magnitude = (direction[0] ** 2 + direction[1] ** 2) ** 0.5
            if magnitude != 0:
                direction = (direction[0] / magnitude, direction[1] / magnitude)
            self.update_movement(direction=direction)
        else:
            lg.error(f"Target {target_id} not found")
            self.action = Action(action_type=ActionType.IDLE)

    def update_movement(
        self, dx: int = 1, dy: int = 1, direction: tuple[float, float] = None
    ):
        if direction is None:
            # Change direction with a probability of 1/100
            if random.random() < 0.01:
                self.direction = (random.uniform(-1, 1), random.uniform(-1, 1))
                magnitude = (self.direction[0] ** 2 + self.direction[1] ** 2) ** 0.5
                if magnitude != 0:
                    self.direction = (
                        self.direction[0] / magnitude,
                        self.direction[1] / magnitude,
                    )
        else:
            self.direction = direction

        new_x = self.x + self.direction[0] * dx * self.speed
        new_y = self.y + self.direction[1] * dy * self.speed

        # Ensure the entity does not move outside the screen boundaries
        if 50 <= new_x < self.world.width - 50:
            self.x = new_x
        else:
            lg.trace(f"Changing direction of {self.id} due to x boundary")
            self.direction = (-self.direction[0], self.direction[1])
            self.x += self.direction[0] * dx * self.speed

        if 50 <= new_y < self.world.height - 50:
            self.y = new_y
        else:
            lg.trace(f"Changing direction of {self.id} due to y boundary")
            self.direction = (self.direction[0], -self.direction[1])
            self.y += self.direction[1] * dy * self.speed

    def idle(self):
        NotImplementedError("idle method must be implemented in subclasses")

    def find_food(self, entities_dict: dict, target_distance: int):
        NotImplementedError("find_food method must be implemented in subclasses")

    def find_partner(self, entities_dict: dict, target_distance: int):
        NotImplementedError("find_partner method must be implemented in subclasses")

    def update_stats(self):
        self.hunger += 1
        self.horny += 1
        self.iteration += 1

        if self.hunger > 10000:
            self.life -= 1
        else:
            self.life += 1

        self.age = self.iteration // 10000

        death_probability = random.randint(self.age * 1000, 120000)
        if death_probability == 120000:
            self.life = 0
            self.world.remove_entity_by_id(self.id)
            lg.warning(f"{self.id} died")

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
