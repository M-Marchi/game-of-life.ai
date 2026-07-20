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
    AgentState,
    Entity,
    EntityKind,
    Faction,
    Position,
    Profession,
    SocialBond,
    Temperament,
    WorldEvent,
    WorldState,
)

MALE_NAMES = ("James", "John", "Robert", "Michael", "David", "Daniel", "Marco", "Luca")
FEMALE_NAMES = ("Mary", "Sarah", "Emily", "Anna", "Sofia", "Giulia", "Elena", "Marta")
FACTION_NOUNS = ("Dawn", "Iron", "River", "Oak", "Ember", "Horizon", "Stone", "Free")
INITIAL_PROFESSIONS = (
    Profession.GATHERER,
    Profession.FARMER,
    Profession.BUILDER,
    Profession.CARPENTER,
    Profession.UNASSIGNED,
    Profession.UNASSIGNED,
    Profession.UNASSIGNED,
    Profession.UNASSIGNED,
)
APPEARANCE_STYLES = ("plain", "elegant", "bold", "natural", "scholarly", "artistic")
ACCESSORIES = ("none", "hat", "ribbon", "glasses", "scarf", "flower")
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
            human.profession = INITIAL_PROFESSIONS[index % len(INITIAL_PROFESSIONS)]
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
        human.aspirations = [human.goal]
        human.values = self._initial_values(human.temperament)
        human.self_awareness = 25 + human.temperament.curiosity * 25
        human.growth_drive = 30 + (human.temperament.ambition + human.temperament.curiosity) * 25
        human.confidence = 35 + human.temperament.resilience * 25
        human.appearance_hue = self.random.randrange(0, 360)
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
            if not actor.alive:
                continue
            if actor.state != AgentState.AWAKE:
                self._advance_sleep(actor)
                self._update_needs(actor)
                continue
            urgent_need = self._has_urgent_survival_need(actor)
            if actor.decision_lock_ticks > 0 and not urgent_need:
                actor.decision_lock_ticks -= 1
            else:
                if urgent_need:
                    actor.decision_lock_ticks = 0
                actor.action = self._choose_local_action(actor)
            self._resolve(actor)
            self._update_needs(actor)
        self._regenerate_resources()
        self._update_factions()
        self._update_vocations()
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
        if actor.aesthetic_need >= 72 and actor.energy > 35:
            return Action(ActionType.SELF_CARE, explanation="I want my appearance to express me")
        if actor.growth_drive >= 82 and actor.energy > 45 and self.random.random() < 0.025:
            return Action(ActionType.STUDY, explanation="I want to become more capable")
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
        if cow.energy <= 25:
            return Action(ActionType.SLEEP, explanation="rest")
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
        romantic = max(
            nearby,
            key=lambda human: self._social_bond(actor, human).attraction,
            default=None,
        )
        if (
            romantic
            and self._social_bond(actor, romantic).attraction >= 28
            and temperament.sociability + temperament.risk_tolerance > 0.9
        ):
            actor.decision_lock_ticks = 50
            return Action(
                ActionType.EXPRESS_AFFECTION,
                romantic.id,
                explanation="I want them to know how much they mean to me",
            )
        disliked = next(
            (human for human in nearby if actor.relationships.get(human.id, 0) < -10), None
        )
        if disliked and temperament.empathy > 0.72 and self.random.random() < 0.45:
            actor.decision_lock_ticks = 60
            return Action(ActionType.FORGIVE, disliked.id, explanation="I will end this grievance")
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
        if nearby and actor.long_term_memory and temperament.sociability > 0.62:
            target = self.random.choice(nearby)
            actor.decision_lock_ticks = 50
            return Action(
                ActionType.TELL_STORY,
                target.id,
                explanation="A memory of mine deserves to be shared",
            )
        if nearby and actor.skills and temperament.empathy + temperament.ambition > 1.05:
            target = min(nearby, key=lambda human: sum(human.skills.values()))
            actor.decision_lock_ticks = 50
            return Action(ActionType.TEACH, target.id, explanation="I will pass on what I know")
        if nearby and actor.confidence > 62 and temperament.sociability > 0.58:
            target = min(nearby, key=lambda human: human.confidence)
            actor.decision_lock_ticks = 50
            return Action(
                ActionType.INSPIRE,
                target.id,
                explanation="I will encourage them to pursue a meaningful goal",
            )
        if actor.short_term_memory and temperament.curiosity > 0.58:
            return Action(ActionType.REFLECT, explanation="I need to understand what happened")
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
        nearby = self._nearby_humans(actor, 60)
        if actor.profession == Profession.SCHOLAR:
            return Action(ActionType.STUDY, explanation="Researching society and human nature")
        if actor.profession == Profession.HEALER:
            patient = min(nearby, key=lambda human: human.health, default=None)
            if patient and patient.health < 95:
                return self._approach_or(
                    ActionType.HELP, actor, patient, 18, "Caring for someone who is hurt"
                )
            return Action(ActionType.STUDY, resource="healing", explanation="Studying healing")
        if actor.profession == Profession.ARTIST:
            building = self._nearest(
                actor,
                kinds={EntityKind.BUILDING},
                predicate=lambda item: item.beauty < 75,
            )
            if building:
                return self._approach_or(
                    ActionType.BEAUTIFY, actor, building, 18, "Making this place beautiful"
                )
            return Action(ActionType.STUDY, resource="art", explanation="Developing my art")
        if actor.profession == Profession.TEACHER:
            if nearby and actor.skills:
                student = min(nearby, key=lambda human: sum(human.skills.values()))
                if student.growth_drive < 38:
                    return self._approach_or(
                        ActionType.INSPIRE,
                        actor,
                        student,
                        20,
                        "Encouraging a discouraged student",
                    )
                return self._approach_or(
                    ActionType.TEACH, actor, student, 20, "Helping someone learn"
                )
            return Action(ActionType.STUDY, resource="education", explanation="Preparing a lesson")
        if actor.profession == Profession.DIPLOMAT:
            grievance = next(
                (human for human in nearby if actor.relationships.get(human.id, 0) < 0), None
            )
            if grievance:
                return self._approach_or(
                    ActionType.FORGIVE, actor, grievance, 20, "Trying to repair a relationship"
                )
            if nearby:
                return self._approach_or(
                    ActionType.TALK, actor, nearby[0], 18, "Listening to another point of view"
                )
        if actor.profession == Profession.GUARD:
            enemy = self._nearest_rival(actor)
            if enemy:
                return self._approach_or(
                    ActionType.ATTACK, actor, enemy, 14, "Defending my community"
                )
            return Action(ActionType.EXPLORE, explanation="Patrolling the settlement")
        if actor.profession == Profession.UNASSIGNED and actor.growth_drive > 55:
            return Action(ActionType.STUDY, explanation="Searching for my vocation")
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
            self._start_sleep(actor)
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
        elif action.kind == ActionType.REFLECT:
            self._reflect(actor)
        elif action.kind == ActionType.TELL_STORY:
            self._tell_story(actor, target)
        elif action.kind == ActionType.TEACH:
            self._teach(actor, target)
        elif action.kind == ActionType.FORGIVE:
            self._forgive(actor, target)
        elif action.kind == ActionType.STUDY:
            self._study(actor, action.resource)
        elif action.kind == ActionType.SELF_CARE:
            self._self_care(actor)
        elif action.kind == ActionType.INSPIRE:
            self._inspire(actor, target)
        elif action.kind == ActionType.BEAUTIFY:
            self._beautify(actor, target)
        elif action.kind == ActionType.EXPRESS_AFFECTION:
            self._express_affection(actor, target)

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

    def _start_sleep(self, actor: Entity) -> None:
        if actor.state != AgentState.AWAKE:
            return
        actor.state = AgentState.SLEEPING
        actor.sleep_ticks_remaining = self.config.sleep_duration_ticks
        actor.decision_lock_ticks = 0
        actor.action = Action(ActionType.SLEEP, explanation="Sleeping and processing memories")
        self.emit("sleep_started", actor.id, short_memories=len(actor.short_term_memory))

    def _advance_sleep(self, actor: Entity) -> None:
        actor.sleep_ticks_remaining = max(0, actor.sleep_ticks_remaining - 1)
        actor.energy = min(100, actor.energy + 0.75)
        if actor.kind == EntityKind.COW:
            if actor.sleep_ticks_remaining == 0:
                actor.state = AgentState.AWAKE
                actor.energy = max(actor.energy, 92)
                actor.action = Action(ActionType.IDLE, explanation="rested")
                self.emit("woke_up", actor.id, dream="", long_memories=0)
            return
        if (
            actor.state == AgentState.SLEEPING
            and actor.sleep_ticks_remaining <= self.config.dream_start_ticks
        ):
            actor.state = AgentState.DREAMING
            dreamer_snapshot = copy.deepcopy(actor)
            dream_context = self.context_for(actor)
            dream_context["sleep_world_state"] = {
                "tick": self.state.tick,
                "population": len(self.state.living(EntityKind.HUMAN)),
                "factions": len(self.state.factions),
                "wars": sum(len(faction.rivals) for faction in self.state.factions.values()) // 2,
                "recent_events": [event.event_type for event in self.events[-10:]],
            }
            submitted = bool(
                self.ai_worker and self.ai_worker.submit_reflection(dreamer_snapshot, dream_context)
            )
            actor.reflection_pending = submitted
            if submitted:
                self.emit("dream_started", actor.id, generated_by="qwen3:8b")
            else:
                retained, forgotten = actor.consolidate_memories(self.state.tick)
                self._create_deterministic_dream(actor, dreamer_snapshot)
                self.emit(
                    "memory_consolidated",
                    actor.id,
                    retained=retained,
                    forgotten=forgotten,
                    ai_dream=False,
                )
        if actor.sleep_ticks_remaining == 0:
            actor.state = AgentState.AWAKE
            actor.energy = max(actor.energy, 92)
            actor.mood = "calm" if not actor.last_dream else actor.mood
            actor.action = Action(ActionType.IDLE, explanation="I have just awakened")
            self.emit(
                "woke_up",
                actor.id,
                dream=actor.last_dream,
                long_memories=len(actor.long_term_memory),
            )

    def _create_deterministic_dream(self, actor: Entity, snapshot: Entity) -> None:
        memories = sorted(
            snapshot.short_term_memory + snapshot.long_term_memory,
            key=lambda memory: (memory.importance, memory.tick),
            reverse=True,
        )[:3]
        if memories:
            fragments = "; then ".join(memory.summary for memory in memories)
            dream = f"I dreamed that {fragments}."
        else:
            dream = "I dreamed of an empty road leading toward an unknown future."
        actor.last_dream = dream
        actor.dreams.append(dream)
        del actor.dreams[:-8]
        actor.remember(
            dream,
            tick=self.state.tick,
            category="dream",
            importance=0.72,
            emotion="curious",
        )
        actor.consolidate_memories(self.state.tick)
        self.emit("dream", actor.id, dream=dream, generated_by="simulation")

    def _reflect(self, actor: Entity) -> None:
        retained, forgotten = actor.consolidate_memories(self.state.tick)
        actor.self_awareness = min(100, actor.self_awareness + 2.5)
        actor.stress = max(0, actor.stress - 4)
        self._evolve_goal(actor)
        actor.mood = "calm"
        actor.decision_lock_ticks = 0
        self.emit("reflection", actor.id, retained=retained, forgotten=forgotten)

    def _tell_story(self, actor: Entity, target: Entity | None) -> None:
        if not self._approach_interaction(actor, target, 20, EntityKind.HUMAN):
            return
        assert target is not None
        if not actor.long_term_memory:
            actor.decision_lock_ticks = 0
            return
        memory = max(actor.long_term_memory, key=lambda item: item.importance)
        memory.recall_count += 1
        memory.last_recalled_tick = self.state.tick
        target.remember(
            f"{actor.name} told me: {memory.summary}",
            tick=self.state.tick,
            category="story",
            importance=max(0.6, memory.importance * 0.8),
            emotion=memory.emotion,
            participants=[actor.id],
        )
        self._update_bond(actor, target, affinity=6, trust=5, familiarity=8, event="shared a story")
        self._update_bond(
            target, actor, affinity=8, trust=7, respect=4, familiarity=8, event="heard a story"
        )
        target.values["community"] = min(100, target.values.get("community", 50) + 2)
        target.self_awareness = min(100, target.self_awareness + 0.4)
        actor.decision_lock_ticks = 0
        self.emit("story_told", actor.id, target.id, memory_id=memory.id)

    def _teach(self, actor: Entity, target: Entity | None) -> None:
        if actor.action_cooldown:
            actor.decision_lock_ticks = 0
            return
        if not self._approach_interaction(actor, target, 20, EntityKind.HUMAN):
            return
        assert target is not None
        if not actor.skills:
            actor.decision_lock_ticks = 0
            return
        skill, level = max(actor.skills.items(), key=lambda item: item[1])
        before = target.skills.get(skill, 0)
        target.skills[skill] = min(20, before + min(0.5, max(0.1, level * 0.1)))
        if skill in actor.knowledge:
            target.knowledge[skill] = min(
                20,
                target.knowledge.get(skill, 0) + min(0.35, actor.knowledge[skill] * 0.08),
            )
        target.growth_drive = min(100, target.growth_drive + 8)
        target.confidence = min(100, target.confidence + 2)
        target.values["knowledge"] = min(100, target.values.get("knowledge", 50) + 2.5)
        target.remember(
            f"{actor.name} taught me {skill}",
            tick=self.state.tick,
            category="learning",
            importance=0.7,
            emotion="hopeful",
            participants=[actor.id],
        )
        actor.reputation = min(100, actor.reputation + 1)
        self._update_bond(
            actor,
            target,
            affinity=3,
            trust=3,
            respect=2,
            familiarity=5,
            event="taught a skill",
            add_roles=("student",),
        )
        self._update_bond(
            target,
            actor,
            affinity=5,
            trust=6,
            respect=10,
            familiarity=5,
            event="learned a skill",
            add_roles=("mentor",),
        )
        self._adapt_temperament(target, valence=1, intensity=0.3, source="learning")
        actor.action_cooldown = 35
        actor.decision_lock_ticks = 0
        self.emit("teach", actor.id, target.id, skill=skill)

    def _forgive(self, actor: Entity, target: Entity | None) -> None:
        if not self._approach_interaction(actor, target, 20, EntityKind.HUMAN):
            return
        assert target is not None
        previous = actor.relationships.get(target.id, 0)
        self._update_bond(
            actor,
            target,
            affinity=min(25, 10 - previous),
            trust=12,
            fear=-15,
            familiarity=2,
            event="chose forgiveness",
        )
        actor.mood = "calm"
        actor.remember(
            f"I chose to forgive {target.name}",
            tick=self.state.tick,
            category="relationship",
            importance=0.75,
            emotion="hopeful",
            participants=[target.id],
        )
        actor.decision_lock_ticks = 0
        self._adapt_temperament(actor, valence=1, intensity=0.65, source="forgiveness")
        self.emit("forgive", actor.id, target.id, previous_relationship=previous)

    def _study(self, actor: Entity, requested_field: str | None = None) -> None:
        if actor.action_cooldown:
            actor.decision_lock_ticks = 0
            return
        profession_fields = {
            Profession.HEALER: "healing",
            Profession.ARTIST: "art",
            Profession.DIPLOMAT: "society",
            Profession.GUARD: "strategy",
            Profession.BUILDER: "craft",
            Profession.CARPENTER: "craft",
            Profession.BLACKSMITH: "craft",
            Profession.FARMER: "nature",
            Profession.RANCHER: "nature",
            Profession.SCHOLAR: "society",
            Profession.TEACHER: "education",
        }
        field = requested_field or profession_fields.get(actor.profession)
        if not field:
            strongest_value = max(actor.values, key=actor.values.get, default="knowledge")
            field = {
                "beauty": "art",
                "community": "society",
                "achievement": "craft",
                "power": "strategy",
                "freedom": "nature",
                "knowledge": "society",
                "care": "healing",
            }.get(strongest_value, "self_knowledge")
        gain = 0.18 + actor.temperament.curiosity * 0.16 + actor.temperament.discipline * 0.12
        previous = actor.knowledge.get(field, 0.0)
        actor.knowledge[field] = min(20, previous + gain)
        actor.skills[field] = min(20, actor.skills.get(field, 0.0) + gain * 0.45)
        actor.self_awareness = min(100, actor.self_awareness + 0.35 + gain * 0.2)
        actor.growth_drive = max(0, actor.growth_drive - 14)
        actor.confidence = min(100, actor.confidence + 0.4)
        actor.energy = max(0, actor.energy - 3)
        actor.mood = "curious"
        actor.action_cooldown = 28
        actor.decision_lock_ticks = 0
        if int(previous) < int(actor.knowledge[field]):
            actor.remember(
                f"I reached a new understanding of {field}",
                tick=self.state.tick,
                category="learning",
                importance=0.68,
                emotion="proud",
            )
            self._evolve_goal(actor)
        self.emit("study", actor.id, field=field, gain=round(gain, 3))

    def _self_care(self, actor: Entity) -> None:
        previous_style = actor.appearance_style
        style_scores = {
            "elegant": actor.temperament.sociability + actor.values.get("beauty", 0) / 100,
            "bold": actor.temperament.ambition + actor.temperament.risk_tolerance,
            "natural": actor.temperament.empathy + actor.values.get("freedom", 0) / 100,
            "scholarly": actor.temperament.curiosity + min(0.8, sum(actor.knowledge.values()) / 40),
            "artistic": actor.temperament.creativity + actor.values.get("beauty", 0) / 100,
            "plain": actor.temperament.discipline,
        }
        actor.appearance_style = max(style_scores, key=style_scores.get)
        actor.accessory = ACCESSORIES[(self.state.tick + actor.memory_sequence) % len(ACCESSORIES)]
        actor.appearance_hue = (
            actor.appearance_hue + 37 + round(actor.temperament.creativity * 90)
        ) % 360
        actor.aesthetic_need = 0
        actor.confidence = min(100, actor.confidence + 8)
        actor.stress = max(0, actor.stress - 7)
        actor.mood = "proud"
        actor.decision_lock_ticks = 0
        actor.remember(
            f"I changed my style from {previous_style} to {actor.appearance_style}",
            tick=self.state.tick,
            category="identity",
            importance=0.62,
            emotion="proud",
        )
        self._adapt_temperament(actor, valence=1, intensity=0.3, source="self_care")
        self.emit(
            "appearance_changed",
            actor.id,
            style=actor.appearance_style,
            accessory=actor.accessory,
            hue=actor.appearance_hue,
        )

    def _inspire(self, actor: Entity, target: Entity | None) -> None:
        if actor.action_cooldown:
            actor.decision_lock_ticks = 0
            return
        if not self._approach_interaction(actor, target, 20, EntityKind.HUMAN):
            return
        assert target is not None
        strongest_value = max(actor.values, key=actor.values.get, default="community")
        target.values[strongest_value] = min(
            100, target.values.get(strongest_value, 50) + 3 + actor.temperament.sociability * 3
        )
        target.confidence = min(100, target.confidence + 6 + actor.confidence * 0.03)
        target.growth_drive = min(100, target.growth_drive + 12)
        if actor.goal not in target.aspirations:
            target.aspirations.append(actor.goal)
            del target.aspirations[:-5]
        if target.self_awareness > 45 and target.confidence > 55:
            self._evolve_goal(target)
        self._update_bond(
            actor, target, affinity=4, respect=3, familiarity=4, event="offered inspiration"
        )
        self._update_bond(
            target,
            actor,
            affinity=7,
            trust=6,
            respect=7,
            familiarity=4,
            event="felt inspired",
        )
        target.remember(
            f"{actor.name} inspired me to value {strongest_value}",
            tick=self.state.tick,
            category="identity",
            importance=0.74,
            emotion="hopeful",
            participants=[actor.id],
        )
        self._adapt_temperament(target, valence=1, intensity=0.45, source="inspiration")
        actor.action_cooldown = 30
        actor.decision_lock_ticks = 0
        self.emit("inspire", actor.id, target.id, value=strongest_value, goal=target.goal)

    def _beautify(self, actor: Entity, target: Entity | None) -> None:
        if actor.action_cooldown:
            return
        if not self._approach_interaction(actor, target, 18, EntityKind.BUILDING):
            return
        assert target is not None
        gain = 6 + actor.temperament.creativity * 8 + actor.skills.get("art", 0)
        target.beauty = min(100, target.beauty + gain)
        target.appearance_hue = actor.appearance_hue
        actor.skills["art"] = actor.skills.get("art", 0) + 0.25
        actor.confidence = min(100, actor.confidence + 2)
        actor.growth_drive = max(0, actor.growth_drive - 5)
        actor.action_cooldown = 45
        actor.decision_lock_ticks = 45
        self.emit("beautify", actor.id, target.id, beauty=round(target.beauty, 1))

    def _express_affection(self, actor: Entity, target: Entity | None) -> None:
        if actor.action_cooldown:
            actor.decision_lock_ticks = 0
            return
        if not self._approach_interaction(actor, target, 18, EntityKind.HUMAN):
            return
        assert target is not None
        target_bond = self._social_bond(target, actor)
        acceptance = (
            0.3
            + target_bond.attraction / 160
            + target_bond.trust / 240
            + target.temperament.empathy * 0.2
        )
        accepted = self.random.random() < max(0.08, min(0.92, acceptance))
        self._update_bond(
            actor,
            target,
            affinity=6 if accepted else -2,
            trust=4 if accepted else -1,
            attraction=10,
            respect=2,
            familiarity=5,
            event="expressed affection",
        )
        if accepted:
            reciprocal = self._update_bond(
                target,
                actor,
                affinity=7,
                trust=5,
                attraction=8,
                respect=2,
                familiarity=5,
                event="returned affection",
            )
            actor.mood = target.mood = "hopeful"
            actor.remember(
                f"{target.name} returned my affection",
                tick=self.state.tick,
                category="love",
                importance=0.84 if reciprocal.label == "love" else 0.7,
                emotion="hopeful",
                participants=[target.id],
            )
        else:
            self._update_bond(
                target,
                actor,
                affinity=-2,
                trust=-1,
                familiarity=3,
                event="declined affection",
            )
            actor.mood = "sad"
            actor.stress = min(100, actor.stress + 4)
        actor.action_cooldown = 45
        actor.decision_lock_ticks = 0
        self.emit(
            "affection",
            actor.id,
            target.id,
            accepted=accepted,
            relationship=self._social_bond(actor, target).label,
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
        actor.decision_lock_ticks = 0
        if target.kind == EntityKind.HUMAN:
            self._update_bond(
                actor,
                target,
                affinity=-8,
                trust=-10,
                respect=2,
                familiarity=3,
                event="attacked",
            )
            self._update_bond(
                target,
                actor,
                affinity=-14,
                trust=-16,
                fear=14,
                familiarity=5,
                event="was attacked",
            )
        self.emit("attack", actor.id, target.id, damage=round(damage, 2))
        if target.health <= 0:
            self._kill(target, actor, cause="violence")

    def _kill(
        self,
        target: Entity,
        killer: Entity | None = None,
        *,
        cause: str | None = None,
    ) -> None:
        if not target.alive:
            return
        target.alive = False
        if killer and target.kind == EntityKind.COW:
            killer.inventory["meat"] = killer.inventory.get("meat", 0) + 8
        if killer and target.kind == EntityKind.HUMAN:
            killer.kills += 1
            killer.reputation -= 6
            for human in self.state.living(EntityKind.HUMAN):
                if human.id != killer.id:
                    self._update_bond(
                        human,
                        killer,
                        affinity=-20,
                        trust=-18,
                        fear=18,
                        familiarity=4,
                        event="witnessed a killing",
                    )
            killer_faction = self.state.factions.get(killer.faction_id or "")
            target_faction = self.state.factions.get(target.faction_id or "")
            if killer_faction and target_faction and target_faction.id in killer_faction.rivals:
                killer_faction.victories += 1
                target_faction.defeats += 1
                for resource, amount in list(target.inventory.items()):
                    captured = amount // 2
                    if captured:
                        killer.inventory[resource] = killer.inventory.get(resource, 0) + captured
            killer.remember(
                f"I killed {target.name}",
                tick=self.state.tick,
                category="violence",
                importance=1.0,
                emotion="angry" if killer.temperament.aggression > 0.6 else "afraid",
                participants=[target.id],
            )
            for witness in self._nearby_humans(target, 80):
                if witness.id != killer.id:
                    witness.remember(
                        f"I witnessed {killer.name} kill {target.name}",
                        tick=self.state.tick,
                        category="violence",
                        importance=0.95,
                        emotion="afraid",
                        participants=[killer.id, target.id],
                    )
                    self._adapt_temperament(
                        witness, valence=-1, intensity=0.9, source="witnessed_death"
                    )
            self._adapt_temperament(killer, valence=-1, intensity=0.8, source="killing")
        self.emit(
            "death",
            killer.id if killer else None,
            target.id,
            kind=target.kind,
            cause=cause or ("violence" if killer else "health"),
        )

    def _talk(self, actor: Entity, target: Entity | None) -> None:
        if actor.action_cooldown:
            actor.decision_lock_ticks = 0
            return
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
        attraction_gain = 0 if argumentative else max(0, compatibility * 3 - 0.6)
        self._update_bond(
            actor,
            target,
            affinity=relationship_change,
            trust=-8 if argumentative else compatibility * 2.5,
            attraction=attraction_gain,
            respect=-2 if argumentative else compatibility,
            familiarity=5,
            event="argued" if argumentative else "talked",
        )
        self._update_bond(
            target,
            actor,
            affinity=relationship_change,
            trust=-8 if argumentative else compatibility * 2.5,
            attraction=attraction_gain,
            respect=-2 if argumentative else compatibility,
            familiarity=5,
            event="argued" if argumentative else "talked",
        )
        topic = max(actor.values, key=actor.values.get, default="survival")
        influenced_trait = max(
            (
                "aggression",
                "sociability",
                "ambition",
                "curiosity",
                "empathy",
                "creativity",
                "risk_tolerance",
                "resilience",
                "discipline",
            ),
            key=lambda trait: getattr(actor.temperament, trait),
        )
        if argumentative:
            actor.mood = target.mood = "angry"
            self._adapt_temperament(actor, valence=-1, intensity=0.4, source="argument")
            self._adapt_temperament(target, valence=-1, intensity=0.45, source="argument")
            self.emit("argument", actor.id, target.id)
        else:
            if compatibility > 0.75:
                actor.mood = target.mood = "hopeful"
            influence = 0.008 + compatibility * 0.012
            current = getattr(target.temperament, influenced_trait)
            example = getattr(actor.temperament, influenced_trait)
            setattr(target.temperament, influenced_trait, current + (example - current) * influence)
            target.values[topic] = min(100, target.values.get(topic, 50) + 1.5 * compatibility)
            target.self_awareness = min(100, target.self_awareness + 0.15)
            if actor.relationships[target.id] > 35 and actor.goal not in target.aspirations:
                target.aspirations.append(actor.goal)
                del target.aspirations[:-5]
            self._adapt_temperament(actor, valence=1, intensity=0.18, source="conversation")
            self._adapt_temperament(target, valence=1, intensity=0.22, source="conversation")
        emotion = "angry" if argumentative else "neutral"
        importance = 0.72 if argumentative else 0.45
        actor.remember(
            f"{'Argued' if argumentative else 'Talked'} with {target.name}",
            tick=self.state.tick,
            category="relationship",
            importance=importance,
            emotion=emotion,
            participants=[target.id],
        )
        target.remember(
            f"{actor.name} {'argued' if argumentative else 'talked'} with me",
            tick=self.state.tick,
            category="relationship",
            importance=importance,
            emotion=emotion,
            participants=[actor.id],
        )
        actor.decision_lock_ticks = 0
        actor.action_cooldown = 30
        self.emit(
            "talk",
            actor.id,
            target.id,
            relationship_change=relationship_change,
            topic=topic,
            influenced_trait=influenced_trait,
        )

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
            or actor.reproduction_drive < 80
            or target.reproduction_drive < 80
            or not self._in_range(actor, target, 13)
        ):
            return
        position = Position(
            (actor.position.x + target.position.x) / 2, (actor.position.y + target.position.y) / 2
        )
        if actor.kind == EntityKind.HUMAN:
            if (
                len(self.state.living(EntityKind.HUMAN)) >= self.config.max_humans
                or actor.age_years < 18
                or target.age_years < 18
                or actor.relationships.get(target.id, 0) < 12
                or target.relationships.get(actor.id, 0) < 12
            ):
                return
            child = self.spawn_human(position=position, age=0)
            child.profession = Profession.UNASSIGNED
            child.temperament = self._inherit_temperament(actor, target)
            child.goal = self._initial_goal(child.temperament)
            child.aspirations = [child.goal]
            child.values = {
                key: max(
                    0,
                    min(
                        100,
                        (actor.values.get(key, 50) + target.values.get(key, 50)) / 2
                        + self.random.uniform(-8, 8),
                    ),
                )
                for key in set(actor.values) | set(target.values)
            }
            child.faction_id = actor.faction_id if actor.faction_id == target.faction_id else None
            if child.faction_id:
                self.state.factions[child.faction_id].members.append(child.id)
            self._update_bond(
                actor,
                target,
                affinity=10,
                trust=12,
                attraction=20,
                familiarity=8,
                event="became parents",
                add_roles=("partner",),
            )
            self._update_bond(
                target,
                actor,
                affinity=10,
                trust=12,
                attraction=20,
                familiarity=8,
                event="became parents",
                add_roles=("partner",),
            )
            self._update_bond(
                actor,
                child,
                affinity=70,
                trust=45,
                attraction=0,
                respect=20,
                familiarity=40,
                event="child was born",
                add_roles=("child",),
            )
            self._update_bond(
                target,
                child,
                affinity=70,
                trust=45,
                respect=20,
                familiarity=40,
                event="child was born",
                add_roles=("child",),
            )
            self._update_bond(
                child,
                actor,
                affinity=65,
                trust=55,
                respect=25,
                familiarity=40,
                event="born to parent",
                add_roles=("parent",),
            )
            self._update_bond(
                child,
                target,
                affinity=65,
                trust=55,
                respect=25,
                familiarity=40,
                event="born to parent",
                add_roles=("parent",),
            )
            sibling_ids = {
                bond.target_id
                for parent in (actor, target)
                for bond in parent.social_bonds.values()
                if "child" in bond.roles and bond.target_id != child.id
            }
            for sibling_id in sibling_ids:
                sibling = self.state.entities.get(sibling_id)
                if not sibling or not sibling.alive:
                    continue
                self._update_bond(
                    child,
                    sibling,
                    affinity=45,
                    trust=30,
                    familiarity=25,
                    event="born as siblings",
                    add_roles=("sibling",),
                )
                self._update_bond(
                    sibling,
                    child,
                    affinity=45,
                    trust=30,
                    familiarity=25,
                    event="became siblings",
                    add_roles=("sibling",),
                )
        else:
            if len(self.state.living(EntityKind.COW)) >= self.config.max_cows:
                return
            child = self.spawn_cow(position=position)
        actor.reproduction_drive = target.reproduction_drive = 0
        actor.reproduction_cooldown = target.reproduction_cooldown = 2_000
        actor.decision_lock_ticks = 0
        if actor.kind == EntityKind.HUMAN:
            actor.remember(
                f"{target.name} and I had a child",
                tick=self.state.tick,
                category="family",
                importance=1.0,
                emotion="hopeful",
                participants=[target.id, child.id],
            )
            target.remember(
                f"{actor.name} and I had a child",
                tick=self.state.tick,
                category="family",
                importance=1.0,
                emotion="hopeful",
                participants=[actor.id, child.id],
            )
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
            beauty=8 + actor.temperament.creativity * 12,
            appearance_hue=actor.appearance_hue,
        )
        self.state.entities[building.id] = building
        actor.remember(
            f"I built a {building_type}",
            tick=self.state.tick,
            category="creation",
            importance=0.85,
            emotion="proud",
            participants=[building.id],
        )
        self._adapt_temperament(actor, valence=1, intensity=0.55, source="creation")
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
        effects = rule.get("effects", {}) if rule.get("category") == "profession" else {}
        effect_amounts = {key: min(10.0, float(value)) for key, value in effects.items()}
        if effect_amounts.get("knowledge_gain"):
            actor.knowledge[rule["id"]] = (
                actor.knowledge.get(rule["id"], 0) + effect_amounts["knowledge_gain"]
            )
            actor.self_awareness = min(
                100, actor.self_awareness + effect_amounts["knowledge_gain"] * 0.2
            )
        if effect_amounts.get("beauty_gain"):
            actor.aesthetic_need = max(0, actor.aesthetic_need - effect_amounts["beauty_gain"])
            building = self._nearest(actor, kinds={EntityKind.BUILDING})
            if building:
                building.beauty = min(100, building.beauty + effect_amounts["beauty_gain"])
        if effect_amounts.get("health_gain"):
            patient = min(
                self._nearby_humans(actor, 30), key=lambda item: item.health, default=actor
            )
            patient.health = min(100, patient.health + effect_amounts["health_gain"])
        if effect_amounts.get("social_gain"):
            actor.social = min(100, actor.social + effect_amounts["social_gain"])
            for neighbor in self._nearby_humans(actor, 25):
                neighbor.social = min(100, neighbor.social + effect_amounts["social_gain"] * 0.5)
        if effect_amounts.get("confidence_gain"):
            actor.confidence = min(100, actor.confidence + effect_amounts["confidence_gain"])
        if effect_amounts.get("stress_relief"):
            actor.stress = max(0, actor.stress - effect_amounts["stress_relief"])
            for neighbor in self._nearby_humans(actor, 25):
                neighbor.stress = max(0, neighbor.stress - effect_amounts["stress_relief"] * 0.5)
        actor.skills[rule_id or "innovation"] = actor.skills.get(rule_id or "innovation", 0) + 0.2
        duration = max(1, min(100, int(rule.get("duration_ticks", 20))))
        actor.action_cooldown = duration
        actor.decision_lock_ticks = duration
        self.emit(
            "work",
            actor.id,
            rule_id=rule_id,
            outputs=rule.get("outputs", {}),
            effects=effect_amounts,
        )

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
        if actor.action_cooldown:
            actor.decision_lock_ticks = 0
            return
        if not self._approach_interaction(actor, target, 18, EntityKind.HUMAN):
            return
        assert target is not None
        if actor.profession == Profession.HEALER and target.health < 100:
            healing = 3 + actor.skills.get("healing", 0) * 0.3
            target.health = min(100, target.health + healing)
            actor.skills["healing"] = actor.skills.get("healing", 0) + 0.2
            actor.knowledge["healing"] = actor.knowledge.get("healing", 0) + 0.08
            self._update_bond(
                actor, target, affinity=5, trust=4, respect=3, familiarity=4, event="provided care"
            )
            self._update_bond(
                target,
                actor,
                affinity=8,
                trust=10,
                respect=7,
                familiarity=5,
                event="received care",
            )
            target.remember(
                f"{actor.name} treated my wounds",
                tick=self.state.tick,
                category="care",
                importance=0.72,
                emotion="hopeful",
                participants=[actor.id],
            )
            self._adapt_temperament(actor, valence=1, intensity=0.35, source="healing")
            self._adapt_temperament(target, valence=1, intensity=0.45, source="healed")
            actor.action_cooldown = 24
            actor.decision_lock_ticks = 0
            self.emit("heal", actor.id, target.id, amount=round(healing, 2))
            return
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
        self._update_bond(
            actor, target, affinity=8, trust=5, respect=3, familiarity=3, event="offered help"
        )
        self._update_bond(
            target,
            actor,
            affinity=12,
            trust=12,
            respect=6,
            familiarity=4,
            event="received help",
        )
        actor.reputation = min(100, actor.reputation + 2)
        actor.mood = "hopeful"
        target.remember(
            f"{actor.name} helped me with {resource}",
            tick=self.state.tick,
            category="relationship",
            importance=0.68,
            emotion="hopeful",
            participants=[actor.id],
        )
        self._adapt_temperament(actor, valence=1, intensity=0.4, source="helping")
        self._adapt_temperament(target, valence=1, intensity=0.55, source="received_help")
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
            self._update_bond(
                target,
                actor,
                affinity=-28,
                trust=-35,
                fear=6,
                familiarity=5,
                event="was robbed",
            )
            self._update_bond(
                actor,
                target,
                affinity=-8,
                trust=-6,
                familiarity=3,
                event="stole from",
            )
            actor.reputation = max(-100, actor.reputation - 5)
            target.mood = "angry"
            target.remember(
                f"{actor.name} stole {resource} from me",
                tick=self.state.tick,
                category="betrayal",
                importance=0.88,
                emotion="angry",
                participants=[actor.id],
            )
            self._adapt_temperament(target, valence=-1, intensity=0.7, source="betrayal")
        actor.mood = "proud" if not detected else "afraid"
        actor.decision_lock_ticks = 0
        self.emit("steal", actor.id, target.id, resource=resource, detected=detected)

    def _explore(self, actor: Entity) -> None:
        if actor.action_cooldown:
            actor.decision_lock_ticks = 0
            return
        actor.position.x = min(
            max(8, actor.position.x + self.random.uniform(-25, 25)), self.state.width - 8
        )
        actor.position.y = min(
            max(8, actor.position.y + self.random.uniform(-25, 25)), self.state.height - 8
        )
        actor.mood = "curious"
        actor.remember(
            "I explored an unfamiliar part of the world",
            tick=self.state.tick,
            category="discovery",
            importance=0.52,
            emotion="curious",
        )
        actor.action_cooldown = 20
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
        actor.remember(
            f"I founded {faction.name}",
            tick=self.state.tick,
            category="politics",
            importance=0.95,
            emotion="proud",
        )
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
            self._update_bond(
                actor,
                target,
                affinity=6,
                trust=5,
                respect=4,
                familiarity=5,
                event="recruited into faction",
                add_roles=("faction_ally",),
            )
            self._update_bond(
                target,
                actor,
                affinity=8,
                trust=7,
                respect=9,
                familiarity=5,
                event="joined faction",
                add_roles=("faction_ally",),
            )
            target.remember(
                f"I joined {faction.name} at {actor.name}'s invitation",
                tick=self.state.tick,
                category="politics",
                importance=0.82,
                emotion="hopeful",
                participants=[actor.id],
            )
            self.emit("recruit", actor.id, target.id, faction_id=faction.id, accepted=True)
        else:
            self._update_bond(
                target,
                actor,
                affinity=-3,
                trust=-2,
                familiarity=2,
                event="rejected recruitment",
            )
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
        self._update_bond(
            actor,
            target,
            affinity=-25,
            trust=-20,
            respect=3,
            fear=5,
            familiarity=5,
            event="declared faction war",
            add_roles=("faction_rival",),
        )
        self._update_bond(
            target,
            actor,
            affinity=-25,
            trust=-20,
            fear=8,
            familiarity=5,
            event="became a faction enemy",
            add_roles=("faction_rival",),
        )
        for member_id in own.members:
            member = self.state.entities.get(member_id)
            if member and member.alive:
                member.remember(
                    f"Our faction {own.name} went to war with {other.name}",
                    tick=self.state.tick,
                    category="war",
                    importance=0.92,
                    emotion="angry",
                    participants=[target.id],
                )
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
            self._update_bond(
                actor,
                target,
                affinity=18,
                trust=12,
                fear=-8,
                familiarity=3,
                event="made peace",
                remove_roles=("faction_rival",),
            )
            self._update_bond(
                target,
                actor,
                affinity=12,
                trust=10,
                fear=-6,
                familiarity=3,
                event="accepted peace",
                remove_roles=("faction_rival",),
            )
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
            actor.remember(
                "I proposed an innovation to change the settlement",
                tick=self.state.tick,
                category="creation",
                importance=0.8,
                emotion="curious",
            )
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
        if actor.state != AgentState.AWAKE:
            hunger_rate *= 0.35
            thirst_multiplier *= 0.35
        actor.hunger = min(120, actor.hunger + hunger_rate * hunger_multiplier)
        actor.thirst = min(120, actor.thirst + 0.1 * thirst_multiplier)
        if actor.state == AgentState.AWAKE:
            actor.social = max(0, actor.social - (0.025 if actor.kind == EntityKind.HUMAN else 0))
            actor.reproduction_drive = min(100, actor.reproduction_drive + 0.025)
        if actor.action.kind not in {ActionType.SLEEP, ActionType.IDLE}:
            actor.energy = max(0, actor.energy - 0.05)
        if actor.action_cooldown:
            actor.action_cooldown -= 1
        if actor.reproduction_cooldown:
            actor.reproduction_cooldown -= 1
        actor.age_years += 1 / 100_000
        if actor.kind == EntityKind.HUMAN:
            self._update_psychology(actor)
        if actor.hunger > 100 or actor.thirst > 100 or actor.energy <= 0:
            actor.health -= 0.15
        elif actor.health < 100 and actor.hunger < 60 and actor.thirst < 60:
            actor.health = min(100, actor.health + 0.02)
        if actor.health <= 0:
            if actor.thirst > 100:
                cause = "dehydration"
            elif actor.hunger > 100:
                cause = "starvation"
            elif actor.energy <= 0:
                cause = "exhaustion"
            else:
                cause = "health"
            self._kill(actor, cause=cause)

    def _update_psychology(self, actor: Entity) -> None:
        if actor.state == AgentState.AWAKE:
            actor.aesthetic_need = min(
                100, actor.aesthetic_need + 0.008 + actor.temperament.creativity * 0.006
            )
            actor.growth_drive = min(
                100,
                actor.growth_drive
                + 0.006
                + (actor.temperament.curiosity + actor.temperament.ambition) * 0.004,
            )
            pressure = max(0, actor.hunger - 65) + max(0, actor.thirst - 65)
            loneliness = max(0, 35 - actor.social)
            actor.stress = min(100, actor.stress + pressure * 0.0008 + loneliness * 0.0005)
        else:
            actor.stress = max(0, actor.stress - 0.08 * actor.temperament.resilience)
        if actor.stress > 82:
            actor.mood = "afraid" if actor.temperament.resilience < 0.55 else "sad"
            actor.confidence = max(0, actor.confidence - 0.008)
        if actor.profession == Profession.UNASSIGNED:
            actor.profession_satisfaction = max(0, actor.profession_satisfaction - 0.008)
        else:
            skill = actor.skills.get(str(actor.profession), 0)
            fulfillment = actor.values.get(self._profession_value(actor.profession), 50) / 100
            target = 35 + fulfillment * 45 + min(15, skill)
            actor.profession_satisfaction += (target - actor.profession_satisfaction) * 0.0008

    def _update_vocations(self) -> None:
        interval = self.config.vocation_review_interval_ticks
        if not interval or self.state.tick % interval:
            return
        humans = [human for human in self.state.living(EntityKind.HUMAN) if human.age_years >= 16]
        counts: dict[str, int] = {}
        for human in humans:
            counts[str(human.profession)] = counts.get(str(human.profession), 0) + 1
        for human in humans:
            if (
                human.profession != Profession.UNASSIGNED
                and human.profession_satisfaction >= 28
                and self.state.tick - human.last_vocation_tick < 1_500
            ):
                continue
            scores = self._vocation_scores(human, counts)
            chosen, chosen_score = max(scores.items(), key=lambda item: (item[1], item[0]))
            current_score = scores.get(str(human.profession), -1.0)
            if human.profession != Profession.UNASSIGNED and chosen_score < current_score + 0.18:
                continue
            previous = str(human.profession)
            human.profession = chosen
            human.profession_satisfaction = 58
            human.last_vocation_tick = self.state.tick
            human.goal = self._profession_goal(chosen)
            if human.goal not in human.aspirations:
                human.aspirations.append(human.goal)
                del human.aspirations[:-5]
            counts[previous] = max(0, counts.get(previous, 1) - 1)
            counts[chosen] = counts.get(chosen, 0) + 1
            human.remember(
                f"I chose the vocation of {chosen}",
                tick=self.state.tick,
                category="profession",
                importance=0.82,
                emotion="hopeful",
            )
            self.emit(
                "vocation_changed",
                human.id,
                previous=previous,
                profession=chosen,
                reason=self._profession_value(chosen),
            )

    def _vocation_scores(self, actor: Entity, counts: dict[str, int]) -> dict[str, float]:
        t = actor.temperament
        humans = self.state.living(EntityKind.HUMAN)
        population = max(1, len(humans))
        average_health = sum(human.health for human in humans) / population
        food_pressure = max(0.0, 1 - self._settlement_resource_total("food") / (population * 3))
        homeless = sum(1 for human in humans if not human.home_id) / population
        wars = sum(len(faction.rivals) for faction in self.state.factions.values()) // 2
        scores = {
            str(Profession.GATHERER): t.discipline + food_pressure * 0.6,
            str(Profession.FARMER): t.discipline + t.empathy * 0.3 + food_pressure,
            str(Profession.RANCHER): t.risk_tolerance + t.discipline * 0.5,
            str(Profession.BUILDER): t.creativity + t.discipline + homeless,
            str(Profession.CARPENTER): t.creativity * 0.7 + t.discipline,
            str(Profession.BLACKSMITH): t.discipline + t.ambition * 0.6,
            str(Profession.MERCHANT): t.sociability + t.ambition * 0.7,
            str(Profession.SCHOLAR): t.curiosity + t.discipline * 0.5 + actor.growth_drive / 100,
            str(Profession.HEALER): t.empathy + t.discipline * 0.4 + (100 - average_health) / 50,
            str(Profession.ARTIST): t.creativity + actor.values.get("beauty", 0) / 100,
            str(Profession.TEACHER): t.empathy
            + t.sociability * 0.5
            + min(0.8, sum(actor.skills.values()) / 20),
            str(Profession.DIPLOMAT): t.sociability + t.empathy * 0.7 + min(1, wars),
            str(Profession.GUARD): t.aggression + t.resilience * 0.7 + min(1, wars),
        }
        for rule in self.state.active_rules.values():
            if rule.get("category") != "profession":
                continue
            effects = rule.get("effects", {})
            scores[rule["id"]] = (
                t.curiosity * float(effects.get("knowledge_gain", 0))
                + t.creativity * float(effects.get("beauty_gain", 0))
                + t.empathy * float(effects.get("health_gain", 0))
                + t.sociability * float(effects.get("social_gain", 0))
                + t.empathy * float(effects.get("stress_relief", 0))
                + t.ambition * 0.5
            )
        scarcity_bonuses = {
            str(Profession.GATHERER): 1.0,
            str(Profession.FARMER): 0.8,
            str(Profession.BUILDER): 0.7 if homeless > 0.2 else 0.2,
            str(Profession.HEALER): 0.7 if average_health < 92 else 0.25,
        }
        for profession, bonus in scarcity_bonuses.items():
            if counts.get(profession, 0) == 0:
                scores[profession] += bonus
        return {
            profession: score - counts.get(profession, 0) * 0.7
            for profession, score in scores.items()
        }

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
        world_memory = {
            "drought": ("A drought threatened our water and food", 0.82, "afraid"),
            "wildfire": ("A wildfire scarred the surrounding land", 0.86, "afraid"),
            "epidemic": ("An epidemic struck the settlement", 0.9, "afraid"),
            "harvest": ("An abundant harvest renewed our hopes", 0.7, "hopeful"),
            "mineral_boom": ("New mineral deposits were discovered", 0.68, "curious"),
        }[event_type]
        for human in self.state.living(EntityKind.HUMAN):
            human.remember(
                world_memory[0],
                tick=self.state.tick,
                category="world_event",
                importance=world_memory[1],
                emotion=world_memory[2],
            )
            self._adapt_temperament(
                human,
                valence=1 if event_type in {"harvest", "mineral_boom"} else -1,
                intensity=0.35 if event_type in {"harvest", "mineral_boom"} else 0.65,
                source=event_type,
            )
        self.emit("world_event", event=event_type)

    def _apply_ai_results(self) -> None:
        if not self.ai_worker:
            return
        self._apply_reflection_results()
        for result in self.ai_worker.drain():
            entity = self.state.entities.get(result.entity_id)
            if not entity or not entity.alive:
                continue
            if entity.state != AgentState.AWAKE:
                entity.thinking = False
                self.emit("ai_rejected", entity.id, reason="agent is asleep")
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
            mundane = action.kind in {
                ActionType.IDLE,
                ActionType.MOVE,
                ActionType.EAT,
                ActionType.DRINK,
                ActionType.GATHER,
            }
            entity.remember(
                f"I decided to {action.kind}: {action.explanation}",
                tick=self.state.tick,
                category="decision",
                importance=0.25 if mundane else 0.68,
                emotion="neutral" if mundane else entity.mood,
                participants=[action.target_id] if action.target_id else [],
            )
            self.emit(
                "ai_decision",
                entity.id,
                action.target_id,
                action=action.kind,
                explanation=action.explanation,
                goal=entity.goal,
                mood=entity.mood,
            )

    def _apply_reflection_results(self) -> None:
        if not self.ai_worker:
            return
        for result in self.ai_worker.drain_reflections():
            entity = self.state.entities.get(result.entity_id)
            if not entity or not entity.alive:
                continue
            entity.reflection_pending = False
            if result.error or not result.reflection:
                self.emit("dream_error", entity.id, error=result.error or "empty reflection")
                self._create_deterministic_dream(entity, copy.deepcopy(entity))
                continue
            reflection = result.reflection
            important_ids = set(reflection.important_memory_ids)
            for memory in entity.long_term_memory + entity.short_term_memory:
                if memory.id in important_ids:
                    memory.importance = min(1.0, memory.importance + 0.18)
                    memory.recall_count += 1
                    memory.last_recalled_tick = self.state.tick
            entity.last_dream = reflection.dream
            entity.dreams.append(reflection.dream)
            del entity.dreams[:-8]
            entity.goal = reflection.new_goal
            if reflection.new_goal not in entity.aspirations:
                entity.aspirations.append(reflection.new_goal)
                del entity.aspirations[:-5]
            entity.mood = reflection.mood
            entity.self_awareness = min(100, entity.self_awareness + 4)
            entity.growth_drive = min(100, entity.growth_drive + 8)
            entity.remember(
                reflection.insight,
                tick=self.state.tick,
                category="insight",
                importance=0.9,
                emotion=reflection.mood,
            )
            entity.remember(
                reflection.dream,
                tick=self.state.tick,
                category="dream",
                importance=0.78,
                emotion=reflection.mood,
            )
            retained, forgotten = entity.consolidate_memories(self.state.tick)
            self.emit(
                "memory_consolidated",
                entity.id,
                retained=retained,
                forgotten=forgotten,
                ai_dream=True,
            )
            self.emit(
                "dream",
                entity.id,
                dream=reflection.dream,
                insight=reflection.insight,
                goal=reflection.new_goal,
                generated_by="qwen3:8b",
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
            and human.state == AgentState.AWAKE
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
            ActionType.TELL_STORY,
            ActionType.TEACH,
            ActionType.FORGIVE,
            ActionType.INSPIRE,
            ActionType.EXPRESS_AFFECTION,
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
        if action.kind == ActionType.ATTACK and target and not self._can_attack(actor, target):
            return "attack requires war, a serious grievance, hunger, or a violent temperament"
        if action.kind == ActionType.SABOTAGE and (
            not target or target.kind != EntityKind.BUILDING
        ):
            return "sabotage requires a building target"
        if action.kind == ActionType.BEAUTIFY and (
            not target or target.kind != EntityKind.BUILDING
        ):
            return "beautify requires a building target"
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
        if action.kind == ActionType.TELL_STORY and not actor.long_term_memory:
            return "telling a story requires a long-term memory"
        if action.kind == ActionType.TEACH and not actor.skills:
            return "teaching requires a learned skill"
        if (
            action.kind == ActionType.FORGIVE
            and target
            and actor.relationships.get(target.id, 0) >= 0
        ):
            return "forgive requires a grievance"
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
                    "relationship_type": (
                        actor.social_bonds[entity.id].label
                        if entity.id in actor.social_bonds
                        else "stranger"
                    ),
                    "trust": (
                        round(actor.social_bonds[entity.id].trust, 1)
                        if entity.id in actor.social_bonds
                        else 0
                    ),
                    "attraction": (
                        round(actor.social_bonds[entity.id].attraction, 1)
                        if entity.id in actor.social_bonds
                        else 0
                    ),
                    "fear": (
                        round(actor.social_bonds[entity.id].fear, 1)
                        if entity.id in actor.social_bonds
                        else 0
                    ),
                    "attack_allowed": self._can_attack(actor, entity),
                    "health": round(entity.health, 1),
                    "mood": entity.mood if entity.kind == EntityKind.HUMAN else None,
                    "goal": entity.goal if entity.kind == EntityKind.HUMAN else None,
                    "confidence": (
                        round(entity.confidence, 1) if entity.kind == EntityKind.HUMAN else None
                    ),
                    "stress": round(entity.stress, 1) if entity.kind == EntityKind.HUMAN else None,
                    "appearance_style": (
                        entity.appearance_style if entity.kind == EntityKind.HUMAN else None
                    ),
                    "inventory": entity.inventory if entity.kind == EntityKind.HUMAN else {},
                    "building_type": entity.building_type,
                    "beauty": round(entity.beauty, 1),
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
                "reflect": "consolidate recent experiences and forget low-value details",
                "tell_story": "share a defining long-term memory with a nearby human",
                "teach": "pass your strongest skill to a nearby human",
                "forgive": "soften a negative relationship with a nearby human",
                "study": "grow knowledge, skill, self-awareness, and possibly find a vocation",
                "self_care": "express identity by visibly changing style and accessory",
                "inspire": "share a value and aspiration with a nearby human",
                "beautify": "an artist improves a nearby building and its visual appearance",
                "express_affection": "reveal affection to someone; it may be returned or declined",
            },
            "legal_actions": self._legal_actions_for(actor, nearby_entities),
        }

    def _legal_actions_for(self, actor: Entity, nearby: list[Entity]) -> list[str]:
        actions = {
            ActionType.IDLE,
            ActionType.SLEEP,
            ActionType.EXPLORE,
            ActionType.STUDY,
            ActionType.SELF_CARE,
        }
        if actor.short_term_memory:
            actions.add(ActionType.REFLECT)
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
                    ActionType.INSPIRE,
                    ActionType.EXPRESS_AFFECTION,
                }
            )
            if any(self._can_attack(actor, human) for human in humans):
                actions.add(ActionType.ATTACK)
            if actor.long_term_memory:
                actions.add(ActionType.TELL_STORY)
            if actor.skills:
                actions.add(ActionType.TEACH)
            if any(actor.relationships.get(human.id, 0) < 0 for human in humans):
                actions.add(ActionType.FORGIVE)
        if any(
            entity.kind == EntityKind.COW and self._can_attack(actor, entity) for entity in nearby
        ):
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
            actions.add(ActionType.BEAUTIFY)
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
        humans = self.state.living(EntityKind.HUMAN)
        population = max(1, len(humans))
        return {
            "humans": len(humans),
            "cows": len(self.state.living(EntityKind.COW)),
            "buildings": sum(
                1 for item in self.state.entities.values() if item.kind == EntityKind.BUILDING
            ),
            "events": len(self.events),
            "factions": len(self.state.factions),
            "wars": sum(len(item.rivals) for item in self.state.factions.values()) // 2,
            "professions": len({str(human.profession) for human in humans}),
            "knowledge": round(sum(sum(human.knowledge.values()) for human in humans) / population),
            "stress": round(sum(human.stress for human in humans) / population),
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
            and entity.reproduction_drive >= 80
            and (
                actor.kind != EntityKind.HUMAN
                or (
                    actor.age_years >= 18
                    and entity.age_years >= 18
                    and actor.relationships.get(entity.id, 0) >= 12
                    and entity.relationships.get(actor.id, 0) >= 12
                )
            )
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
            "resilience": self.random.betavariate(1.8, 1.5),
            "discipline": self.random.betavariate(1.6, 1.6),
        }
        archetypes = {
            "aggression": "warrior",
            "sociability": "diplomat",
            "ambition": "leader",
            "curiosity": "explorer",
            "empathy": "caretaker",
            "creativity": "visionary",
            "risk_tolerance": "rebel",
            "resilience": "stoic",
            "discipline": "scholar",
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
            "resilience",
            "discipline",
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
            "resilience": "stoic",
            "discipline": "scholar",
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
            "stoic": "become resilient enough to protect what matters",
            "scholar": "understand myself and the world deeply",
        }.get(temperament.archetype, "survive and find a place in the world")

    @staticmethod
    def _initial_values(temperament: Temperament) -> dict[str, float]:
        return {
            "community": 25 + temperament.sociability * 55,
            "care": 25 + temperament.empathy * 55,
            "achievement": 25 + temperament.ambition * 55,
            "knowledge": 25 + temperament.curiosity * 55,
            "beauty": 25 + temperament.creativity * 55,
            "power": 20 + temperament.aggression * 55,
            "freedom": 25 + temperament.risk_tolerance * 55,
        }

    def _adapt_temperament(
        self, actor: Entity, *, valence: int, intensity: float, source: str
    ) -> None:
        intensity = max(0.0, min(1.0, intensity))
        previous_archetype = actor.temperament.archetype
        if valence >= 0:
            actor.temperament.empathy = min(1, actor.temperament.empathy + 0.012 * intensity)
            actor.temperament.sociability = min(
                1, actor.temperament.sociability + 0.009 * intensity
            )
            actor.temperament.resilience = min(1, actor.temperament.resilience + 0.014 * intensity)
            actor.temperament.curiosity = min(1, actor.temperament.curiosity + 0.006 * intensity)
            actor.confidence = min(100, actor.confidence + 2.5 * intensity)
            actor.stress = max(0, actor.stress - 5 * intensity)
        else:
            vulnerability = 1 - actor.temperament.resilience * 0.65
            actor.temperament.aggression = min(
                1, actor.temperament.aggression + 0.015 * intensity * vulnerability
            )
            actor.temperament.sociability = max(
                0, actor.temperament.sociability - 0.01 * intensity * vulnerability
            )
            actor.temperament.resilience = min(1, actor.temperament.resilience + 0.006 * intensity)
            actor.confidence = max(0, actor.confidence - 4 * intensity * vulnerability)
            actor.stress = min(100, actor.stress + 14 * intensity * vulnerability)
        self._refresh_archetype(actor)
        if intensity >= 0.4:
            self.emit(
                "temperament_changed",
                actor.id,
                source=source,
                valence=valence,
                archetype_before=previous_archetype,
                archetype_after=actor.temperament.archetype,
                stress=round(actor.stress, 1),
            )

    @staticmethod
    def _refresh_archetype(actor: Entity) -> None:
        archetypes = {
            "aggression": "warrior",
            "sociability": "diplomat",
            "ambition": "leader",
            "curiosity": "explorer",
            "empathy": "caretaker",
            "creativity": "visionary",
            "risk_tolerance": "rebel",
            "resilience": "stoic",
            "discipline": "scholar",
        }
        strongest = max(archetypes, key=lambda trait: getattr(actor.temperament, trait))
        actor.temperament.archetype = archetypes[strongest]

    def _evolve_goal(self, actor: Entity) -> None:
        if actor.profession != Profession.UNASSIGNED and actor.profession_satisfaction >= 45:
            goal = self._profession_goal(str(actor.profession))
        else:
            strongest = max(actor.values, key=actor.values.get, default="knowledge")
            goal = {
                "community": "create a community where nobody is isolated",
                "care": "learn how to heal and protect vulnerable people",
                "achievement": "master a difficult craft and leave a legacy",
                "knowledge": "understand the world and share what I discover",
                "beauty": "make myself and the settlement more beautiful",
                "power": "earn influence and reshape society",
                "freedom": "build a life independent of other people's rules",
            }[strongest]
        actor.goal = goal
        if goal not in actor.aspirations:
            actor.aspirations.append(goal)
            del actor.aspirations[:-5]

    @staticmethod
    def _profession_value(profession: str) -> str:
        return {
            str(Profession.SCHOLAR): "knowledge",
            str(Profession.HEALER): "care",
            str(Profession.ARTIST): "beauty",
            str(Profession.TEACHER): "knowledge",
            str(Profession.DIPLOMAT): "community",
            str(Profession.GUARD): "community",
            str(Profession.BUILDER): "achievement",
            str(Profession.CARPENTER): "achievement",
            str(Profession.BLACKSMITH): "achievement",
            str(Profession.MERCHANT): "freedom",
        }.get(str(profession), "care")

    @staticmethod
    def _profession_goal(profession: str) -> str:
        return {
            str(Profession.SCHOLAR): "study the world and preserve its knowledge",
            str(Profession.HEALER): "keep the community healthy and ease suffering",
            str(Profession.ARTIST): "bring beauty and meaning into everyday life",
            str(Profession.TEACHER): "help others discover what they can become",
            str(Profession.DIPLOMAT): "resolve conflicts and connect divided people",
            str(Profession.GUARD): "protect the settlement without becoming cruel",
            str(Profession.BUILDER): "give every person a safe and beautiful home",
            str(Profession.FARMER): "make sure the community never goes hungry",
            str(Profession.GATHERER): "provide what the settlement needs to endure",
        }.get(str(profession), f"master the vocation of {profession}")

    @staticmethod
    def _in_range(first: Entity, second: Entity, distance: float) -> bool:
        return first.position.distance_to(second.position) <= distance

    def _has_urgent_survival_need(self, actor: Entity) -> bool:
        if actor.thirst >= 55 or actor.energy <= 22:
            return True
        if actor.kind == EntityKind.COW:
            return actor.hunger >= 48
        return actor.hunger >= 70 or (
            actor.hunger >= 55 and self._inventory_total(actor, ("food", "meat")) > 0
        )

    def _can_attack(self, actor: Entity, target: Entity) -> bool:
        if not target.alive or actor.id == target.id:
            return False
        if target.kind == EntityKind.COW:
            return actor.hunger >= 60 or (
                actor.temperament.aggression >= 0.86 and actor.temperament.risk_tolerance >= 0.72
            )
        if target.kind != EntityKind.HUMAN or actor.kind != EntityKind.HUMAN:
            return False
        own_faction = self.state.factions.get(actor.faction_id or "")
        at_war = bool(own_faction and target.faction_id and target.faction_id in own_faction.rivals)
        bond = actor.social_bonds.get(target.id)
        serious_grievance = actor.relationships.get(target.id, 0) <= -20 or bool(
            bond and (bond.affinity <= -20 or bond.trust <= -25)
        )
        violent_impulse = (
            actor.temperament.aggression >= 0.82
            and actor.temperament.empathy <= 0.38
            and actor.temperament.risk_tolerance >= 0.68
        )
        return at_war or serious_grievance or violent_impulse

    @staticmethod
    def _inventory_total(entity: Entity, resources: tuple[str, ...]) -> int:
        return sum(entity.inventory.get(resource, 0) for resource in resources)

    def _settlement_resource_total(self, resource: str) -> int:
        return sum(
            human.inventory.get(resource, 0) for human in self.state.living(EntityKind.HUMAN)
        )

    def _social_bond(self, actor: Entity, target: Entity) -> SocialBond:
        bond = actor.social_bonds.get(target.id)
        if bond is None:
            bond = SocialBond(
                target_id=target.id,
                affinity=actor.relationships.get(target.id, 0.0),
            )
            actor.social_bonds[target.id] = bond
        return bond

    def _update_bond(
        self,
        actor: Entity,
        target: Entity,
        *,
        affinity: float = 0,
        trust: float = 0,
        attraction: float = 0,
        respect: float = 0,
        fear: float = 0,
        familiarity: float = 0,
        event: str,
        add_roles: tuple[str, ...] = (),
        remove_roles: tuple[str, ...] = (),
    ) -> SocialBond:
        bond = self._social_bond(actor, target)
        previous_label = bond.label
        bond.affinity = max(-100, min(100, bond.affinity + affinity))
        bond.trust = max(-100, min(100, bond.trust + trust))
        bond.attraction = max(-100, min(100, bond.attraction + attraction))
        bond.respect = max(-100, min(100, bond.respect + respect))
        bond.fear = max(0, min(100, bond.fear + fear))
        bond.familiarity = max(0, min(100, bond.familiarity + familiarity))
        bond.interaction_count += 1
        bond.last_interaction_tick = self.state.tick
        for role in remove_roles:
            bond.roles = [item for item in bond.roles if item != role]
        for role in add_roles:
            if role not in bond.roles:
                bond.roles.append(role)
        bond.history.append(f"[{self.state.tick}] {event}")
        del bond.history[:-12]
        actor.relationships[target.id] = bond.affinity
        if previous_label != bond.label:
            self.emit(
                "relationship_changed",
                actor.id,
                target.id,
                previous=previous_label,
                relationship=bond.label,
                affinity=round(bond.affinity, 1),
                trust=round(bond.trust, 1),
                attraction=round(bond.attraction, 1),
            )
        return bond

    def social_graph(self) -> dict[str, list[dict[str, object]]]:
        humans = {human.id: human for human in self.state.living(EntityKind.HUMAN)}
        nodes = [
            {
                "id": human.id,
                "name": human.name,
                "profession": str(human.profession),
                "faction_id": human.faction_id,
                "x": round(human.position.x, 2),
                "y": round(human.position.y, 2),
            }
            for human in humans.values()
        ]
        edges = []
        for source in humans.values():
            for target_id, bond in source.social_bonds.items():
                if target_id not in humans or bond.label == "stranger":
                    continue
                edges.append(
                    {
                        "source": source.id,
                        "target": target_id,
                        "relationship": bond.label,
                        "affinity": round(bond.affinity, 2),
                        "trust": round(bond.trust, 2),
                        "attraction": round(bond.attraction, 2),
                        "respect": round(bond.respect, 2),
                        "fear": round(bond.fear, 2),
                        "familiarity": round(bond.familiarity, 2),
                        "interaction_count": bond.interaction_count,
                        "last_interaction_tick": bond.last_interaction_tick,
                        "roles": list(bond.roles),
                        "history": list(bond.history),
                    }
                )
        return {"nodes": nodes, "edges": edges}
