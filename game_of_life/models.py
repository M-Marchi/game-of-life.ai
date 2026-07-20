from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from math import hypot
from typing import Any


class EntityKind(StrEnum):
    HUMAN = "human"
    COW = "cow"
    TREE = "tree"
    ROCK = "rock"
    LAKE = "lake"
    BUILDING = "building"


class ActionType(StrEnum):
    IDLE = "idle"
    MOVE = "move"
    EAT = "eat"
    DRINK = "drink"
    GATHER = "gather"
    ATTACK = "attack"
    SLEEP = "sleep"
    TALK = "talk"
    MATE = "mate"
    BUILD = "build"
    WORK = "work"
    TRADE = "trade"


class Profession(StrEnum):
    UNASSIGNED = "unassigned"
    GATHERER = "gatherer"
    FARMER = "farmer"
    RANCHER = "rancher"
    BUILDER = "builder"
    CARPENTER = "carpenter"
    BLACKSMITH = "blacksmith"
    MERCHANT = "merchant"


@dataclass(slots=True)
class Position:
    x: float
    y: float

    def distance_to(self, other: Position) -> float:
        return hypot(other.x - self.x, other.y - self.y)


@dataclass(slots=True)
class Action:
    kind: ActionType = ActionType.IDLE
    target_id: str | None = None
    resource: str | None = None
    amount: int = 1
    explanation: str = ""


@dataclass(slots=True)
class Entity:
    id: str
    kind: EntityKind
    position: Position
    name: str = ""
    gender: str | None = None
    age_years: float = 0.0
    health: float = 100.0
    hunger: float = 0.0
    thirst: float = 0.0
    energy: float = 100.0
    social: float = 100.0
    reproduction_drive: float = 0.0
    speed: float = 1.0
    attack: float = 5.0
    defense: float = 1.0
    vision: float = 120.0
    inventory: dict[str, int] = field(default_factory=dict)
    profession: str = Profession.UNASSIGNED
    skills: dict[str, float] = field(default_factory=dict)
    relationships: dict[str, float] = field(default_factory=dict)
    memories: list[str] = field(default_factory=list)
    home_id: str | None = None
    action: Action = field(default_factory=Action)
    action_cooldown: int = 0
    decision_lock_ticks: int = 0
    reproduction_cooldown: int = 0
    resource_amount: int = 0
    resource_capacity: int = 0
    building_type: str | None = None
    owner_id: str | None = None
    alive: bool = True

    @property
    def is_living(self) -> bool:
        return self.kind in {EntityKind.HUMAN, EntityKind.COW}

    def remember(self, text: str, *, limit: int = 20) -> None:
        self.memories.append(text)
        if len(self.memories) > limit:
            del self.memories[: len(self.memories) - limit]


@dataclass(slots=True)
class WorldState:
    width: int
    height: int
    seed: int
    tick: int = 0
    next_id: int = 1
    entities: dict[str, Entity] = field(default_factory=dict)
    active_rules: dict[str, dict[str, Any]] = field(default_factory=dict)

    def allocate_id(self, prefix: str) -> str:
        entity_id = f"{prefix}-{self.next_id:06d}"
        self.next_id += 1
        return entity_id

    def living(self, kind: EntityKind | None = None) -> list[Entity]:
        return [
            entity
            for entity in self.entities.values()
            if entity.alive and entity.is_living and (kind is None or entity.kind == kind)
        ]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WorldEvent:
    tick: int
    event_type: str
    actor_id: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
