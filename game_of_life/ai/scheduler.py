from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import Any

from game_of_life.ai.client import AgentIntent, AIClient
from game_of_life.models import Entity
from game_of_life.rules import RuleProposal


@dataclass(frozen=True, slots=True)
class DecisionResult:
    entity_id: str
    intent: AgentIntent | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RuleResult:
    proposal: RuleProposal | None
    error: str | None = None
    proposer_id: str | None = None


class AIWorker:
    def __init__(self, client: AIClient, max_pending: int = 8) -> None:
        self._client = client
        self._requests: Queue[tuple[str, Entity | None, dict[str, Any]]] = Queue(
            maxsize=max_pending
        )
        self._results: Queue[DecisionResult] = Queue()
        self._rule_results: Queue[RuleResult] = Queue()
        self._pending: set[str] = set()
        self._rule_pending = False
        self._stopped = Event()
        self._thread = Thread(target=self._run, name="ollama-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def pending_count(self) -> int:
        return len(self._pending) + int(self._rule_pending)

    def is_pending(self, entity_id: str) -> bool:
        return entity_id in self._pending

    def submit(self, entity: Entity, context: dict[str, Any]) -> bool:
        if entity.id in self._pending:
            return False
        try:
            self._requests.put_nowait(("decision", entity, context))
        except Full:
            return False
        self._pending.add(entity.id)
        return True

    def submit_rule(self, context: dict[str, Any]) -> bool:
        if self._rule_pending:
            return False
        try:
            self._requests.put_nowait(("rule", None, context))
        except Full:
            return False
        self._rule_pending = True
        return True

    def drain(self) -> list[DecisionResult]:
        results: list[DecisionResult] = []
        while True:
            try:
                result = self._results.get_nowait()
            except Empty:
                break
            self._pending.discard(result.entity_id)
            results.append(result)
        return results

    def drain_rules(self) -> list[RuleResult]:
        results: list[RuleResult] = []
        while True:
            try:
                result = self._rule_results.get_nowait()
            except Empty:
                break
            self._rule_pending = False
            results.append(result)
        return results

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                job_type, entity, context = self._requests.get(timeout=0.1)
            except Empty:
                continue
            try:
                if job_type == "rule":
                    self._rule_results.put(
                        RuleResult(
                            self._client.propose_rule(context),
                            proposer_id=context.get("proposer_id"),
                        )
                    )
                elif entity is not None:
                    intent = self._client.decide(entity, context)
                    self._results.put(DecisionResult(entity.id, intent))
            except Exception as exc:
                if job_type == "rule":
                    self._rule_results.put(
                        RuleResult(None, str(exc), proposer_id=context.get("proposer_id"))
                    )
                elif entity is not None:
                    self._results.put(DecisionResult(entity.id, None, str(exc)))
