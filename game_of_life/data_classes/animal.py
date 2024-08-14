from dataclasses import dataclass, field

import pygame

from game_of_life.constants import COW_SPRITE
from game_of_life.data_classes.action import Action, ActionType
from game_of_life.data_classes.entity import AliveEntity, get_entity_by_id
from game_of_life.data_classes.world_entity import Tree

from loguru import logger as lg


@dataclass
class Cow(AliveEntity):
    meat: int = 10

    def __post_init__(self):
        super().__post_init__()

    def draw(self, screen):
        # Draw the white body of the cow as a rectangle
        pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(self.x, self.y, 2, 2))

        # # Draw a circle around to simulate eyesight
        # pygame.draw.circle(
        #     screen, (255, 255, 255), (self.x + 5, self.y + 5), self.eye_sight, 1
        # )

    def think(self) -> Action:
        entities_dict = self.get_nearby_entities()
        target_distance = 999999

        if self.hunger > 1000 or self.action.action_type == ActionType.FIND_FOOD:
            self.action = self.find_food(entities_dict, target_distance)
        elif self.horny > 100000 or self.action.action_type == ActionType.FIND_PARTNER:
            self.action = self.find_partner(entities_dict, target_distance)
        else:
            self.action = Action(action_type=ActionType.IDLE)

        # lg.debug(f"Cow {self.id} is thinking: {self.action}")
        return self.action

    def find_food(self, entities_dict: dict, target_distance: int) -> Action:
        for entity_id, distance in entities_dict.items():
            entity = get_entity_by_id(self.world.entities, entity_id)
            if isinstance(entity, Tree):
                if distance < 2:
                    lg.info(f"Cow {self.id} is eating")
                    self.hunger = 0
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
            if isinstance(entity, Cow) and entity.gender != self.gender:
                if distance < 2:
                    self.horny = 0
                    new_cow = Cow(x=self.x, y=self.y, world=self.world)
                    self.world.entities.append(new_cow)
                    lg.info(f"New Cow {new_cow.id} was born")
                    return Action(action_type=ActionType.IDLE)
                elif distance < self.eye_sight:
                    if target_distance > distance:
                        target_distance = distance
                        self.speed = 2
                        return Action(action_type=ActionType.MOVE, target_id=entity_id)
        self.speed = 2
        return Action(action_type=ActionType.FIND_PARTNER)

    def idle(self):
        self.speed = 1
        self.update_movement()
