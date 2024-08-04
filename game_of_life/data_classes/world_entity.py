from game_of_life.data_classes.entity import Entity
from game_of_life.constants import LAKE_SPRITE, TREE_SPRITE


class Lake(Entity):
    def __init__(self, x, y, size):
        super().__init__(x, y, LAKE_SPRITE, size)


class Tree(Entity):
    def __init__(self, x, y, size):
        super().__init__(x, y, TREE_SPRITE, size)