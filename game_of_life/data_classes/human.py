# game_of_life/data_classes/human.py
from dataclasses import dataclass
from game_of_life.data_classes.entity import AliveEntity


@dataclass
class Human(AliveEntity):
    backstory: str = ""

