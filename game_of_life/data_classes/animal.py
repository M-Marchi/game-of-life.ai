from dataclasses import dataclass, field
from game_of_life.constants import COW_SPRITE
from game_of_life.data_classes.entity import AliveEntity


@dataclass
class Cow(AliveEntity):
    meat: int = 10
    age: int = field(init=False, default=0)
    attack: int = field(init=False, default=0)
    hunger: int = field(init=False, default=100)
    life: int = field(init=False, default=100)
    energy: int = field(init=False, default=100)

    def __post_init__(self):
        super().__post_init__()
