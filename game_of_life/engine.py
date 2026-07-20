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
    Faction,
    Position,
    Profession,
    Temperament,
    WorldEvent,
    WorldState,
)

MALE_NAMES = ("James", "John", "Robert", "Michael", "David", "Daniel", "Marco", "Luca")
FEMALE_NAMES = ("Mary", "Sarah", "Emily", "Anna", "Sofia", "Giulia", "Elena", "Marta")
FACTION_NOUNS = ("Dawn", "Iron", "River", "Oak", "Ember", "Horizon", "Stone", "Free")
PROFESSIONS = (
    Profession.GATHERER,
    Profession.FARMER,
    Profession.RANCHER,
    Profession.BUILDER,
    Profession.CARPENTER,
    Profession.BLACKSMITH,
    Profession.MERCHANT,
)
BUILTIN_RECIPES = {
    "basic_tools": {
        "id": "basic_tools",
        "name": "Basic tools",
        "category": "recipe",
        "requirements": {"wood": 1, "stone": 2},
        "outputs": {"tools": 1},
        "duration_ticks": 35,
    }
}


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
            temperament=self._random_temperament(),
        )
        human.goal = self._initial_goal(human.temperament)
        human.attack += human.temperament.aggression * 4
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
        self._update_factions()
        self._trigger_world_event()
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
        personality_action = self._choose_personality_action(actor)
        if personality_action:
            return personality_action
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

    def _choose_personality_action(self, actor: Entity) -> Action | None:
        if actor.age_years < 16:
            return None
        temperament = actor.temperament
        strongest_drive = max(
            temperament.aggression,
            temperament.sociability,
            temperament.ambition,
            temperament.curiosity,
            temperament.empathy,
            temperament.creativity,
            temperament.risk_tolerance,
        )
        if self.random.random() > 0.001 + strongest_drive * 0.002:
            return None

        faction = self.state.factions.get(actor.faction_id or "")
        if not faction and temperament.ambition > 0.68:
            population = len(self.state.living(EntityKind.HUMAN))
            faction_limit = min(8, max(2, population // 15))
            if len(self.state.factions) < faction_limit:
                return Action(ActionType.FORM_FACTION, explanation="I will gather people around me")

        if faction and faction.leader_id == actor.id:
            recruit = self._nearest(
                actor,
                kinds={EntityKind.HUMAN},
                exclude_id=actor.id,
                predicate=lambda entity: entity.faction_id is None,
            )
            if recruit and temperament.ambition + temperament.sociability > 1.15:
                actor.decision_lock_ticks = 80
                return Action(ActionType.RECRUIT, recruit.id, explanation="Our faction must grow")

            rival = self._nearest_other_faction_member(actor)
            if rival and temperament.aggression > 0.72 and rival.faction_id not in faction.rivals:
                actor.decision_lock_ticks = 100
                return Action(
                    ActionType.DECLARE_WAR,
                    rival.id,
                    explanation="Their faction stands in our way",
                )
            enemy = self._nearest_rival(actor)
            if enemy and temperament.empathy > 0.78 and self.random.random() < 0.35:
                actor.decision_lock_ticks = 100
                return Action(
                    ActionType.MAKE_PEACE, enemy.id, explanation="This war costs too much"
                )

        enemy = self._nearest_rival(actor)
        if enemy and temperament.aggression + temperament.risk_tolerance > 0.95:
            actor.decision_lock_ticks = 120
            return Action(ActionType.ATTACK, enemy.id, explanation="I will fight for my faction")

        nearby = self._nearby_humans(actor, 60)
        disliked = next(
            (human for human in nearby if actor.relationships.get(human.id, 0) < -10), None
        )
        if disliked and temperament.aggression > 0.68:
            actor.decision_lock_ticks = 60
            action = ActionType.ATTACK if temperament.aggression > 0.82 else ActionType.STEAL
            return Action(action, disliked.id, explanation="I act on an old grievance")

        needy = next((human for human in nearby if human.hunger > 65 or human.thirst > 65), None)
        if needy and temperament.empathy > 0.68 and actor.inventory:
            actor.decision_lock_ticks = 50
            return Action(ActionType.HELP, needy.id, explanation="I will help someone in need")

        if nearby and temperament.risk_tolerance > 0.78 and temperament.empathy < 0.42:
            target = self.random.choice(nearby)
            actor.decision_lock_ticks = 50
            return Action(
                ActionType.STEAL, target.id, explanation="I can profit from their supplies"
            )

        if temperament.creativity > 0.72:
            return Action(
                ActionType.INNOVATE, explanation="I have an idea that could change society"
            )
        if temperament.curiosity > 0.65:
            return Action(ActionType.EXPLORE, explanation="I want to discover a new place")
        if nearby and temperament.sociability > 0.65:
            target = self.random.choice(nearby)
            actor.decision_lock_ticks = 50
            return Action(ActionType.TALK, target.id, explanation="I want to know them better")
        return None

    def _choose_work(self, actor: Entity) -> Action | None:
        dynamic = self._choose_dynamic_work(actor)
        if dynamic:
            return dynamic
        if actor.profession in {Profession.GATHERER, Profession.CARPENTER}:
            if (
                self._settlement_resource_total("wood")
                >= len(self.state.living(EntityKind.HUMAN)) * 7
            ):
                return None
            tree = self._nearest_with_resource(actor, "wood")
            return self._approach_or(
                ActionType.GATHER, actor, tree, 14, "Gathering wood", resource="wood"
            )
        if actor.profession == Profession.FARMER:
            if (
                self._settlement_resource_total("food")
                >= len(self.state.living(EntityKind.HUMAN)) * 4
            ):
                return None
            tree = self._nearest_with_resource(actor, "food")
            return self._approach_or(
                ActionType.GATHER, actor, tree, 14, "Gathering food", resource="food"
            )
        if actor.profession == Profession.BLACKSMITH:
            population = max(1, len(self.state.living(EntityKind.HUMAN)))
            if self._settlement_resource_total("tools") < max(2, population // 3):
                requirements = BUILTIN_RECIPES["basic_tools"]["requirements"]
                missing = next(
                    (
                        resource
                        for resource, amount in requirements.items()
                        if actor.inventory.get(resource, 0) < amount
                    ),
                    None,
                )
                if not missing:
                    return Action(
                        ActionType.WORK,
                        resource="basic_tools",
                        explanation="Forging tools for the settlement",
                    )
                target = self._nearest_with_resource(actor, missing)
                return self._approach_or(
                    ActionType.GATHER,
                    actor,
                    target,
                    14,
                    f"Gathering {missing} for tools",
                    resource=missing,
                )
            return None
        if actor.profession == Profession.RANCHER:
            population = max(1, len(self.state.living(EntityKind.HUMAN)))
            if self._settlement_resource_total("meat") < population // 2:
                cow = self._nearest(actor, kinds={EntityKind.COW})
                return self._approach_or(
                    ActionType.ATTACK, actor, cow, 14, "Hunting livestock for meat"
                )
        if actor.profession == Profession.BUILDER:
            homeless = [
                human
                for human in self.state.living(EntityKind.HUMAN)
                if not human.home_id and human.age_years >= 16
            ]
            existing_types = {
                entity.building_type
                for entity in self.state.entities.values()
                if entity.alive and entity.kind == EntityKind.BUILDING
            }
            if homeless:
                desired_building = "house"
            elif "workshop" not in existing_types:
                desired_building = "workshop"
            elif self.state.factions and "market" not in existing_types:
                desired_building = "market"
            else:
                return None
            if actor.inventory.get("wood", 0) >= 10 and actor.inventory.get("stone", 0) >= 3:
                return Action(
                    ActionType.BUILD,
                    resource=desired_building,
                    explanation=f"Building a {desired_building}",
                )
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
        elif action.kind == ActionType.HELP:
            self._help(actor, target)
        elif action.kind == ActionType.STEAL:
            self._steal(actor, target)
        elif action.kind == ActionType.EXPLORE:
            self._explore(actor)
        elif action.kind == ActionType.FORM_FACTION:
            self._form_faction(actor)
        elif action.kind == ActionType.RECRUIT:
            self._recruit(actor, target)
        elif action.kind == ActionType.DECLARE_WAR:
            self._declare_war(actor, target)
        elif action.kind == ActionType.MAKE_PEACE:
            self._make_peace(actor, target)
        elif action.kind == ActionType.INNOVATE:
            self._innovate(actor)
        elif action.kind == ActionType.SABOTAGE:
            self._sabotage(actor, target)

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
        if target and target.kind == EntityKind.LAKE and not self._in_range(actor, target, 16):
            self._move(actor, target)
            return
        if target and target.kind == EntityKind.LAKE:
            actor.thirst = max(0, actor.thirst - 65)
            if actor.kind == EntityKind.HUMAN:
                actor.decision_lock_ticks = 0
            self.emit("drink", actor.id, target.id)

    def _gather(self, actor: Entity, target: Entity | None, requested: str | None) -> None:
        if target and not self._in_range(actor, target, 14):
            self._move(actor, target)
            return
        if not target:
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
            actor.decision_lock_ticks = 0
        self.emit("gather", actor.id, target.id, resource=resource)

    def _attack(self, actor: Entity, target: Entity | None) -> None:
        if target and target.alive and not self._in_range(actor, target, 14):
            self._move(actor, target)
            return
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
            killer.kills += 1
            killer.reputation -= 6
            for human in self.state.living(EntityKind.HUMAN):
                human.relationships[killer.id] = human.relationships.get(killer.id, 0) - 20
            killer_faction = self.state.factions.get(killer.faction_id or "")
            target_faction = self.state.factions.get(target.faction_id or "")
            if killer_faction and target_faction and target_faction.id in killer_faction.rivals:
                killer_faction.victories += 1
                target_faction.defeats += 1
                for resource, amount in list(target.inventory.items()):
                    captured = amount // 2
                    if captured:
                        killer.inventory[resource] = killer.inventory.get(resource, 0) + captured
        self.emit("death", killer.id if killer else None, target.id, kind=target.kind)

    def _talk(self, actor: Entity, target: Entity | None) -> None:
        if target and target.kind == EntityKind.HUMAN and not self._in_range(actor, target, 18):
            self._move(actor, target)
            return
        if not target or target.kind != EntityKind.HUMAN:
            return
        compatibility = 1 - abs(actor.temperament.empathy - target.temperament.empathy)
        argumentative = (
            actor.temperament.aggression + target.temperament.aggression > 1.45
            and self.random.random() < 0.18
        )
        relationship_change = -12 if argumentative else 2 + round(compatibility * 5)
        actor.social = min(100, actor.social + 18)
        target.social = min(100, target.social + 10)
        actor.relationships[target.id] = max(
            -100, min(100, actor.relationships.get(target.id, 0) + relationship_change)
        )
        target.relationships[actor.id] = max(
            -100, min(100, target.relationships.get(actor.id, 0) + relationship_change)
        )
        if argumentative:
            actor.mood = target.mood = "angry"
            self.emit("argument", actor.id, target.id)
        elif compatibility > 0.75:
            actor.mood = target.mood = "hopeful"
        actor.remember(f"Talked with {target.name}")
        target.remember(f"{actor.name} talked with me")
        actor.decision_lock_ticks = 0
        self.emit("talk", actor.id, target.id, relationship_change=relationship_change)

    def _mate(self, actor: Entity, target: Entity | None) -> None:
        if target and target.alive and not self._in_range(actor, target, 13):
            self._move(actor, target)
            return
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
            child.temperament = self._inherit_temperament(actor, target)
            child.goal = self._initial_goal(child.temperament)
            child.faction_id = actor.faction_id if actor.faction_id == target.faction_id else None
            if child.faction_id:
                self.state.factions[child.faction_id].members.append(child.id)
            actor.relationships[target.id] = actor.relationships.get(target.id, 0) + 10
            target.relationships[actor.id] = target.relationships.get(actor.id, 0) + 10
        else:
            child = self.spawn_cow(position=position)
        actor.reproduction_drive = target.reproduction_drive = 0
        actor.reproduction_cooldown = target.reproduction_cooldown = 2_000
        actor.decision_lock_ticks = 0
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
        resident_id = None
        if building_type == "house":
            homeless = [
                human
                for human in self.state.living(EntityKind.HUMAN)
                if not human.home_id and human.age_years >= 16
            ]
            resident = min(
                homeless,
                key=lambda human: actor.position.distance_to(human.position),
                default=actor,
            )
            resident.home_id = building.id
            building.owner_id = resident.id
            resident_id = resident.id
        self.emit(
            "build",
            actor.id,
            building.id,
            building_type=building_type,
            resident_id=resident_id,
        )

    def _work(self, actor: Entity, rule_id: str | None) -> None:
        rule = self.state.active_rules.get(rule_id or "") or BUILTIN_RECIPES.get(rule_id or "")
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
        if actor.action_cooldown:
            return
        if target and target.kind == EntityKind.HUMAN and not self._in_range(actor, target, 18):
            self._move(actor, target)
            return
        if not target or target.kind != EntityKind.HUMAN:
            return
        surplus = next((key for key, value in sorted(actor.inventory.items()) if value > 3), None)
        if not surplus:
            return
        actor.inventory[surplus] -= 1
        target.inventory[surplus] = target.inventory.get(surplus, 0) + 1
        actor.action_cooldown = 50
        actor.decision_lock_ticks = 0
        self.emit("trade", actor.id, target.id, resource=surplus, amount=1)

    def _help(self, actor: Entity, target: Entity | None) -> None:
        if not self._approach_interaction(actor, target, 18, EntityKind.HUMAN):
            return
        assert target is not None
        wanted = "food" if target.hunger >= target.thirst else "water"
        resource = (
            wanted
            if actor.inventory.get(wanted, 0)
            else next((item for item, amount in actor.inventory.items() if amount > 1), None)
        )
        if not resource:
            actor.decision_lock_ticks = 0
            return
        actor.inventory[resource] -= 1
        target.inventory[resource] = target.inventory.get(resource, 0) + 1
        actor.relationships[target.id] = actor.relationships.get(target.id, 0) + 8
        target.relationships[actor.id] = target.relationships.get(actor.id, 0) + 12
        actor.reputation = min(100, actor.reputation + 2)
        actor.mood = "hopeful"
        target.remember(f"{actor.name} helped me with {resource}")
        actor.decision_lock_ticks = 0
        self.emit("help", actor.id, target.id, resource=resource)

    def _steal(self, actor: Entity, target: Entity | None) -> None:
        if not self._approach_interaction(actor, target, 14, EntityKind.HUMAN):
            return
        assert target is not None
        resource = next(
            (item for item, amount in sorted(target.inventory.items()) if amount > 0), None
        )
        if not resource:
            actor.decision_lock_ticks = 0
            return
        target.inventory[resource] -= 1
        actor.inventory[resource] = actor.inventory.get(resource, 0) + 1
        detected = self.random.random() > actor.temperament.risk_tolerance * 0.55
        if detected:
            target.relationships[actor.id] = target.relationships.get(actor.id, 0) - 28
            actor.relationships[target.id] = actor.relationships.get(target.id, 0) - 8
            actor.reputation = max(-100, actor.reputation - 5)
            target.mood = "angry"
            target.remember(f"{actor.name} stole {resource} from me")
        actor.mood = "proud" if not detected else "afraid"
        actor.decision_lock_ticks = 0
        self.emit("steal", actor.id, target.id, resource=resource, detected=detected)

    def _explore(self, actor: Entity) -> None:
        actor.position.x = min(
            max(8, actor.position.x + self.random.uniform(-25, 25)), self.state.width - 8
        )
        actor.position.y = min(
            max(8, actor.position.y + self.random.uniform(-25, 25)), self.state.height - 8
        )
        actor.mood = "curious"
        actor.remember("I explored an unfamiliar part of the world")
        self.emit("explore", actor.id)

    def _form_faction(self, actor: Entity) -> None:
        if actor.kind != EntityKind.HUMAN or actor.faction_id or actor.age_years < 16:
            return
        if len(self.state.factions) >= 8:
            return
        faction_id = self.state.allocate_id("faction")
        noun = self.random.choice(FACTION_NOUNS)
        faction = Faction(
            id=faction_id,
            name=f"{noun} {actor.temperament.archetype.title()}s",
            leader_id=actor.id,
            members=[actor.id],
            ideology=actor.temperament.archetype,
            founded_tick=self.state.tick,
        )
        self.state.factions[faction.id] = faction
        actor.faction_id = faction.id
        actor.reputation += 8
        actor.mood = "proud"
        actor.goal = f"make {faction.name} influential"
        self.emit("faction_founded", actor.id, faction_id=faction.id, name=faction.name)

    def _recruit(self, actor: Entity, target: Entity | None) -> None:
        if not self._approach_interaction(actor, target, 18, EntityKind.HUMAN):
            return
        assert target is not None
        faction = self.state.factions.get(actor.faction_id or "")
        if not faction or target.faction_id:
            actor.decision_lock_ticks = 0
            return
        relationship = target.relationships.get(actor.id, 0)
        chance = 0.35 + relationship / 200 + actor.reputation / 300
        chance += target.temperament.sociability * 0.2
        if self.random.random() < chance:
            target.faction_id = faction.id
            faction.members.append(target.id)
            target.goal = f"help {faction.name} prosper"
            target.remember(f"I joined {faction.name} at {actor.name}'s invitation")
            self.emit("recruit", actor.id, target.id, faction_id=faction.id, accepted=True)
        else:
            target.relationships[actor.id] = relationship - 3
            self.emit("recruit", actor.id, target.id, faction_id=faction.id, accepted=False)
        actor.decision_lock_ticks = 0

    def _declare_war(self, actor: Entity, target: Entity | None) -> None:
        if not target or target.kind != EntityKind.HUMAN:
            return
        own = self.state.factions.get(actor.faction_id or "")
        other = self.state.factions.get(target.faction_id or "")
        if not own or not other or own.id == other.id or own.leader_id != actor.id:
            return
        if other.id not in own.rivals:
            own.rivals.append(other.id)
        if own.id not in other.rivals:
            other.rivals.append(own.id)
        actor.mood = "angry"
        actor.goal = f"defeat {other.name}"
        self.emit("war_declared", actor.id, target.id, attacker=own.id, defender=other.id)
        actor.decision_lock_ticks = 0

    def _make_peace(self, actor: Entity, target: Entity | None) -> None:
        if not self._approach_interaction(actor, target, 20, EntityKind.HUMAN):
            return
        assert target is not None
        own = self.state.factions.get(actor.faction_id or "")
        other = self.state.factions.get(target.faction_id or "")
        if not own or not other or own.leader_id != actor.id or other.id not in own.rivals:
            actor.decision_lock_ticks = 0
            return
        acceptance = target.temperament.empathy + actor.reputation / 100
        if self.random.random() < max(0.15, min(0.85, acceptance / 2)):
            own.rivals = [item for item in own.rivals if item != other.id]
            other.rivals = [item for item in other.rivals if item != own.id]
            self.emit("peace_made", actor.id, target.id, factions=[own.id, other.id])
        else:
            self.emit("peace_rejected", actor.id, target.id, factions=[own.id, other.id])
        actor.decision_lock_ticks = 0

    def _innovate(self, actor: Entity) -> None:
        if not self.innovation_manager:
            return
        submitted = self.innovation_manager.request_from_actor(self, actor)
        if submitted:
            actor.mood = "curious"
            actor.remember("I proposed an innovation to change the settlement")
            self.emit("innovation_proposed", actor.id, goal=actor.goal)

    def _sabotage(self, actor: Entity, target: Entity | None) -> None:
        if not self._approach_interaction(actor, target, 14, EntityKind.BUILDING):
            return
        assert target is not None
        damage = 8 + actor.temperament.aggression * 12
        target.health -= damage
        actor.reputation = max(-100, actor.reputation - 4)
        self.emit("sabotage", actor.id, target.id, damage=round(damage, 1))
        if target.health <= 0:
            target.alive = False
            self.emit("building_destroyed", actor.id, target.id)
        actor.decision_lock_ticks = 0

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

    def _update_factions(self) -> None:
        if self.state.tick % 50:
            return
        for faction_id, faction in list(self.state.factions.items()):
            faction.members = [
                member_id
                for member_id in faction.members
                if (member := self.state.entities.get(member_id)) and member.alive
            ]
            if not faction.members:
                del self.state.factions[faction_id]
                for other in self.state.factions.values():
                    other.rivals = [item for item in other.rivals if item != faction_id]
                self.emit("faction_dissolved", faction_id=faction_id)
                continue
            if faction.leader_id not in faction.members:
                faction.leader_id = max(
                    faction.members,
                    key=lambda member_id: self.state.entities[member_id].temperament.ambition,
                )
                self.emit("leader_changed", faction.leader_id, faction_id=faction.id)

        humans = self.state.living(EntityKind.HUMAN)
        desired_factions = min(5, len(humans) // 12)
        if self.state.tick % 800 == 0 and len(self.state.factions) < desired_factions:
            unaffiliated = [
                human for human in humans if not human.faction_id and human.age_years >= 16
            ]
            if unaffiliated:
                founder = max(unaffiliated, key=lambda human: human.temperament.ambition)
                self._form_faction(founder)

        wars = sum(len(faction.rivals) for faction in self.state.factions.values()) // 2
        if self.state.tick % 600 == 0 and not wars and len(self.state.factions) >= 2:
            factions = sorted(
                self.state.factions.values(),
                key=lambda faction: self.state.entities[faction.leader_id].temperament.aggression,
                reverse=True,
            )
            attacker, defender = factions[:2]
            leader = self.state.entities[attacker.leader_id]
            target = self.state.entities[defender.leader_id]
            tension = leader.temperament.aggression + leader.temperament.ambition
            if tension > 0.9 or self.random.random() < 0.25:
                self._declare_war(leader, target)

    def _trigger_world_event(self) -> None:
        interval = self.config.world_event_interval_ticks
        if not interval or not self.state.tick or self.state.tick % interval:
            return
        event_type = self.random.choices(
            ("drought", "wildfire", "epidemic", "harvest", "mineral_boom"),
            weights=(3, 2, 2, 2, 1),
            k=1,
        )[0]
        if event_type == "drought":
            for tree in (
                item for item in self.state.entities.values() if item.kind == EntityKind.TREE
            ):
                tree.inventory["food"] = tree.inventory.get("food", 0) // 2
            for living in self.state.living():
                living.thirst = min(120, living.thirst + 18)
        elif event_type == "wildfire":
            trees = [item for item in self.state.entities.values() if item.kind == EntityKind.TREE]
            for tree in self.random.sample(trees, k=min(len(trees), max(4, len(trees) // 8))):
                tree.inventory["food"] = 0
                tree.inventory["wood"] = max(0, tree.inventory.get("wood", 0) // 3)
        elif event_type == "epidemic":
            humans = self.state.living(EntityKind.HUMAN)
            for human in self.random.sample(humans, k=min(len(humans), max(2, len(humans) // 5))):
                human.health -= self.random.uniform(8, 22)
                human.mood = "afraid"
        elif event_type == "harvest":
            for tree in (
                item for item in self.state.entities.values() if item.kind == EntityKind.TREE
            ):
                tree.inventory["food"] = 10
        elif event_type == "mineral_boom":
            for _ in range(max(2, len(self.state.living(EntityKind.HUMAN)) // 15)):
                self.spawn_resource(EntityKind.ROCK)
        self.emit("world_event", event=event_type)

    def _apply_ai_results(self) -> None:
        if not self.ai_worker:
            return
        for result in self.ai_worker.drain():
            entity = self.state.entities.get(result.entity_id)
            if not entity or not entity.alive:
                continue
            if result.error or not result.intent:
                entity.thinking = False
                self.emit("ai_error", entity.id, error=result.error or "unknown error")
                continue
            action = result.intent.to_action()
            target = self.state.entities.get(action.target_id or "")
            if action.target_id and (not target or not target.alive):
                entity.thinking = False
                self.emit("ai_rejected", entity.id, action.target_id, reason="invalid target")
                continue
            invalid_reason = self._validate_action(entity, action, target)
            if invalid_reason:
                entity.thinking = False
                self.emit(
                    "ai_rejected",
                    entity.id,
                    action.target_id,
                    action=action.kind,
                    reason=invalid_reason,
                )
                continue
            entity.action = action
            entity.thinking = False
            entity.goal = result.intent.goal or entity.goal
            entity.mood = result.intent.mood
            entity.decision_lock_ticks = 90 if action.target_id else 1
            if action.kind == ActionType.SLEEP:
                entity.decision_lock_ticks = 12
            entity.remember(f"I decided to {action.kind}: {action.explanation}")
            self.emit(
                "ai_decision",
                entity.id,
                action.target_id,
                action=action.kind,
                explanation=action.explanation,
                goal=entity.goal,
                mood=entity.mood,
            )

    def _schedule_ai(self) -> None:
        interval = self.config.ai.decision_interval_ticks
        if not self.ai_worker or self.state.tick % interval:
            return
        candidates = [
            human
            for human in self.state.living(EntityKind.HUMAN)
            if human.hunger < 78
            and human.thirst < 78
            and human.energy > 20
            and not human.thinking
            and self.state.tick - human.last_ai_tick >= self.config.ai.decision_cooldown_ticks
        ]
        candidates.sort(key=lambda human: (human.last_ai_tick, human.id))
        capacity = max(0, self.config.ai.max_pending_requests - self.ai_worker.pending_count)
        for human in candidates[:capacity]:
            if self.ai_worker.submit(copy.deepcopy(human), self.context_for(human)):
                human.thinking = True
                human.last_ai_tick = self.state.tick
                self.emit("ai_thinking", human.id, goal=human.goal)

    def _validate_action(self, actor: Entity, action: Action, target: Entity | None) -> str | None:
        human_targets = {
            ActionType.TALK,
            ActionType.MATE,
            ActionType.TRADE,
            ActionType.HELP,
            ActionType.STEAL,
            ActionType.RECRUIT,
            ActionType.DECLARE_WAR,
            ActionType.MAKE_PEACE,
        }
        if action.kind in human_targets and (not target or target.kind != EntityKind.HUMAN):
            return "action requires a human target"
        if action.kind == ActionType.DRINK and (not target or target.kind != EntityKind.LAKE):
            return "drink requires a lake target"
        if action.kind == ActionType.GATHER and (
            not target or target.kind not in {EntityKind.TREE, EntityKind.ROCK, EntityKind.LAKE}
        ):
            return "gather requires a resource target"
        if action.kind == ActionType.ATTACK and (
            not target or target.kind not in {EntityKind.HUMAN, EntityKind.COW}
        ):
            return "attack requires a living target"
        if action.kind == ActionType.SABOTAGE and (
            not target or target.kind != EntityKind.BUILDING
        ):
            return "sabotage requires a building target"
        faction = self.state.factions.get(actor.faction_id or "")
        target_faction = self.state.factions.get(target.faction_id or "") if target else None
        if action.kind == ActionType.FORM_FACTION and actor.faction_id:
            return "actor already belongs to a faction"
        if action.kind == ActionType.RECRUIT and (
            not faction or faction.leader_id != actor.id or (target and target.faction_id)
        ):
            return "only a leader can recruit an unaffiliated human"
        if action.kind == ActionType.DECLARE_WAR and (
            not faction
            or faction.leader_id != actor.id
            or not target_faction
            or target_faction.id == faction.id
            or target_faction.id in faction.rivals
        ):
            return "war requires a leader and a non-rival foreign faction"
        if action.kind == ActionType.MAKE_PEACE and (
            not faction
            or faction.leader_id != actor.id
            or not target_faction
            or target_faction.id not in faction.rivals
        ):
            return "peace requires a leader and a current rival faction"
        if action.kind == ActionType.INNOVATE and not self.innovation_manager:
            return "innovation service unavailable"
        return None

    def context_for(self, actor: Entity) -> dict[str, object]:
        nearby_entities = [
            entity
            for entity in self.state.entities.values()
            if entity.alive
            and entity.id != actor.id
            and actor.position.distance_to(entity.position) <= actor.vision
        ]
        nearby = sorted(
            (
                {
                    "id": entity.id,
                    "kind": entity.kind,
                    "name": entity.name,
                    "distance": round(actor.position.distance_to(entity.position), 1),
                    "profession": entity.profession if entity.kind == EntityKind.HUMAN else None,
                    "faction_id": entity.faction_id,
                    "relationship": round(actor.relationships.get(entity.id, 0), 1),
                    "health": round(entity.health, 1),
                    "inventory": entity.inventory if entity.kind == EntityKind.HUMAN else {},
                    "building_type": entity.building_type,
                }
                for entity in nearby_entities
            ),
            key=lambda item: item["distance"],
        )[:20]
        factions = [
            {
                "id": faction.id,
                "name": faction.name,
                "leader_id": faction.leader_id,
                "members": len(faction.members),
                "rivals": faction.rivals,
                "ideology": faction.ideology,
            }
            for faction in self.state.factions.values()
        ]
        return {
            "tick": self.state.tick,
            "seed": self.state.seed,
            "decision_seed": self.state.seed + self.state.tick + int(actor.id.rsplit("-", 1)[-1]),
            "nearby": nearby,
            "factions": factions,
            "population": len(self.state.living(EntityKind.HUMAN)),
            "settlement_resources": {
                resource: self._settlement_resource_total(resource)
                for resource in ("food", "water", "wood", "stone", "tools", "meat")
            },
            "buildings": sum(
                1
                for entity in self.state.entities.values()
                if entity.alive and entity.kind == EntityKind.BUILDING
            ),
            "recent_world_events": [
                {"type": event.event_type, "actor": event.actor_id, "target": event.target_id}
                for event in self.events[-12:]
            ],
            "action_guidance": {
                "form_faction": "create a new political group; no target",
                "recruit": "invite an unaffiliated nearby human",
                "declare_war": "target a non-rival member of another faction",
                "make_peace": "target a member of a current rival faction",
                "innovate": "propose a generated profession, recipe, building, or rule",
                "sabotage": "damage a nearby building",
                "help": "give a resource to a nearby human",
                "steal": "take a resource and risk creating an enemy",
            },
            "legal_actions": self._legal_actions_for(actor, nearby_entities),
        }

    def _legal_actions_for(self, actor: Entity, nearby: list[Entity]) -> list[str]:
        actions = {
            ActionType.IDLE,
            ActionType.SLEEP,
            ActionType.EXPLORE,
        }
        if nearby:
            actions.add(ActionType.MOVE)
        if self._inventory_total(actor, ("food", "meat")):
            actions.add(ActionType.EAT)
        if any(entity.kind == EntityKind.LAKE for entity in nearby):
            actions.add(ActionType.DRINK)
        if any(
            entity.kind in {EntityKind.TREE, EntityKind.ROCK, EntityKind.LAKE}
            and any(amount > 0 for amount in entity.inventory.values())
            for entity in nearby
        ):
            actions.add(ActionType.GATHER)
        humans = [entity for entity in nearby if entity.kind == EntityKind.HUMAN]
        if humans:
            actions.update(
                {
                    ActionType.TALK,
                    ActionType.TRADE,
                    ActionType.HELP,
                    ActionType.STEAL,
                    ActionType.ATTACK,
                }
            )
        if any(entity.kind == EntityKind.COW for entity in nearby):
            actions.add(ActionType.ATTACK)
        if any(
            entity.kind == actor.kind
            and entity.gender != actor.gender
            and entity.reproduction_cooldown == 0
            for entity in nearby
        ):
            actions.add(ActionType.MATE)
        if any(entity.kind == EntityKind.BUILDING for entity in nearby):
            actions.add(ActionType.SABOTAGE)
        if actor.inventory.get("wood", 0) >= 10 and actor.inventory.get("stone", 0) >= 3:
            actions.add(ActionType.BUILD)
        if actor.profession != Profession.UNASSIGNED:
            actions.add(ActionType.WORK)
        if self.innovation_manager:
            actions.add(ActionType.INNOVATE)

        faction = self.state.factions.get(actor.faction_id or "")
        if not faction:
            actions.add(ActionType.FORM_FACTION)
        elif faction.leader_id == actor.id:
            if any(not human.faction_id for human in humans):
                actions.add(ActionType.RECRUIT)
            foreign_factions = {
                human.faction_id
                for human in humans
                if human.faction_id and human.faction_id != faction.id
            }
            if any(faction_id not in faction.rivals for faction_id in foreign_factions):
                actions.add(ActionType.DECLARE_WAR)
            if any(faction_id in faction.rivals for faction_id in foreign_factions):
                actions.add(ActionType.MAKE_PEACE)
        return sorted(action.value for action in actions)

    def statistics(self) -> dict[str, int]:
        return {
            "humans": len(self.state.living(EntityKind.HUMAN)),
            "cows": len(self.state.living(EntityKind.COW)),
            "buildings": sum(
                1 for item in self.state.entities.values() if item.kind == EntityKind.BUILDING
            ),
            "events": len(self.events),
            "factions": len(self.state.factions),
            "wars": sum(len(item.rivals) for item in self.state.factions.values()) // 2,
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
        predicate: Callable[[Entity], bool] | None = None,
    ) -> Entity | None:
        candidates = [
            entity
            for entity in self.state.entities.values()
            if entity.alive
            and entity.kind in kinds
            and entity.id != exclude_id
            and (predicate is None or predicate(entity))
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

    def _nearby_humans(self, actor: Entity, distance: float) -> list[Entity]:
        return sorted(
            (
                entity
                for entity in self.state.living(EntityKind.HUMAN)
                if entity.id != actor.id and actor.position.distance_to(entity.position) <= distance
            ),
            key=lambda entity: actor.position.distance_to(entity.position),
        )

    def _nearest_other_faction_member(self, actor: Entity) -> Entity | None:
        return self._nearest(
            actor,
            kinds={EntityKind.HUMAN},
            exclude_id=actor.id,
            predicate=lambda entity: bool(
                entity.faction_id and entity.faction_id != actor.faction_id
            ),
        )

    def _nearest_rival(self, actor: Entity) -> Entity | None:
        faction = self.state.factions.get(actor.faction_id or "")
        if not faction or not faction.rivals:
            return None
        return self._nearest(
            actor,
            kinds={EntityKind.HUMAN},
            exclude_id=actor.id,
            predicate=lambda entity: entity.faction_id in faction.rivals,
        )

    def _approach_interaction(
        self,
        actor: Entity,
        target: Entity | None,
        distance: float,
        expected_kind: EntityKind,
    ) -> bool:
        if not target or not target.alive or target.kind != expected_kind:
            actor.decision_lock_ticks = 0
            return False
        if not self._in_range(actor, target, distance):
            self._move(actor, target)
            return False
        return True

    def _random_temperament(self) -> Temperament:
        traits = {
            "aggression": self.random.betavariate(1.4, 1.8),
            "sociability": self.random.betavariate(1.7, 1.5),
            "ambition": self.random.betavariate(1.5, 1.6),
            "curiosity": self.random.betavariate(1.8, 1.4),
            "empathy": self.random.betavariate(1.7, 1.5),
            "creativity": self.random.betavariate(1.6, 1.5),
            "risk_tolerance": self.random.betavariate(1.5, 1.7),
        }
        archetypes = {
            "aggression": "warrior",
            "sociability": "diplomat",
            "ambition": "leader",
            "curiosity": "explorer",
            "empathy": "caretaker",
            "creativity": "visionary",
            "risk_tolerance": "rebel",
        }
        strongest = max(traits, key=traits.get)
        return Temperament(archetype=archetypes[strongest], **traits)

    def _inherit_temperament(self, first: Entity, second: Entity) -> Temperament:
        values: dict[str, float] = {}
        for trait in (
            "aggression",
            "sociability",
            "ambition",
            "curiosity",
            "empathy",
            "creativity",
            "risk_tolerance",
        ):
            inherited = (getattr(first.temperament, trait) + getattr(second.temperament, trait)) / 2
            values[trait] = max(0.0, min(1.0, inherited + self.random.uniform(-0.12, 0.12)))
        archetypes = {
            "aggression": "warrior",
            "sociability": "diplomat",
            "ambition": "leader",
            "curiosity": "explorer",
            "empathy": "caretaker",
            "creativity": "visionary",
            "risk_tolerance": "rebel",
        }
        strongest = max(values, key=values.get)
        return Temperament(archetype=archetypes[strongest], **values)

    @staticmethod
    def _initial_goal(temperament: Temperament) -> str:
        return {
            "warrior": "become strong and defeat my enemies",
            "diplomat": "build lasting relationships",
            "leader": "found and lead a powerful community",
            "explorer": "discover what lies beyond my home",
            "caretaker": "protect people who need help",
            "visionary": "create something the world has never seen",
            "rebel": "gain freedom and challenge authority",
        }.get(temperament.archetype, "survive and find a place in the world")

    @staticmethod
    def _in_range(first: Entity, second: Entity, distance: float) -> bool:
        return first.position.distance_to(second.position) <= distance

    @staticmethod
    def _inventory_total(entity: Entity, resources: tuple[str, ...]) -> int:
        return sum(entity.inventory.get(resource, 0) for resource in resources)

    def _settlement_resource_total(self, resource: str) -> int:
        return sum(
            human.inventory.get(resource, 0) for human in self.state.living(EntityKind.HUMAN)
        )
