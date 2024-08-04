from game_of_life.constants import COW_SPRITE
from game_of_life.data_classes.entity import AliveEntity


class Cow(AliveEntity):
    def __init__(self, x, y, size, gender, meat: int = 10):
        super().__init__(x, y, COW_SPRITE, size, gender)
        self.meat = meat
        self.attack = 0
        self.hunger = 100
        self.life = 100
