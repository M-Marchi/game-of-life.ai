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
    HELP = "help"
    STEAL = "steal"
    EXPLORE = "explore"
    FORM_FACTION = "form_faction"
    RECRUIT = "recruit"
    DECLARE_WAR = "declare_war"
    MAKE_PEACE = "make_peace"
    INNOVATE = "innovate"
    SABOTAGE = "sabotage"
    REFLECT = "reflect"
    TELL_STORY = "tell_story"
    TEACH = "teach"
    FORGIVE = "forgive"
    STUDY = "study"
    SELF_CARE = "self_care"
    INSPIRE = "inspire"
    BEAUTIFY = "beautify"
    EXPRESS_AFFECTION = "express_affection"


class AgentState(StrEnum):
    AWAKE = "awake"
    SLEEPING = "sleeping"
    DREAMING = "dreaming"


class Profession(StrEnum):
    UNASSIGNED = "unassigned"
    GATHERER = "gatherer"
    FARMER = "farmer"
    RANCHER = "rancher"
    BUILDER = "builder"
    CARPENTER = "carpenter"
    BLACKSMITH = "blacksmith"
    MERCHANT = "merchant"
    SCHOLAR = "scholar"
    HEALER = "healer"
    ARTIST = "artist"
    TEACHER = "teacher"
    DIPLOMAT = "diplomat"
    GUARD = "guard"


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
class Temperament:
    archetype: str = "balanced"
    aggression: float = 0.5
    sociability: float = 0.5
    ambition: float = 0.5
    curiosity: float = 0.5
    empathy: float = 0.5
    creativity: float = 0.5
    risk_tolerance: float = 0.5
    resilience: float = 0.5
    discipline: float = 0.5


@dataclass(slots=True)
class Faction:
    id: str
    name: str
    leader_id: str
    members: list[str] = field(default_factory=list)
    rivals: list[str] = field(default_factory=list)
    ideology: str = "survival"
    founded_tick: int = 0
    victories: int = 0
    defeats: int = 0


@dataclass(slots=True)
class MemoryEntry:
    id: str
    tick: int
    summary: str
    category: str = "event"
    importance: float = 0.5
    emotion: str = "neutral"
    participants: list[str] = field(default_factory=list)
    recall_count: int = 0
    last_recalled_tick: int = 0


