from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from game_of_life.ai.scheduler import AIWorker
from game_of_life.models import Entity, EntityKind, Profession
from game_of_life.rules import RuleProposal, RuleRegistry, RuleValidation

if TYPE_CHECKING:
    from game_of_life.engine import Simulation


@dataclass(slots=True)
class InnovationManager:
    worker: AIWorker
    registry: RuleRegistry = field(default_factory=RuleRegistry)
    interval_ticks: int = 1_000
    _hydrated: bool = False
    _baselines: dict[str, tuple[int, dict[str, int]]] = field(default_factory=dict)

    def step(self, simulation: Simulation) -> None:
        self._hydrate(simulation)
        for result in self.worker.drain_rules():
            if result.error or not result.proposal:
                simulation.emit("rule_error", error=result.error or "empty proposal")
                continue
            validation = self._shadow_validate(result.proposal, simulation)
            if not validation.accepted:
                self.registry.rejected[result.proposal.id] = validation.reasons
                simulation.emit(
                    "rule_rejected",
                    rule_id=result.proposal.id,
                    reasons=list(validation.reasons),
                )
                continue
            self.registry.activate(result.proposal)
            definition = result.proposal.model_dump(mode="json")
            simulation.state.active_rules[result.proposal.id] = definition
            self._baselines[result.proposal.id] = (
                simulation.state.tick,
                self._resource_totals(simulation),
            )
            self._assign_profession(result.proposal, simulation, result.proposer_id)
            simulation.emit(
                "rule_activated",
                result.proposer_id,
                rule_id=result.proposal.id,
                definition=definition,
            )

        self._monitor(simulation)
        if simulation.state.tick and simulation.state.tick % self.interval_ticks == 0:
            shortage = self._largest_shortage(simulation)
            if shortage:
                self.worker.submit_rule(
                    {
                        "tick": simulation.state.tick,
                        "seed": simulation.state.seed,
                        "population": len(simulation.state.living(EntityKind.HUMAN)),
                        "shortage": shortage,
                        "resources": self._resource_totals(simulation),
                        "existing_rules": sorted(self.registry.active),
                    }
                )

    def request_from_actor(self, simulation: Simulation, actor: Entity) -> bool:
        return self.worker.submit_rule(
            {
                "tick": simulation.state.tick,
                "seed": simulation.state.seed,
                "population": len(simulation.state.living(EntityKind.HUMAN)),
                "resources": self._resource_totals(simulation),
                "existing_rules": sorted(self.registry.active),
                "proposer_id": actor.id,
                "proposer_name": actor.name,
                "proposer_goal": actor.goal,
                "proposer_profession": actor.profession,
                "proposer_temperament": actor.temperament.archetype,
                "opportunity": (
                    "Create a surprising but useful change consistent with the proposer."
                ),
            }
        )

    def _hydrate(self, simulation: Simulation) -> None:
        if self._hydrated:
            return
        for definition in simulation.state.active_rules.values():
            proposal = RuleProposal.model_validate(definition)
            self.registry.active[proposal.id] = proposal
        self._hydrated = True

    def _shadow_validate(self, proposal: RuleProposal, simulation: Simulation) -> RuleValidation:
        validation = self.registry.validate(proposal)
        if not validation.accepted:
            return validation
        population = max(1, len(simulation.state.living(EntityKind.HUMAN)))
        projected_cycles = 1_000 / proposal.duration_ticks * population
        projected_output = sum(proposal.outputs.values()) * projected_cycles
        if projected_output > max(2_000, population * 150):
            return RuleValidation(False, ("shadow simulation predicts runaway production",))
        return validation

    def _monitor(self, simulation: Simulation) -> None:
        totals = self._resource_totals(simulation)
        population = max(1, len(simulation.state.living(EntityKind.HUMAN)))
        for rule_id, (activation_tick, baseline) in list(self._baselines.items()):
            if simulation.state.tick - activation_tick > 2_000:
                del self._baselines[rule_id]
                continue
            proposal = self.registry.active.get(rule_id)
            if not proposal:
                continue
            runaway = any(
                totals.get(resource, 0) - baseline.get(resource, 0) > population * 100 + 500
                for resource in proposal.outputs
            )
            if runaway:
                self.registry.rollback(rule_id)
                simulation.state.active_rules.pop(rule_id, None)
                del self._baselines[rule_id]
                simulation.emit("rule_rollback", rule_id=rule_id, reason="runaway production")

    @staticmethod
    def _assign_profession(
        proposal: RuleProposal, simulation: Simulation, preferred_id: str | None = None
    ) -> None:
        if proposal.category != "profession":
            return
        humans = simulation.state.living(EntityKind.HUMAN)
        candidate = simulation.state.entities.get(preferred_id or "")
        if candidate and (not candidate.alive or candidate.kind != EntityKind.HUMAN):
            candidate = None
        candidate = candidate or next(
            (human for human in humans if human.profession == Profession.UNASSIGNED), None
        )
        candidate = candidate or next(
            (human for human in humans if human.profession == Profession.MERCHANT), None
        )
        if candidate:
            candidate.profession = proposal.id
            candidate.remember(
                f"I became a {proposal.name} to address: {proposal.activation_reason}",
                tick=simulation.state.tick,
                category="profession",
                importance=0.85,
                emotion="proud",
            )

    @staticmethod
    def _resource_totals(simulation: Simulation) -> dict[str, int]:
        totals: dict[str, int] = {}
        for human in simulation.state.living(EntityKind.HUMAN):
            for resource, amount in human.inventory.items():
                totals[resource] = totals.get(resource, 0) + amount
        return totals

    def _largest_shortage(self, simulation: Simulation) -> dict[str, float | str] | None:
        population = max(1, len(simulation.state.living(EntityKind.HUMAN)))
        targets = {"food": 4, "water": 2, "wood": 5, "stone": 2, "tools": 1}
        totals = self._resource_totals(simulation)
        ratios = {
            resource: totals.get(resource, 0) / (per_person * population)
            for resource, per_person in targets.items()
        }
        resource, ratio = min(ratios.items(), key=lambda item: item[1])
        if ratio >= 0.75:
            return None
        return {"resource": resource, "coverage_ratio": round(ratio, 3)}
