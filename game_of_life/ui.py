from __future__ import annotations

from dataclasses import dataclass

import pygame

from game_of_life.engine import Simulation
from game_of_life.models import Entity, EntityKind

COLORS = {
    EntityKind.HUMAN: (235, 210, 120),
    EntityKind.COW: (245, 245, 245),
    EntityKind.TREE: (30, 125, 55),
    EntityKind.ROCK: (120, 120, 125),
    EntityKind.LAKE: (40, 120, 220),
    EntityKind.BUILDING: (155, 95, 55),
}


@dataclass(slots=True)
class SimulationUI:
    simulation: Simulation
    screen: pygame.Surface
    selected_id: str | None = None
    paused: bool = False
    speed: int = 1

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key in {pygame.K_PLUS, pygame.K_EQUALS}:
                self.speed = min(8, self.speed * 2)
            elif event.key == pygame.K_MINUS:
                self.speed = max(1, self.speed // 2)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            if x < self.simulation.state.width:
                self.selected_id = self._select_at(x, y)
        return True

    def draw(self) -> None:
        self.screen.fill((42, 145, 72))
        for entity in self.simulation.state.entities.values():
            if entity.alive or not entity.is_living:
                self._draw_entity(entity)
        self._draw_panel()
        pygame.display.flip()

    def _draw_entity(self, entity: Entity) -> None:
        x, y = round(entity.position.x), round(entity.position.y)
        color = COLORS[entity.kind]
        if entity.kind == EntityKind.LAKE:
            pygame.draw.circle(self.screen, color, (x, y), 18)
        elif entity.kind == EntityKind.TREE:
            pygame.draw.polygon(self.screen, color, ((x, y - 10), (x - 8, y + 8), (x + 8, y + 8)))
        elif entity.kind == EntityKind.ROCK:
            pygame.draw.circle(self.screen, color, (x, y), 7)
        elif entity.kind == EntityKind.BUILDING:
            pygame.draw.rect(self.screen, color, (x - 10, y - 10, 22, 22))
            pygame.draw.polygon(
                self.screen, (110, 50, 35), ((x - 13, y - 10), (x, y - 22), (x + 15, y - 10))
            )
        else:
            pygame.draw.circle(self.screen, color, (x, y), 6)
            if entity.kind == EntityKind.HUMAN:
                self._text(entity.name, x - 12, y - 18, size=13)
        if entity.id == self.selected_id:
            pygame.draw.circle(self.screen, (255, 220, 40), (x, y), 12, 2)

    def _draw_panel(self) -> None:
        left = self.simulation.state.width
        pygame.draw.rect(
            self.screen,
            (22, 27, 34),
            (left, 0, self.screen.get_width() - left, self.screen.get_height()),
        )
        self._text("GAME OF LIFE AI", left + 16, 14, size=24, color=(240, 220, 120))
        status = "PAUSA" if self.paused else f"RUN x{self.speed}"
        self._text(f"Tick {self.simulation.state.tick}  |  {status}", left + 16, 48)
        stats = self.simulation.statistics()
        self._text(
            f"Umani {stats['humans']}   Mucche {stats['cows']}   Case {stats['buildings']}",
            left + 16,
            72,
        )
        resources = self._settlement_resources()
        resource_line = "  ".join(
            f"{key}:{resources.get(key, 0)}" for key in ("food", "wood", "stone", "tools")
        )
        self._text(resource_line, left + 16, 94, size=14, color=(180, 190, 170))
        self._text("SPAZIO pausa   +/- velocità", left + 16, 114, color=(155, 165, 175))

        y = 142
        selected = self.simulation.state.entities.get(self.selected_id or "")
        if selected:
            self._text("AGENTE", left + 16, y, color=(100, 190, 255))
            details = (
                f"{selected.name or selected.id} ({selected.kind})",
                f"Età {selected.age_years:.1f}  Salute {selected.health:.0f}",
                f"Fame {selected.hunger:.0f}  Sete {selected.thirst:.0f}",
                f"Energia {selected.energy:.0f}  Sociale {selected.social:.0f}",
                f"Professione: {selected.profession}",
                f"Azione: {selected.action.kind}",
                f"Inventario: {selected.inventory}",
            )
            for line in details:
                y += 22
                self._text(line, left + 16, y)
            if selected.memories:
                y += 30
                self._text("ULTIMO RICORDO", left + 16, y, color=(100, 190, 255))
                y += 22
                self._text(selected.memories[-1][:42], left + 16, y, size=14)
            y += 38

        if self.simulation.state.active_rules:
            self._text("REGOLE ATTIVE", left + 16, y, color=(170, 130, 255))
            for rule in list(self.simulation.state.active_rules.values())[-3:]:
                y += 19
                self._text(f"{rule['name']} v{rule['version']}", left + 16, y, size=13)
            y += 28

        self._text("EVENTI", left + 16, y, color=(100, 190, 255))
        max_events = max(3, (self.screen.get_height() - y - 28) // 20)
        for event in reversed(self.simulation.events[-max_events:]):
            y += 20
            label = f"[{event.tick}] {event.event_type}: {event.actor_id or '-'}"
            self._text(label[:44], left + 16, y, size=13, color=(190, 195, 205))

    def _select_at(self, x: int, y: int) -> str | None:
        candidates = [
            entity
            for entity in self.simulation.state.entities.values()
            if entity.alive
            and abs(entity.position.x - x) <= 12
            and abs(entity.position.y - y) <= 12
        ]
        if not candidates:
            return None
        return min(
            candidates, key=lambda item: item.position.distance_to(type(item.position)(x, y))
        ).id

    def _settlement_resources(self) -> dict[str, int]:
        resources: dict[str, int] = {}
        for entity in self.simulation.state.living(EntityKind.HUMAN):
            for resource, amount in entity.inventory.items():
                resources[resource] = resources.get(resource, 0) + amount
        return resources

    def _text(
        self,
        text: str,
        x: int,
        y: int,
        *,
        size: int = 16,
        color: tuple[int, int, int] = (235, 235, 235),
    ) -> None:
        font = pygame.font.Font(None, size)
        self.screen.blit(font.render(str(text), True, color), (x, y))