@dataclass(slots=True)
class SocialBond:
    target_id: str
    affinity: float = 0.0
    trust: float = 0.0
    attraction: float = 0.0
    respect: float = 0.0
    fear: float = 0.0
    familiarity: float = 0.0
    interaction_count: int = 0
    last_interaction_tick: int = 0
    roles: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        role_priority = (
            "parent",
            "child",
            "sibling",
            "partner",
            "mentor",
            "student",
            "faction_ally",
            "faction_rival",
        )
        role = next((item for item in role_priority if item in self.roles), None)
        if role in {"parent", "child", "sibling"}:
            return "family"
        if self.attraction >= 65 and self.trust >= 35 and self.affinity >= 35:
            return "love"
        if self.affinity <= -55 or self.trust <= -45:
            return "hate"
        if self.fear >= 60 and self.affinity < 0:
            return "fear"
        if role:
            return role
        if self.affinity <= -25:
            return "rival"
        if self.trust >= 45 and self.affinity >= 40:
            return "friend"
        if self.interaction_count > 0 or self.familiarity > 0:
            return "acquaintance"
        return "stranger"


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
    profession_satisfaction: float = 50.0
    skills: dict[str, float] = field(default_factory=dict)
    knowledge: dict[str, float] = field(default_factory=dict)
    values: dict[str, float] = field(default_factory=dict)
    relationships: dict[str, float] = field(default_factory=dict)
    social_bonds: dict[str, SocialBond] = field(default_factory=dict)
    short_term_memory: list[MemoryEntry] = field(default_factory=list)
    long_term_memory: list[MemoryEntry] = field(default_factory=list)
    dreams: list[str] = field(default_factory=list)
    memory_sequence: int = 0
    home_id: str | None = None
    action: Action = field(default_factory=Action)
    action_cooldown: int = 0
    decision_lock_ticks: int = 0
    reproduction_cooldown: int = 0
    resource_amount: int = 0
    resource_capacity: int = 0
    building_type: str | None = None
    owner_id: str | None = None
    temperament: Temperament = field(default_factory=Temperament)
    mood: str = "calm"
    goal: str = "survive and find a place in the world"
    aspirations: list[str] = field(default_factory=list)
    self_awareness: float = 30.0
    growth_drive: float = 50.0
    confidence: float = 50.0
    stress: float = 0.0
    aesthetic_need: float = 20.0
    appearance_style: str = "plain"
    appearance_hue: int = 42
    accessory: str = "none"
    beauty: float = 0.0
    last_vocation_tick: int = -100_000
    faction_id: str | None = None
    reputation: float = 0.0
    last_ai_tick: int = -100_000
    thinking: bool = False
    kills: int = 0
    state: AgentState = AgentState.AWAKE
    sleep_ticks_remaining: int = 0
    reflection_pending: bool = False
    last_dream: str = ""
    alive: bool = True

    @property
    def is_living(self) -> bool:
        return self.kind in {EntityKind.HUMAN, EntityKind.COW}

    def remember(
        self,
        text: str,
        *,
        tick: int = 0,
        category: str = "event",
        importance: float = 0.5,
        emotion: str = "neutral",
        participants: list[str] | None = None,
        limit: int = 16,
    ) -> MemoryEntry:
        self.memory_sequence += 1
        memory = MemoryEntry(
            id=f"{self.id}-m{self.memory_sequence:05d}",
            tick=tick,
            summary=text,
            category=category,
            importance=max(0.0, min(1.0, importance)),
            emotion=emotion,
            participants=list(participants or []),
            last_recalled_tick=tick,
        )
        self.short_term_memory.append(memory)
        if len(self.short_term_memory) > limit:
            overflow = len(self.short_term_memory) - limit
            ranked_for_eviction = sorted(
                self.short_term_memory,
                key=lambda item: (
                    item.importance + (0.15 if item.emotion not in {"neutral", "calm"} else 0),
                    item.tick,
                ),
            )
            evicted_ids = {item.id for item in ranked_for_eviction[:overflow]}
            self.short_term_memory = [
                item for item in self.short_term_memory if item.id not in evicted_ids
            ]
        return memory

    def consolidate_memories(self, tick: int, *, long_term_limit: int = 48) -> tuple[int, int]:
        retained = 0
        forgotten = 0
        for memory in self.short_term_memory:
            emotional = memory.emotion not in {"neutral", "calm"}
            if memory.importance < 0.55 and not emotional:
                forgotten += 1
                continue
            duplicate = next(
                (
                    existing
                    for existing in self.long_term_memory
                    if existing.summary.casefold() == memory.summary.casefold()
                ),
                None,
            )
            if duplicate:
                duplicate.importance = min(1.0, max(duplicate.importance, memory.importance) + 0.05)
                duplicate.recall_count += 1
                duplicate.last_recalled_tick = tick
            else:
                self.long_term_memory.append(memory)
            retained += 1
        self.short_term_memory.clear()
        self.long_term_memory.sort(
            key=lambda memory: (
                memory.importance + min(0.2, memory.recall_count * 0.02),
                memory.tick,
            ),
            reverse=True,
        )
        if len(self.long_term_memory) > long_term_limit:
            forgotten += len(self.long_term_memory) - long_term_limit
            del self.long_term_memory[long_term_limit:]
        return retained, forgotten


@dataclass(slots=True)
class WorldState:
    width: int
    height: int
    seed: int
    tick: int = 0
    next_id: int = 1
    entities: dict[str, Entity] = field(default_factory=dict)
    active_rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)

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
