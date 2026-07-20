from __future__ import annotations

import copy
import random
from collections.abc import Callable
from math import hypot
from typing import Any

from game_of_life.ai.scheduler import AIWorker
from game_of_life.config import SimulationConfig
from game_of_life.models import (
    Action,
    ActionType,
    Entity,
    EntityKind,
    Position,
    Profession,
    WorldEvent,
    WorldState,
)

MALE_NAMES = ("James", "John", "Robert", "Michael", "David", "Daniel", "Marco", "Luca")
FEMALE_NAMES = ("Mary", "Sarah", "Emily", "Anna", "Sofia", "Giulia", "Elena", "Marta")
PROFESSIONS = (
    Profession.GATHERER,
    Profession.FARMER,
    Profession.RANCHER,
    Profession.BUILDER,
    Profession.CARPENTER,
    Profession.BLACKSMITH,
    Profession.MERCHANT,
)


class Simulation:
    def __init__(
        self,
        config: SimulationConfig,
        *,
        ai_worker: AIWorker | None = None,
        innovation_manager: Any = None,
        initialize: bool = True,
    ) -> None:
        self.config = config
        self.state = WorldState(config.width, config.height, config.seed)
        self.random = random.Random(config.seed)
        self.ai_worker = ai_worker
        self.innovation_manager = innovation_manager
        self.events: list[WorldEvent] = []
        self._event_sinks: list[Callable[[WorldEvent], None]] = []
        if initialize:
            self.populate()

    def populate(self) -> None:
        for _ in range(self.config.initial_trees):
            self.spawn_resource(EntityKind.TREE)
        for _ in range(self.config.initial_rocks):
            self.spawn_resource(EntityKind.ROCK)
        for _ in range(self.config.initial_lakes):
            self.spawn_resource(EntityKind.LAKE)
        for index in range(self.config.initial_humans):
            human = self.spawn_human()
            human.profession = PROFESSIONS[index % len(PROFESSIONS)]
            human.inventory["food"] = 2
            if human.profession == Profession.BUILDER:
                human.inventory.update({"wood": 10, "stone": 3})
        for _ in range(self.config.initial_cows):
            self.spawn_cow()

    def add_event_sink(self, sink: Callable[[WorldEvent], None]) -> None:
        self._event_sinks.append(sink)

    def emit(
        self,
        event_type: str,
        actor_id: str | None = None,
        target_id: str | None = None,
        **payload: object,
    ) -> None:
        event = WorldEvent(self.state.tick, event_type, actor_id, target_id, dict(payload))
        self.events.append(event)
        if len(self.events) > 300:
            del self.events[:-300]
        for sink in self._event_sinks:
            sink(event)

    def spawn_resource(self, kind: EntityKind) -> Entity:
        prefix = {EntityKind.TREE: "tree", EntityKind.ROCK: "rock", EntityKind.LAKE: "lake"}[kind]
        inventories = {
            EntityKind.TREE: {"wood": 20, "food": 6},
            EntityKind.ROCK: {"stone": 30},
            EntityKind.LAKE: {"water": 10_000},
        }
        entity = Entity(
            id=self.state.allocate_id(prefix),
            kind=kind,
            position=self._random_position(),
            inventory=inventories[kind],
        )
        self.state.entities[entity.id] = entity
        return entity

    def spawn_human(
        self,
        *,
        position: Position | None = None,
        gender: str | None = None,
        age: float | None = None,
    ) -> Entity:
        gender = gender or self.random.choice(("male", "female"))
        names = MALE_NAMES if gender == "male" else FEMALE_NAMES
        human = Entity(
            id=self.state.allocate_id("human"),
            kind=EntityKind.HUMAN,
            position=position or self._random_position(),
            name=self.random.choice(names),
            gender=gender,
            age_years=age if age is not None else self.random.uniform(18, 55),
            speed=2.0,
            attack=self.random.uniform(7, 14),
            defense=self.random.uniform(1, 5),
        )
        self.state.entities[human.id] = human
        self.emit("birth", human.id, name=human.name, kind=human.kind)
        return human

    def spawn_cow(self, *, position: Position | None = None, gender: str | None = None) -> Entity:
        cow = Entity(
            id=self.state.allocate_id("cow"),
            kind=EntityKind.COW,
            position=position or self._random_position(),
            gender=gender or self.random.choice(("male", "female")),
            speed=1.2,
            attack=2,
            defense=1,
            vision=90,
        )
        self.state.entities[cow.id] = cow
        self.emit("birth", cow.id, kind=cow.kind)
        return cow

    def step(self) -> None:
        self.state.tick += 1
        self._apply_ai_results()
        actors = sorted(self.state.living(), key=lambda entity: entity.id)
        for actor in actors:
            if actor.decision_lock_ticks > 0:
                actor.decision_lock_ticks -= 1
            else:
                actor.action = self._choose_local_action(actor)
            self._resolve(actor)
            self._update_needs(actor)
        self._regenerate_resources()
        self._schedule_ai()
        if self.innovation_manager:
            self.innovation_manager.step(self)

    def _choose_local_action(self, actor: Entity) -> Action:
        if actor.kind == EntityKind.COW:
            return self._choose_cow_action(actor)

        if actor.hunger >= 55 and self._inventory_total(actor, ("food", "meat")):
            resource = "food" if actor.inventory.get("food", 0) else "meat"
            return Action(ActionType.EAT, resource=resource, explanation="I need food")
        if actor.thirst >= 55:
            lake = self._nearest(actor, kinds={EntityKind.LAKE})
            return self._approach_or(ActionType.DRINK, actor, lake, 16, "I need water")
        if actor.hunger >= 70:
            tree = self._nearest_with_resource(actor, "food")
            if tree:
                return self._approach_or(
                    ActionType.GATHER, actor, tree, 14, "I need food", resource="food"
                )
            cow = self._nearest(actor, kinds={EntityKind.COW})
            return self._approach_or(ActionType.ATTACK, actor, cow, 14, "I need meat")
        if actor.energy <= 22:
            return Action(ActionType.SLEEP, explanation="I am exhausted")
        if actor.reproduction_drive >= 82 and actor.reproduction_cooldown == 0:
            partner = self._nearest_partner(actor)
            if partner:
                return self._approach_or(ActionType.MATE, actor, partner, 13, "I want a family")
        if actor.social <= 35:
            partner = self._nearest(actor, kinds={EntityKind.HUMAN}, exclude_id=actor.id)
            if partner:
                return self._approach_or(ActionType.TALK, actor, partner, 18, "I need company")
        work = self._choose_work(actor)
        return work or Action(ActionType.IDLE, explanation="No urgent task")

    def _choose_cow_action(self, cow: Entity) -> Action:
        if cow.thirst >= 55:
            lake = self._nearest(cow, kinds={EntityKind.LAKE})
            return self._approach_or(ActionType.DRINK, cow, lake, 16, "drink")
        if cow.hunger >= 48:
            tree = self._nearest_with_resource(cow, "food")
            return self._approach_or(ActionType.GATHER, cow, tree, 13, "graze", resource="food")
        if cow.reproduction_drive >= 88 and cow.reproduction_cooldown == 0:
            partner = self._nearest_partner(cow)
            if partner:
                return self._approach_or(ActionType.MATE, cow, partner, 12, "mate")
        return Action(ActionType.IDLE)

    def _choose_work(self, actor: Entity) -> Action | None:
        dynamic = self._choose_dynamic_work(actor)
        if dynamic:
            return dynamic
        if actor.profession in {Profession.GATHERER, Profession.CARPENTER}:
            tree = self._nearest_with_resource(actor, "wood")
            return self._approach_or(
                ActionType.GATHER, actor, tree, 14, "Gathering wood", resource="wood"
            )
        if actor.profession == Profession.FARMER:
            tree = self._nearest_with_resource(actor, "food")
            return self._approach_or(
                ActionType.GATHER, actor, tree, 14, "Gathering food", resource="food"
            )
        if actor.profession == Profession.BLACKSMITH:
            rock = self._nearest_with_resource(actor, "stone")
            return self._approach_or(
                ActionType.GATHER, actor, rock, 14, "Gathering stone", resource="stone"
            )
        if actor.profession == Profession.BUILDER:
            if actor.inventory.get("wood", 0) >= 10 and actor.inventory.get("stone", 0) >= 3:
                return Action(ActionType.BUILD, resource="house", explanation="Building a home")
            target_resource = "wood" if actor.inventory.get("wood", 0) < 10 else "stone"
            target = self._nearest_with_resource(actor, target_resource)
            return self._approach_or(
                ActionType.GATHER,
                actor,
                target,
                14,
                "Collecting materials",
                resource=target_resource,
            )
        if actor.profession in {Profession.RANCHER, Profession.MERCHANT}:
            other = self._nearest(actor, kinds={EntityKind.HUMAN}, exclude_id=actor.id)
            if other and actor.position.distance_to(other.position) <= 18:
                return Action(ActionType.TRADE, target_id=other.id, explanation="Trading supplies")
        return None

    def _choose_dynamic_work(self, actor: Entity) -> Action | None:
        rules = sorted(self.state.active_rules.values(), key=lambda item: item["id"])
        for rule in rules:
            applies = actor.profession == rule["id"] or (
                rule["category"] in {"recipe", "building"}
                and (not rule.get("workplace") or rule.get("workplace") == actor.profession)
            )
            if not applies:
                continue
            requirements = rule.get("requirements", {})
            missing = next(
                (
                    resource
                    for resource, amount in requirements.items()
                    if actor.inventory.get(resource, 0) < amount
                ),
                None,
            )
            if missing:
                target = self._nearest_with_resource(actor, missing)
                return self._approach_or(
                    ActionType.GATHER,
                    actor,
                    target,
                    14,
                    f"Collecting {missing} for {rule['name']}",
                    resource=missing,
                )
            action = ActionType.BUILD if rule["category"] == "building" else ActionType.WORK
            return Action(action, resource=rule["id"], explanation=f"Working on {rule['name']}")
        return None

    def _resolve(self, actor: Entity) -> None:
        action = actor.action
        target = self.state.entities.get(action.target_id) if action.target_id else None
        if action.kind == ActionType.MOVE:
            self._move(actor, target)
        elif action.kind == ActionType.IDLE:
            self._wander(actor)
        elif action.kind == ActionType.EAT:
            self._eat(actor, action.resource)
        elif action.kind == ActionType.DRINK:
            self._drink(actor, target)
        elif action.kind == ActionType.GATHER:
            self._gather(actor, target, action.resource)
        elif action.kind == ActionType.ATTACK:
            self._attack(actor, target)
        elif action.kind == ActionType.SLEEP:
            actor.energy = min(100, actor.energy + 2.5)
        elif action.kind == ActionType.TALK:
            self._talk(actor, target)
        elif action.kind == ActionType.MATE:
            self._mate(actor, target)
        elif action.kind == ActionType.BUILD:
            self._build(actor, action.resource or "house")
        elif action.kind == ActionType.WORK:
            self._work(actor, action.resource)
        elif action.kind == ActionType.TRADE:
            self._trade(actor, target)

    def _move(self, actor: Entity, target: Entity | None) -> None:
        if not target or not target.alive:
            actor.decision_lock_ticks = 0
            return
        dx = target.position.x - actor.position.x
        dy = target.position.y - actor.position.y
        magnitude = hypot(dx, dy)
        if magnitude:
            actor.position.x = min(
                max(8, actor.position.x + dx / magnitude * actor.speed), self.state.width - 8
            )
            actor.position.y = min(
                max(8, actor.position.y + dy / magnitude * actor.speed), self.state.height - 8
            )

    def _wander(self, actor: Entity) -> None:
        actor.position.x = min(
            max(8, actor.position.x + self.random.uniform(-1, 1) * actor.speed),
            self.state.width - 8,
        )
        actor.position.y = min(
            max(8, actor.position.y + self.random.uniform(-1, 1) * actor.speed),
            self.state.height - 8,
        )

    def _eat(self, actor: Entity, resource: str | None) -> None:
        if resource and actor.inventory.get(resource, 0) > 0:
            actor.inventory[resource] -= 1
            actor.hunger = max(0, actor.hunger - (45 if resource == "meat" else 32))
            self.emit("eat", actor.id, resource=resource)

    def _drink(self, actor: Entity, target: Entity | None) -> None:
        if target and target.kind == EntityKind.LAKE and self._in_range(actor, target, 16):
            actor.thirst = max(0, actor.thirst - 65)
            self.emit("drink", actor.id, target.id)

    def _gather(self, actor: Entity, target: Entity | None, requested: str | None) -> None:
        if not target or not self._in_range(actor, target, 14):
            return
        options = [requested] if requested else list(target.inventory)
        resource = next(
            (item for item in options if item and target.inventory.get(item, 0) > 0), None
        )
        if not resource:
            return
        target.inventory[resource] -= 1
        if actor.kind == EntityKind.COW and resource == "food":
            actor.hunger = max(0, actor.hunger - 40)
        else:
            actor.inventory[resource] = actor.inventory.get(resource, 0) + 1
            actor.skills[actor.profession] = actor.skills.get(actor.profession, 0) + 0.1
        self.emit("gather", actor.id, target.id, resource=resource)

    def _attack(self, actor: Entity, target: Entity | None) -> None:
        if (
            actor.action_cooldown
            or not target
            or not target.alive
            or not self._in_range(actor, target, 14)
        ):
            return
        damage = max(1.0, actor.attack - target.defense)
        target.health -= damage
        actor.action_cooldown = 10
        self.emit("attack", actor.id, target.id, damage=round(damage, 2))
        if target.health <= 0:
            self._kill(target, actor)

    def _kill(self, target: Entity, killer: Entity | None = None) -> None:
        target.alive = False
        if killer and target.kind == EntityKind.COW:
            killer.inventory["meat"] = killer.inventory.get("meat", 0) + 8
        if killer and target.kind == EntityKind.HUMAN:
            for human in self.state.living(EntityKind.HUMAN):
                human.relationships[killer.id] = human.relationships.get(killer.id, 0) - 20
        self.emit("death", killer.id if killer else None, target.id, kind=target.kind)

    def _talk(self, actor: Entity, target: Entity | None) -> None:
        if not target or target.kind != EntityKind.HUMAN or not self._in_range(actor, target, 18):
            return
        actor.social = min(100, actor.social + 18)
        target.social = min(100, target.social + 10)
        actor.relationships[target.id] = min(100, actor.relationships.get(target.id, 0) + 5)
        target.relationships[actor.id] = min(100, target.relationships.get(actor.id, 0) + 4)
        actor.remember(f"Talked with {target.name}")
        target.remember(f"{actor.name} talked with me")
        self.emit("talk", actor.id, target.id)

    def _mate(self, actor: Entity, target: Entity | None) -> None:
        if (
            not target
            or not target.alive
            or target.kind != actor.kind
            or target.gender == actor.gender
            or actor.reproduction_cooldown
            or target.reproduction_cooldown
            or target.reproduction_drive < 70
            or not self._in_range(actor, target, 13)
        ):
            return
        position = Position(
            (actor.position.x + target.position.x) / 2, (actor.position.y + target.position.y) / 2
        )
        if actor.kind == EntityKind.HUMAN:
            child = self.spawn_human(position=position, age=0)
            child.profession = Profession.UNASSIGNED
            actor.relationships[target.id] = actor.relationships.get(target.id, 0) + 10
            target.relationships[actor.id] = target.relationships.get(actor.id, 0) + 10
        else:
            child = self.spawn_cow(position=position)
        actor.reproduction_drive = target.reproduction_drive = 0
        actor.reproduction_cooldown = target.reproduction_cooldown = 2_000
        self.emit("reproduction", actor.id, target.id, child_id=child.id)

    def _build(self, actor: Entity, building_type: str) -> None:
        rule = self.state.active_rules.get(building_type)
        costs = rule.get("requirements", {}) if rule else {"wood": 10, "stone": 3}
        if any(actor.inventory.get(resource, 0) < amount for resource, amount in costs.items()):
            return
        for resource, amount in costs.items():
            actor.inventory[resource] -= amount
        building = Entity(
            id=self.state.allocate_id("building"),
            kind=EntityKind.BUILDING,
            position=Position(actor.position.x + 12, actor.position.y + 12),
            name=building_type.title(),
            building_type=building_type,
            owner_id=actor.id,
        )
        self.state.entities[building.id] = building
        actor.home_id = building.id if building_type == "house" else actor.home_id
        self.emit("build", actor.id, building.id, building_type=building_type)

    def _work(self, actor: Entity, rule_id: str | None) -> None:
        rule = self.state.active_rules.get(rule_id or "")
        if not rule or actor.action_cooldown:
            return
        requirements = rule.get("requirements", {})
        if any(
            actor.inventory.get(resource, 0) < amount for resource, amount in requirements.items()
        ):
            return
        for resource, amount in requirements.items():
            actor.inventory[resource] -= amount
        for resource, amount in rule.get("outputs", {}).items():
            actor.inventory[resource] = actor.inventory.get(resource, 0) + amount
        actor.skills[rule_id or "innovation"] = actor.skills.get(rule_id or "innovation", 0) + 0.2
        duration = max(1, min(100, int(rule.get("duration_ticks", 20))))
        actor.action_cooldown = duration
        actor.decision_lock_ticks = duration
        self.emit("work", actor.id, rule_id=rule_id, outputs=rule.get("outputs", {}))

    def _trade(self, actor: Entity, target: Entity | None) -> None:
        if not target or target.kind != EntityKind.HUMAN or not self._in_range(actor, target, 18):
            return
        surplus = next((key for key, value in sorted(actor.inventory.items()) if value > 3), None)
        if not surplus:
            return
        actor.inventory[surplus] -= 1
        target.inventory[surplus] = target.inventory.get(surplus, 0) + 1
        self.emit("trade", actor.id, target.id, resource=surplus, amount=1)

    def _update_needs(self, actor: Entity) -> None:
        hunger_multiplier = self._world_effect("hunger_rate_multiplier", default=1.0)
        thirst_multiplier = self._world_effect("thirst_rate_multiplier", default=1.0)
        hunger_rate = 0.08 if actor.kind == EntityKind.HUMAN else 0.06
        actor.hunger = min(120, actor.hunger + hunger_rate * hunger_multiplier)
        actor.thirst = min(120, actor.thirst + 0.1 * thirst_multiplier)
        actor.social = max(0, actor.social - (0.025 if actor.kind == EntityKind.HUMAN else 0))
        actor.reproduction_drive = min(100, actor.reproduction_drive + 0.025)
        if actor.action.kind not in {ActionType.SLEEP, ActionType.IDLE}:
            actor.energy = max(0, actor.energy - 0.05)
        if actor.action_cooldown:
            actor.action_cooldown -= 1
        if actor.reproduction_cooldown:
            actor.reproduction_cooldown -= 1
        actor.age_years += 1 / 100_000
        if actor.hunger > 100 or actor.thirst > 100 or actor.energy <= 0:
            actor.health -= 0.15
        elif actor.health < 100 and actor.hunger < 60 and actor.thirst < 60:
            actor.health = min(100, actor.health + 0.02)
        if actor.health <= 0:
            self._kill(actor)

    def _regenerate_resources(self) -> None:
        if self.state.tick % 50:
            return
        for entity in self.state.entities.values():
            if entity.kind == EntityKind.TREE:
                food_rate = max(0, round(self._world_effect("food_regeneration", default=1.0)))
                wood_rate = max(0, round(self._world_effect("wood_regeneration", default=1.0)))
                entity.inventory["food"] = min(6, entity.inventory.get("food", 0) + food_rate)
                entity.inventory["wood"] = min(20, entity.inventory.get("wood", 0) + wood_rate)
            elif entity.kind == EntityKind.ROCK:
                stone_rate = max(0, round(self._world_effect("stone_regeneration", default=0.0)))
                entity.inventory["stone"] = min(30, entity.inventory.get("stone", 0) + stone_rate)

    def _world_effect(self, name: str, *, default: float) -> float:
        value = default
        for rule in self.state.active_rules.values():
            effects = rule.get("effects", {})
            if rule.get("category") == "world_rule" and name in effects:
                value *= float(effects[name])
        return max(0.1, min(5.0, value))

    def _apply_ai_results(self) -> None:
        if not self.ai_worker:
            return
        for result in self.ai_worker.drain():
            entity = self.state.entities.get(result.entity_id)
            if not entity or not entity.alive:
                continue
            if result.error or not result.intent:
                self.emit("ai_error", entity.id, error=result.error or "unknown error")
                continue
            action = result.intent.to_action()
            if action.target_id and action.target_id not in self.state.entities:
                self.emit("ai_rejected", entity.id, reason="unknown target")
                continue
            entity.action = action
            entity.decision_lock_ticks = (
                12 if action.kind in {ActionType.MOVE, ActionType.SLEEP} else 0
            )
            entity.remember(f"I decided to {action.kind}: {action.explanation}")
            self.emit(
                "ai_decision",
                entity.id,
                action.target_id,
                action=action.kind,
                explanation=action.explanation,
            )

    def _schedule_ai(self) -> None:
        interval = self.config.ai.decision_interval_ticks
        if not self.ai_worker or self.state.tick % interval:
            return
        candidates = [
            human
            for human in self.state.living(EntityKind.HUMAN)
            if human.hunger < 55 and human.thirst < 55 and human.energy > 30
        ]
        for human in candidates[: self.config.ai.max_pending_requests]:
            self.ai_worker.submit(copy.deepcopy(human), self.context_for(human))

    def context_for(self, actor: Entity) -> dict[str, object]:
        nearby = sorted(
            (
                {
                    "id": entity.id,
                    "kind": entity.kind,
                    "distance": round(actor.position.distance_to(entity.position), 1),
                }
                for entity in self.state.entities.values()
                if entity.alive
                and entity.id != actor.id
                and actor.position.distance_to(entity.position) <= actor.vision
            ),
            key=lambda item: item["distance"],
        )[:12]
        return {
            "tick": self.state.tick,
            "seed": self.state.seed,
            "nearby": nearby,
            "legal_actions": [item.value for item in ActionType],
        }

    def statistics(self) -> dict[str, int]:
        return {
            "humans": len(self.state.living(EntityKind.HUMAN)),
            "cows": len(self.state.living(EntityKind.COW)),
            "buildings": sum(
                1 for item in self.state.entities.values() if item.kind == EntityKind.BUILDING
            ),
            "events": len(self.events),
        }

    def _approach_or(
        self,
        action: ActionType,
        actor: Entity,
        target: Entity | None,
        distance: float,
        explanation: str,
        resource: str | None = None,
    ) -> Action:
        if not target:
            return Action(ActionType.IDLE, explanation="No target available")
        if self._in_range(actor, target, distance):
            selected_resource = resource
            if action == ActionType.GATHER and not selected_resource:
                selected_resource = next(
                    (key for key, value in target.inventory.items() if value > 0), None
                )
            return Action(action, target.id, resource=selected_resource, explanation=explanation)
        return Action(ActionType.MOVE, target.id, explanation=explanation)

    def _nearest(
        self,
        actor: Entity,
        *,
        kinds: set[EntityKind],
        exclude_id: str | None = None,
    ) -> Entity | None:
        candidates = [
            entity
            for entity in self.state.entities.values()
            if entity.alive and entity.kind in kinds and entity.id != exclude_id
        ]
        return min(
            candidates, key=lambda item: actor.position.distance_to(item.position), default=None
        )

    def _nearest_with_resource(self, actor: Entity, resource: str) -> Entity | None:
        candidates = [
            entity
            for entity in self.state.entities.values()
            if entity.kind in {EntityKind.TREE, EntityKind.ROCK, EntityKind.LAKE}
            and entity.alive
            and entity.inventory.get(resource, 0) > 0
            and entity.id != actor.id
        ]
        return min(
            candidates, key=lambda item: actor.position.distance_to(item.position), default=None
        )

    def _nearest_partner(self, actor: Entity) -> Entity | None:
        candidates = [
            entity
            for entity in self.state.living(actor.kind)
            if entity.id != actor.id
            and entity.gender != actor.gender
            and entity.reproduction_cooldown == 0
            and entity.reproduction_drive >= 70
        ]
        return min(
            candidates, key=lambda item: actor.position.distance_to(item.position), default=None
        )

    def _random_position(self) -> Position:
        return Position(
            self.random.uniform(30, self.state.width - 30),
            self.random.uniform(30, self.state.height - 30),
        )

    @staticmethod
    def _in_range(first: Entity, second: Entity, distance: float) -> bool:
        return first.position.distance_to(second.position) <= distance

    @staticmethod
    def _inventory_total(entity: Entity, resources: tuple[str, ...]) -> int:
        return sum(entity.inventory.get(resource, 0) for resource in resources)
