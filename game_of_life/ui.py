from __future__ import annotations

from dataclasses import dataclass

import pygame

from game_of_life.engine import Simulation
from game_of_life.models import AgentState, Entity, EntityKind

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
    graph_mode: bool = False

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
            elif event.key == pygame.K_g:
                self.graph_mode = not self.graph_mode
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            if x < self.simulation.state.width:
                self.selected_id = self._select_at(x, y)
        return True

    def draw(self) -> None:
        if self.graph_mode:
            self.screen.fill((18, 24, 32))
            self._draw_social_graph()
        else:
            self.screen.fill((42, 145, 72))
            for entity in self.simulation.state.entities.values():
                if entity.alive:
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
            if entity.beauty:
                accent = self._hue_color(entity.appearance_hue, saturation=70, value=95)
                pygame.draw.rect(self.screen, accent, (x - 7, y - 6, 5, 6), 2)
                pygame.draw.rect(self.screen, accent, (x + 4, y - 6, 5, 6), 2)
                if entity.beauty >= 40:
                    pygame.draw.circle(self.screen, accent, (x, y + 8), 3)
            pygame.draw.polygon(
                self.screen, (110, 50, 35), ((x - 13, y - 10), (x, y - 22), (x + 15, y - 10))
            )
        elif entity.kind == EntityKind.HUMAN:
            self._draw_human(entity, x, y)
        else:
            pygame.draw.circle(self.screen, color, (x, y), 6)
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
        self._text(
            f"Fazioni {stats['factions']}   Guerre {stats['wars']}   Lavori {stats['professions']}",
            left + 16,
            90,
            size=14,
            color=(235, 150, 135),
        )
        resources = self._settlement_resources()
        resource_line = "  ".join(
            f"{key}:{resources.get(key, 0)}" for key in ("food", "wood", "stone", "tools")
        )
        self._text(resource_line, left + 16, 108, size=14, color=(180, 190, 170))
        self._text(
            f"Conoscenza {stats['knowledge']}   Stress medio {stats['stress']}",
            left + 16,
            122,
            size=13,
            color=(160, 205, 220),
        )
        self._text("SPAZIO pausa  +/- velocità  G grafo", left + 16, 140, color=(155, 165, 175))

        y = 166
        selected = self.simulation.state.entities.get(self.selected_id or "")
        if self.graph_mode:
            self._draw_social_panel(left, y, selected)
            return
        if selected:
            self._text("AGENTE", left + 16, y, color=(100, 190, 255))
            details = (
                f"{selected.name or selected.id} ({selected.kind})",
                f"Età {selected.age_years:.1f}  Salute {selected.health:.0f}",
                f"Fame {selected.hunger:.0f}  Sete {selected.thirst:.0f}",
                f"Energia {selected.energy:.0f}  Sociale {selected.social:.0f}",
                f"Professione: {selected.profession} ({selected.profession_satisfaction:.0f}%)",
                f"Temperamento: {selected.temperament.archetype}",
                f"Umore: {selected.mood}",
                f"Coscienza {selected.self_awareness:.0f}  Crescita {selected.growth_drive:.0f}",
                f"Fiducia {selected.confidence:.0f}  Stress {selected.stress:.0f}",
                f"Estetica {selected.aesthetic_need:.0f}  Stile {selected.appearance_style}",
                f"Fazione: {selected.faction_id or '-'}",
                f"Stato: {selected.state}",
                f"Azione: {'THINKING' if selected.thinking else selected.action.kind}",
                f"Obiettivo: {selected.goal[:34]}",
                f"Inventario: {selected.inventory}",
                f"Conoscenze: {sum(selected.knowledge.values()):.1f}",
            )
            for line in details:
                y += 18
                self._text(line, left + 16, y, size=15)
            memories = selected.short_term_memory + selected.long_term_memory
            if memories:
                y += 30
                self._text(
                    f"MEMORIA breve {len(selected.short_term_memory)} / lunga "
                    f"{len(selected.long_term_memory)}",
                    left + 16,
                    y,
                    color=(100, 190, 255),
                )
                y += 22
                memory = max(memories, key=lambda item: (item.importance, item.tick))
                self._text(memory.summary[:42], left + 16, y, size=14)
            if selected.last_dream:
                y += 24
                self._text("SOGNO", left + 16, y, color=(205, 150, 255))
                y += 19
                self._text(selected.last_dream[:42], left + 16, y, size=13)
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

    def _draw_human(self, entity: Entity, x: int, y: int) -> None:
        outfit = self._hue_color(entity.appearance_hue, saturation=62, value=90)
        skin = (224, 177, 132)
        if entity.appearance_style in {"elegant", "artistic"}:
            pygame.draw.polygon(self.screen, outfit, ((x, y - 1), (x - 7, y + 8), (x + 7, y + 8)))
        elif entity.appearance_style == "bold":
            pygame.draw.rect(self.screen, outfit, (x - 7, y - 1, 14, 9), border_radius=2)
        else:
            pygame.draw.circle(self.screen, outfit, (x, y + 3), 7)
        pygame.draw.circle(self.screen, skin, (x, y - 5), 4)
        if entity.appearance_style == "scholarly":
            pygame.draw.line(self.screen, (50, 45, 40), (x - 4, y - 5), (x + 4, y - 5), 1)
        if entity.accessory == "hat":
            pygame.draw.rect(self.screen, (70, 50, 35), (x - 6, y - 11, 12, 2))
            pygame.draw.rect(self.screen, (70, 50, 35), (x - 3, y - 15, 7, 5))
        elif entity.accessory == "ribbon":
            pygame.draw.circle(self.screen, (245, 90, 145), (x + 5, y - 8), 2)
        elif entity.accessory == "glasses":
            pygame.draw.circle(self.screen, (50, 55, 65), (x - 2, y - 5), 2, 1)
            pygame.draw.circle(self.screen, (50, 55, 65), (x + 3, y - 5), 2, 1)
        elif entity.accessory == "scarf":
            pygame.draw.line(self.screen, (230, 80, 70), (x - 4, y), (x + 5, y + 2), 2)
        elif entity.accessory == "flower":
            pygame.draw.circle(self.screen, (255, 170, 210), (x + 4, y - 9), 2)
        self._text(entity.name, x - 12, y - 23, size=13)
        if entity.faction_id:
            pygame.draw.circle(self.screen, self._faction_color(entity.faction_id), (x, y), 11, 2)
        if entity.thinking:
            self._text("...", x - 5, y + 10, size=15, color=(120, 210, 255))
        elif entity.state == AgentState.SLEEPING:
            self._text("zZ", x - 5, y + 10, size=15, color=(170, 190, 255))
        elif entity.state == AgentState.DREAMING:
            self._text("*", x - 2, y + 10, size=18, color=(205, 150, 255))

    def _draw_social_graph(self) -> None:
        graph = self.simulation.social_graph()
        nodes = {node["id"]: node for node in graph["nodes"]}
        priority = {
            "love": 9,
            "family": 8,
            "hate": 7,
            "fear": 6,
            "faction_rival": 5,
            "rival": 5,
            "mentor": 4,
            "student": 4,
            "partner": 4,
            "friend": 3,
            "faction_ally": 2,
            "acquaintance": 1,
        }
        pairs: dict[frozenset[str], dict[str, object]] = {}
        for edge in graph["edges"]:
            pair = frozenset((str(edge["source"]), str(edge["target"])))
            current = pairs.get(pair)
            if current is None or priority.get(str(edge["relationship"]), 0) > priority.get(
                str(current["relationship"]), 0
            ):
                pairs[pair] = edge
        for edge in pairs.values():
            source = nodes.get(edge["source"])
            target = nodes.get(edge["target"])
            if not source or not target:
                continue
            relationship = str(edge["relationship"])
            color = self._relationship_color(relationship)
            start = (round(float(source["x"])), round(float(source["y"])))
            end = (round(float(target["x"])), round(float(target["y"])))
            pygame.draw.line(
                self.screen,
                color,
                start,
                end,
                3 if relationship in {"love", "family", "hate"} else 1,
            )
            if self.selected_id in {edge["source"], edge["target"]}:
                midpoint = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
                self._text(relationship, midpoint[0], midpoint[1], size=13, color=color)
        for human in self.simulation.state.living(EntityKind.HUMAN):
            self._draw_human(human, round(human.position.x), round(human.position.y))
            if human.id == self.selected_id:
                pygame.draw.circle(
                    self.screen,
                    (255, 220, 40),
                    (round(human.position.x), round(human.position.y)),
                    14,
                    2,
                )

    def _draw_social_panel(self, left: int, y: int, selected: Entity | None) -> None:
        graph = self.simulation.social_graph()
        counts: dict[str, int] = {}
        for edge in graph["edges"]:
            relationship = str(edge["relationship"])
            counts[relationship] = counts.get(relationship, 0) + 1
        self._text("GRAFO SOCIALE", left + 16, y, color=(235, 135, 190))
        y += 24
        summary = "  ".join(
            f"{name}:{counts.get(name, 0)}" for name in ("love", "friend", "family", "hate")
        )
        self._text(summary, left + 16, y, size=14)
        y += 26
        if not selected or selected.kind != EntityKind.HUMAN:
            self._text("Seleziona una persona per vedere i legami", left + 16, y, size=14)
            return
        self._text(selected.name, left + 16, y, color=(100, 190, 255))
        bonds = sorted(
            selected.social_bonds.values(),
            key=lambda bond: abs(bond.affinity) + abs(bond.trust) + bond.attraction + bond.fear,
            reverse=True,
        )
        for bond in bonds[:14]:
            target = self.simulation.state.entities.get(bond.target_id)
            if not target:
                continue
            y += 22
            color = self._relationship_color(bond.label)
            self._text(f"{target.name}: {bond.label}", left + 16, y, size=15, color=color)
            y += 16
            self._text(
                f"Aff {bond.affinity:.0f}  Fid {bond.trust:.0f}  "
                f"Attr {bond.attraction:.0f}  Paura {bond.fear:.0f}",
                left + 26,
                y,
                size=13,
                color=(175, 185, 195),
            )

    @staticmethod
    def _relationship_color(relationship: str) -> tuple[int, int, int]:
        return {
            "love": (255, 80, 155),
            "family": (90, 175, 255),
            "friend": (80, 220, 130),
            "hate": (245, 55, 55),
            "fear": (155, 80, 200),
            "rival": (245, 145, 55),
            "faction_rival": (245, 110, 55),
            "mentor": (190, 135, 255),
            "student": (155, 125, 220),
            "partner": (245, 115, 180),
            "faction_ally": (80, 185, 180),
            "acquaintance": (105, 120, 135),
        }.get(relationship, (120, 130, 145))

    @staticmethod
    def _hue_color(hue: int, *, saturation: int, value: int) -> tuple[int, int, int]:
        color = pygame.Color(0)
        color.hsva = (hue % 360, saturation, value, 100)
        return color.r, color.g, color.b

    def _settlement_resources(self) -> dict[str, int]:
        resources: dict[str, int] = {}
        for entity in self.simulation.state.living(EntityKind.HUMAN):
            for resource, amount in entity.inventory.items():
                resources[resource] = resources.get(resource, 0) + amount
        return resources

    @staticmethod
    def _faction_color(faction_id: str) -> tuple[int, int, int]:
        value = sum((index + 1) * ord(character) for index, character in enumerate(faction_id))
        return (80 + value % 176, 80 + (value // 3) % 176, 80 + (value // 7) % 176)

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
