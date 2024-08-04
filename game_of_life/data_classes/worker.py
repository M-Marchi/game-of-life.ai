from game_of_life.data_classes.human import Human
from game_of_life.constants import (
    GENERIC_MALE_SPRITE,
    GENERIC_FEMALE_SPRITE,
    KNIGHT_SPRITE,
    WIZARD_SPRITE,
    BLACKSMITH_SPRITE,
    FARMER_SPRITE,
)

class GenericMale(Human):
    def __init__(self, x, y, size):
        super().__init__(x, y, GENERIC_MALE_SPRITE, size, "male")

class GenericFemale(Human):
    def __init__(self, x, y, size):
        super().__init__(x, y, GENERIC_FEMALE_SPRITE, size, "female")

class Knight(Human):
    def __init__(self, x, y, size):
        super().__init__(x, y, KNIGHT_SPRITE, size, "male")

class Wizard(Human):
    def __init__(self, x, y, size, gender):
        super().__init__(x, y, WIZARD_SPRITE, size, gender)

class Blacksmith(Human):
    def __init__(self, x, y, size, gender):
        super().__init__(x, y, BLACKSMITH_SPRITE, size, gender)

class Farmer(Human):
    def __init__(self, x, y, size, gender):
        super().__init__(x, y, FARMER_SPRITE, size, gender)