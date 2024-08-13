from dataclasses import dataclass

import pygame

from game_of_life.data_classes.entity import Entity
from game_of_life.constants import LAKE_SPRITE, TREE_SPRITE


@dataclass
class Lake(Entity):
    def draw(self, screen):
        pygame.draw.circle(screen, (0, 0, 255), (self.x, self.y), 15)


@dataclass
class Tree(Entity):
    def draw(self, screen):
        pygame.draw.polygon(screen, (0, 255, 0), [(self.x, self.y), (self.x + 10, self.y), (self.x + 5, self.y - 10)])
