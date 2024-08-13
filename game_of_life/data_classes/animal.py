from dataclasses import dataclass, field

import pygame

from game_of_life.constants import COW_SPRITE
from game_of_life.data_classes.action import Action, ActionType
from game_of_life.data_classes.entity import AliveEntity, get_entity_by_id
from game_of_life.data_classes.world_entity import Tree


@dataclass
class Cow(AliveEntity):
    meat: int = 10

    def __post_init__(self):
        super().__post_init__()

    def draw(self, screen):
        # Draw the white body of the cow as a rectangle
        pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(self.x, self.y, 10, 10))

        # Add black pixels inside the cow
        black_pixels = [
            (self.x + 2, self.y + 2),
            (self.x + 4, self.y + 4),
            (self.x + 6, self.y + 6),
        ]
        for pixel in black_pixels:
            screen.set_at(pixel, (0, 0, 0))

    def think(self) -> Action:
        entities_dict = self.get_nearby_entities()
        target_distance = 999999

        if self.hunger > 10000 or self.action.action_type == ActionType.FIND_FOOD:
            for entity_id, distance in entities_dict.items():
                entity = get_entity_by_id(self.world.entities, entity_id)
                if isinstance(entity, Tree):
                    if distance < 2:
                        self.hunger = 0
                        self.action = Action(action_type=ActionType.IDLE)
                    elif distance < self.eye_sight:
                        if target_distance > distance:
                            target_distance = distance
                            self.speed = 2
                            self.action = Action(
                                action_type=ActionType.MOVE, target_id=entity_id
                            )
                    else:
                        self.speed = 2
                        self.action = Action(action_type=ActionType.FIND_FOOD)
                    break

        elif self.horny > 10000 or self.action.action_type == ActionType.FIND_PARTNER:
            for entity_id, distance in entities_dict.items():
                entity = get_entity_by_id(self.world.entities, entity_id)
                if isinstance(entity, Cow) and entity.gender != self.gender:
                    if distance < 2:
                        self.horny = 0
                        self.action = Action(action_type=ActionType.IDLE)
                    elif distance < self.eye_sight:
                        if target_distance > distance:
                            target_distance = distance
                            self.speed = 2
                            self.action = Action(
                                action_type=ActionType.MOVE, target_id=entity_id
                            )
                    else:
                        self.speed = 2
                        self.action = Action(action_type=ActionType.FIND_PARTNER)
                    break
