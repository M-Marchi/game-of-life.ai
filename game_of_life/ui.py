from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, pi, sin

import pygame

from game_of_life.engine import Simulation
from game_of_life.models import AgentState, Entity, EntityKind

INK = (229, 235, 239)
MUTED = (132, 148, 158)
PANEL = (14, 21, 29)
PANEL_CARD = (23, 32, 42)
CYAN = (77, 205, 214)
GOLD = (244, 193, 92)
VIOLET = (180, 133, 255)
CORAL = (244, 120, 105)


@dataclass(slots=True)
class SimulationUI:
    simulation: Simulation
    screen: pygame.Surface
    selected_id: str | None = None
    paused: bool = False
    speed: int = 1
    insight_mode: bool = False
    _fonts: dict[tuple[int, bool], pygame.font.Font] = field(default_factory=dict, init=False)

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
            elif event.key in {pygame.K_i, pygame.K_TAB}:
                self.insight_mode = not self.insight_mode
            elif event.key == pygame.K_ESCAPE:
                self.selected_id = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            if x < self.simulation.state.width:
                self.selected_id = self._select_at(x, y)
            elif 40 <= y <= 70:
                panel_x = x - self.simulation.state.width
                self.insight_mode = panel_x >= self.simulation.config.panel_width // 2
        return True

    def draw(self) -> None:
        self._draw_world(insight=self.insight_mode)
        if self.insight_mode:
            self._draw_insight_overlay()
        self._draw_top_hud()
        self._draw_panel()
        pygame.display.flip()

    def _draw_world(self, *, insight: bool) -> None:
        phase = str(self.simulation.world_time()["phase"])
        palettes = {
            "dawn": ((31, 66, 69), (80, 107, 77)),
            "day": ((31, 82, 71), (70, 113, 75)),
            "dusk": ((43, 53, 67), (103, 82, 67)),
            "night": ((10, 24, 39), (22, 45, 54)),
        }
        top, bottom = palettes[phase]
        if insight:
            top = tuple(max(7, channel // 3) for channel in top)
            bottom = tuple(max(12, channel // 3) for channel in bottom)
        self._vertical_gradient(top, bottom, self.simulation.state.width)
        self._draw_terrain_grid(insight)

        for entity in self.simulation.state.entities.values():
            if not entity.alive or (
                insight and entity.kind not in {EntityKind.HUMAN, EntityKind.BUILDING}
            ):
                continue
            self._draw_entity(entity, subdued=insight and entity.kind != EntityKind.HUMAN)

    def _vertical_gradient(
        self, top: tuple[int, int, int], bottom: tuple[int, int, int], width: int
    ) -> None:
        height = self.screen.get_height()
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(round(a + (b - a) * ratio) for a, b in zip(top, bottom, strict=True))
            pygame.draw.line(self.screen, color, (0, y), (width, y))

    def _draw_terrain_grid(self, insight: bool) -> None:
        width = self.simulation.state.width
        height = self.simulation.state.height
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        grid_color = (142, 205, 173, 10 if insight else 16)
        for x in range(32, width, 64):
            pygame.draw.line(overlay, grid_color, (x, 0), (x, height))
        for y in range(32, height, 64):
            pygame.draw.line(overlay, grid_color, (0, y), (width, y))
        for x in range(26, width, 96):
            for y in range(34, height, 88):
                pygame.draw.circle(overlay, (181, 218, 172, 14), (x, y), 2)
        self.screen.blit(overlay, (0, 0))

    def _draw_entity(self, entity: Entity, *, subdued: bool = False) -> None:
        x, y = round(entity.position.x), round(entity.position.y)
        shadow = pygame.Surface((42, 22), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (4, 10, 12, 75), (5, 9, 32, 9))
        self.screen.blit(shadow, (x - 21, y - 5))
        if entity.kind == EntityKind.LAKE:
            pygame.draw.ellipse(self.screen, (36, 126, 182), (x - 24, y - 14, 48, 28))
            pygame.draw.arc(self.screen, (104, 210, 224), (x - 18, y - 8, 34, 14), 0, pi, 2)
        elif entity.kind == EntityKind.TREE:
            pygame.draw.rect(self.screen, (99, 67, 45), (x - 2, y, 5, 11), border_radius=2)
            pygame.draw.circle(self.screen, (27, 105, 67), (x, y - 7), 10)
            pygame.draw.circle(self.screen, (43, 133, 76), (x - 6, y - 2), 7)
            pygame.draw.circle(self.screen, (57, 151, 83), (x + 6, y - 2), 7)
        elif entity.kind == EntityKind.ROCK:
            pygame.draw.polygon(
                self.screen,
                (123, 134, 136),
                ((x - 8, y + 5), (x - 5, y - 5), (x + 3, y - 8), (x + 9, y + 3)),
            )
            pygame.draw.line(self.screen, (165, 173, 172), (x - 4, y - 4), (x + 3, y - 6), 2)
        elif entity.kind == EntityKind.BUILDING:
            wall = (111, 83, 67) if subdued else (189, 132, 80)
            pygame.draw.rect(self.screen, wall, (x - 13, y - 10, 27, 24), border_radius=2)
            pygame.draw.polygon(
                self.screen, (91, 48, 46), ((x - 17, y - 9), (x, y - 25), (x + 18, y - 9))
            )
            pygame.draw.rect(self.screen, (58, 46, 43), (x - 3, y + 2, 7, 12), border_radius=2)
            window = self._hue_color(entity.appearance_hue, saturation=55, value=95)
            pygame.draw.rect(self.screen, window, (x - 10, y - 5, 5, 6), border_radius=1)
            pygame.draw.rect(self.screen, window, (x + 6, y - 5, 5, 6), border_radius=1)
        elif entity.kind == EntityKind.HUMAN:
            self._draw_human(entity, x, y)
        else:
            pygame.draw.ellipse(self.screen, (235, 238, 229), (x - 9, y - 6, 18, 13))
            pygame.draw.circle(self.screen, (68, 58, 55), (x + 7, y - 4), 5)
            pygame.draw.circle(self.screen, (42, 39, 37), (x + 9, y - 5), 1)

        if entity.id == self.selected_id:
            pygame.draw.circle(self.screen, GOLD, (x, y), 17, 2)
            pygame.draw.circle(self.screen, (255, 225, 142), (x, y), 21, 1)

    def _draw_human(self, entity: Entity, x: int, y: int) -> None:
        outfit = self._hue_color(entity.appearance_hue, saturation=58, value=90)
        skin = (226, 181, 143)
        pygame.draw.circle(self.screen, (8, 17, 22), (x, y + 1), 10)
        pygame.draw.rect(self.screen, outfit, (x - 7, y - 1, 14, 13), border_radius=5)
        pygame.draw.circle(self.screen, skin, (x, y - 7), 5)
        pygame.draw.circle(self.screen, (38, 31, 30), (x - 2, y - 8), 1)
        pygame.draw.circle(self.screen, (38, 31, 30), (x + 2, y - 8), 1)
        if entity.appearance_style == "scholarly" or entity.accessory == "glasses":
            pygame.draw.circle(self.screen, (48, 55, 62), (x - 2, y - 7), 2, 1)
            pygame.draw.circle(self.screen, (48, 55, 62), (x + 3, y - 7), 2, 1)
        if entity.accessory == "hat":
            pygame.draw.rect(self.screen, (66, 48, 38), (x - 7, y - 14, 14, 2))
            pygame.draw.rect(self.screen, (66, 48, 38), (x - 4, y - 19, 9, 6))
        elif entity.accessory in {"ribbon", "flower"}:
            pygame.draw.circle(self.screen, (244, 116, 166), (x + 6, y - 11), 3)
        elif entity.accessory == "scarf":
            pygame.draw.line(self.screen, CORAL, (x - 6, y), (x + 7, y + 3), 3)
        if entity.faction_id:
            pygame.draw.arc(
                self.screen,
                self._faction_color(entity.faction_id),
                (x - 13, y - 13, 26, 26),
                0,
                pi * 1.7,
                2,
            )
        state_color = CYAN if entity.thinking else VIOLET
        if entity.thinking:
            self._pill("thinking", x + 11, y - 26, state_color)
        elif entity.state == AgentState.DREAMING:
            self._pill("dream", x + 11, y - 26, state_color)
        elif entity.state == AgentState.SLEEPING:
            self._pill("sleep", x + 11, y - 26, (133, 155, 214))
        self._label(entity.name or entity.id, x, y + 16, selected=entity.id == self.selected_id)

    def _draw_top_hud(self) -> None:
        width = self.simulation.state.width
        overlay = pygame.Surface((width, 64), pygame.SRCALPHA)
        overlay.fill((7, 15, 20, 202))
        self.screen.blit(overlay, (0, 0))
        world_time = self.simulation.world_time()
        mode = "INSIGHT" if self.insight_mode else "WORLD"
        self._text(mode, 22, 13, size=13, color=CYAN, bold=True)
        subtitle = "reti sociali · idee · causalità" if self.insight_mode else "società emergente"
        self._text(subtitle, 22, 31, size=18, color=INK, bold=True)
        clock = f"GIORNO {world_time['day']}  ·  {world_time['hour']:02}:{world_time['minute']:02}"
        self._text(clock, width - 220, 15, size=16, color=GOLD, bold=True)
        status = "PAUSA" if self.paused else f"LIVE  ×{self.speed}"
        self._text(
            status, width - 220, 37, size=12, color=CORAL if self.paused else CYAN, bold=True
        )

    def _draw_panel(self) -> None:
        left = self.simulation.state.width
        width = self.screen.get_width() - left
        height = self.screen.get_height()
        pygame.draw.rect(self.screen, PANEL, (left, 0, width, height))
        pygame.draw.line(self.screen, (42, 61, 70), (left, 0), (left, height), 1)

        self._text("LIFE / OBSERVATORY", left + 18, 14, size=19, color=INK, bold=True)
        self._draw_mode_tabs(left, width)
        y = 82
        y = self._draw_world_summary(left, width, y)
        selected = self.simulation.state.entities.get(self.selected_id or "")
        if selected and selected.kind == EntityKind.HUMAN:
            y = self._draw_identity_card(left, width, y, selected)
            if self.insight_mode:
                y = self._draw_inner_life_card(left, width, y, selected)
                y = self._draw_connections_card(left, width, y, selected)
            else:
                y = self._draw_needs_card(left, width, y, selected)
        else:
            y = self._draw_empty_selection(left, width, y)
        self._draw_event_stream(left, width, y, height)

    def _draw_mode_tabs(self, left: int, width: int) -> None:
        tab_y = 43
        tab_width = (width - 28) // 2
        for index, (label, active) in enumerate(
            (("MONDO", not self.insight_mode), ("INSIGHT", self.insight_mode))
        ):
            rect = pygame.Rect(left + 10 + index * tab_width, tab_y, tab_width - 4, 29)
            pygame.draw.rect(self.screen, (29, 42, 52) if active else PANEL, rect, border_radius=7)
            if active:
                pygame.draw.line(
                    self.screen,
                    CYAN,
                    (rect.left + 10, rect.bottom),
                    (rect.right - 10, rect.bottom),
                    2,
                )
            self._centered_text(label, rect, size=12, color=INK if active else MUTED, bold=True)

    def _draw_world_summary(self, left: int, width: int, y: int) -> int:
        stats = self.simulation.statistics()
        rect = self._card(left, width, y, 70)
        self._text("MONDO", rect.x + 12, rect.y + 9, size=11, color=MUTED, bold=True)
        self._metric(str(stats["humans"]), "PERSONE", rect.x + 12, rect.y + 30)
        self._metric(str(stats["factions"]), "FAZIONI", rect.x + 83, rect.y + 30)
        self._metric(str(stats["professions"]), "LAVORI", rect.x + 154, rect.y + 30)
        self._metric(
            str(stats["wars"]), "GUERRE", rect.x + 225, rect.y + 30, alert=bool(stats["wars"])
        )
        return rect.bottom + 8

    def _draw_identity_card(self, left: int, width: int, y: int, entity: Entity) -> int:
        rect = self._card(left, width, y, 104)
        accent = self._hue_color(entity.appearance_hue, saturation=55, value=95)
        pygame.draw.circle(self.screen, accent, (rect.x + 25, rect.y + 29), 12)
        self._text(
            entity.name or entity.id, rect.x + 46, rect.y + 12, size=19, color=INK, bold=True
        )
        self._text(
            f"{entity.profession}  ·  {entity.temperament.archetype}",
            rect.x + 46,
            rect.y + 35,
            size=12,
            color=CYAN,
        )
        action = "sta pensando" if entity.thinking else str(entity.action.kind)
        self._pill(action, rect.x + 12, rect.y + 58, CYAN if entity.thinking else (99, 142, 151))
        mood_x = rect.x + 118
        self._pill(entity.mood, mood_x, rect.y + 58, VIOLET)
        self._text(
            f"{entity.age_years:.1f} anni  ·  soddisfazione {entity.profession_satisfaction:.0f}%",
            rect.x + 12,
            rect.y + 84,
            size=11,
            color=MUTED,
        )
        return rect.bottom + 8

    def _draw_needs_card(self, left: int, width: int, y: int, entity: Entity) -> int:
        rect = self._card(left, width, y, 150)
        self._text("STATO VITALE", rect.x + 12, rect.y + 10, size=11, color=MUTED, bold=True)
        rows = (
            ("SALUTE", entity.health, (90, 209, 142)),
            ("ENERGIA", entity.energy, GOLD),
            ("FAME", entity.hunger, CORAL),
            ("SETE", entity.thirst, (84, 169, 230)),
            ("SOCIALE", entity.social, VIOLET),
        )
        for index, (label, value, color) in enumerate(rows):
            self._bar(label, value, rect.x + 12, rect.y + 32 + index * 22, rect.width - 24, color)
        return rect.bottom + 8

    def _draw_inner_life_card(self, left: int, width: int, y: int, entity: Entity) -> int:
        rect = self._card(left, width, y, 168)
        self._text("VITA INTERIORE", rect.x + 12, rect.y + 10, size=11, color=VIOLET, bold=True)
        self._text("OBIETTIVO", rect.x + 12, rect.y + 31, size=10, color=MUTED, bold=True)
        text_y = rect.y + 46
        for line in self._wrap(entity.goal, rect.width - 24, 13)[:2]:
            self._text(line, rect.x + 12, text_y, size=13, color=INK)
            text_y += 17
        signal_y = rect.y + 87
        memories = entity.short_term_memory + entity.long_term_memory
        strongest = max(memories, key=lambda item: (item.importance, item.tick), default=None)
        signal = entity.last_dream or (strongest.summary if strongest else "Nessun segnale ancora")
        signal_type = "SOGNO" if entity.last_dream else "MEMORIA DOMINANTE"
        self._text(signal_type, rect.x + 12, signal_y, size=10, color=VIOLET, bold=True)
        for line in self._wrap(signal, rect.width - 24, 12)[:3]:
            signal_y += 15
            self._text(line, rect.x + 12, signal_y, size=12, color=(190, 197, 211))
        return rect.bottom + 8

    def _draw_connections_card(self, left: int, width: int, y: int, entity: Entity) -> int:
        available = self.screen.get_height() - y - 102
        height = max(82, min(134, available))
        rect = self._card(left, width, y, height)
        self._text("CONNESSIONI", rect.x + 12, rect.y + 10, size=11, color=CYAN, bold=True)
        bonds = sorted(
            entity.social_bonds.values(),
            key=lambda bond: abs(bond.affinity) + abs(bond.trust) + bond.attraction + bond.fear,
            reverse=True,
        )
        row_y = rect.y + 32
        for bond in bonds[: max(1, (height - 36) // 20)]:
            target = self.simulation.state.entities.get(bond.target_id)
            if not target:
                continue
            color = self._relationship_color(bond.label)
            pygame.draw.circle(self.screen, color, (rect.x + 16, row_y + 6), 4)
            self._text(target.name or target.id, rect.x + 27, row_y, size=12, color=INK, bold=True)
            self._text(bond.label, rect.right - 82, row_y, size=11, color=color)
            row_y += 20
        if not bonds:
            self._text("Nessun legame significativo", rect.x + 12, row_y, size=12, color=MUTED)
        return rect.bottom + 8

    def _draw_empty_selection(self, left: int, width: int, y: int) -> int:
        rect = self._card(left, width, y, 86)
        self._text(
            "SELEZIONA UNA PERSONA", rect.x + 12, rect.y + 14, size=12, color=CYAN, bold=True
        )
        self._text("Clicca sulla mappa per aprire", rect.x + 12, rect.y + 38, size=13, color=INK)
        self._text("la sua vita interiore.", rect.x + 12, rect.y + 56, size=13, color=MUTED)
        return rect.bottom + 8

    def _draw_event_stream(self, left: int, width: int, y: int, height: int) -> None:
        if y > height - 52:
            return
        self._text("SEGNALI RECENTI", left + 18, y, size=11, color=CORAL, bold=True)
        y += 21
        excluded = {"ai_thinking", "eat", "drink", "gather", "study", "temperament_changed"}
        events = [
            event for event in reversed(self.simulation.events) if event.event_type not in excluded
        ]
        for event in events[: max(1, (height - y - 28) // 29)]:
            color = self._event_color(event.event_type)
            pygame.draw.circle(self.screen, color, (left + 21, y + 6), 4)
            actor = self.simulation.state.entities.get(event.actor_id or "")
            name = actor.name if actor and actor.name else event.actor_id or "mondo"
            self._text(
                self._event_title(event.event_type), left + 33, y - 2, size=12, color=INK, bold=True
            )
            self._text(str(name), left + 33, y + 12, size=10, color=MUTED)
            y += 29
        self._text(
            "I / TAB Insight   SPAZIO pausa   +/− velocità",
            left + 18,
            height - 22,
            size=10,
            color=MUTED,
        )

    def _draw_insight_overlay(self) -> None:
        graph = self.simulation.social_graph()
        nodes = {str(node["id"]): node for node in graph["nodes"]}
        selected = self.simulation.state.entities.get(self.selected_id or "")
        selected_id = selected.id if selected and selected.kind == EntityKind.HUMAN else None
        pairs: dict[frozenset[str], dict[str, object]] = {}
        priority = {
            "love": 9,
            "family": 8,
            "hate": 8,
            "fear": 7,
            "rival": 6,
            "mentor": 5,
            "friend": 4,
            "faction_ally": 3,
            "acquaintance": 1,
        }
        for edge in graph["edges"]:
            relationship = str(edge["relationship"])
            involved = selected_id in {edge["source"], edge["target"]}
            if relationship == "acquaintance" and not involved:
                continue
            pair = frozenset((str(edge["source"]), str(edge["target"])))
            current = pairs.get(pair)
            if current is None or priority.get(relationship, 0) > priority.get(
                str(current["relationship"]), 0
            ):
                pairs[pair] = edge
        layer = pygame.Surface(
            (self.simulation.state.width, self.simulation.state.height), pygame.SRCALPHA
        )
        for edge in pairs.values():
            source = nodes.get(str(edge["source"]))
            target = nodes.get(str(edge["target"]))
            if not source or not target:
                continue
            relationship = str(edge["relationship"])
            color = self._relationship_color(relationship)
            involved = selected_id in {edge["source"], edge["target"]}
            alpha = 215 if involved else 48
            start = (round(float(source["x"])), round(float(source["y"])))
            end = (round(float(target["x"])), round(float(target["y"])))
            pygame.draw.line(layer, (*color, alpha), start, end, 3 if involved else 1)
            if involved:
                midpoint = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
                self._insight_tag(layer, relationship, midpoint, color)
        self._draw_causal_links(layer)
        self.screen.blit(layer, (0, 0))
        self._draw_active_ideas()
        if selected and selected.kind == EntityKind.HUMAN:
            self._draw_cognitive_constellation(selected)

    def _draw_active_ideas(self) -> None:
        for human in self.simulation.state.living(EntityKind.HUMAN):
            rule = self.simulation.state.active_rules.get(str(human.profession))
            if not rule:
                continue
            position = (round(human.position.x), round(human.position.y))
            pygame.draw.circle(self.screen, (110, 220, 151), position, 22, 2)
            if human.id != self.selected_id:
                self._pill("idea in action", position[0] + 14, position[1] - 34, (110, 220, 151))

    def _draw_causal_links(self, layer: pygame.Surface) -> None:
        for event in reversed(self.simulation.events[-120:]):
            if event.event_type != "work" or not event.actor_id:
                continue
            actor = self.simulation.state.entities.get(event.actor_id)
            if not actor:
                continue
            for impact in event.payload.get("impacts", []):
                if not isinstance(impact, dict):
                    continue
                for target_id in impact.get("applied_to", []):
                    target = self.simulation.state.entities.get(str(target_id))
                    if not target:
                        continue
                    start = (round(actor.position.x), round(actor.position.y))
                    end = (round(target.position.x), round(target.position.y))
                    self._dashed_line(layer, (*GOLD, 190), start, end, 2)

    def _draw_cognitive_constellation(self, entity: Entity) -> None:
        memories = entity.short_term_memory + entity.long_term_memory
        strongest = max(memories, key=lambda item: (item.importance, item.tick), default=None)
        top_value = max(entity.values, key=entity.values.get, default="")
        signals: list[tuple[str, str, tuple[int, int, int]]] = [("GOAL", entity.goal, GOLD)]
        if entity.last_dream:
            signals.append(("DREAM", entity.last_dream, VIOLET))
        if strongest:
            signals.append(("MEMORY", strongest.summary, CYAN))
        if top_value:
            signals.append(("VALUE", top_value, CORAL))
        rule = self.simulation.state.active_rules.get(str(entity.profession))
        if rule:
            signals.append(
                ("IDEA → WORK", str(rule.get("name", entity.profession)), (110, 220, 151))
            )
        else:
            idea_events = {
                "innovation_proposed",
                "rule_activated",
                "reflection",
                "inspire",
                "story_told",
            }
            idea = next(
                (
                    event
                    for event in reversed(self.simulation.events)
                    if event.actor_id == entity.id and event.event_type in idea_events
                ),
                None,
            )
            if idea:
                idea_text = idea.payload.get("goal") or idea.payload.get("explanation")
                idea_text = idea_text or self._event_title(idea.event_type)
                signals.append(("IDEA", str(idea_text), (110, 220, 151)))
        if not signals:
            return
        center = (round(entity.position.x), round(entity.position.y))
        radius = 125
        count = len(signals[:5])
        if center[1] < 100:
            span = count * 146
            start = min(
                self.simulation.state.width - span - 8,
                max(8, center[0] - span // 2),
            )
            card_centers = [(start + index * 146 + 69, 98) for index in range(count)]
        elif center[1] > self.simulation.state.height - 100:
            span = count * 146
            start = min(
                self.simulation.state.width - span - 8,
                max(8, center[0] - span // 2),
            )
            card_centers = [
                (start + index * 146 + 69, self.simulation.state.height - 34)
                for index in range(count)
            ]
        elif center[0] < 100:
            span = count * 56
            start = min(
                self.simulation.state.height - span - 8,
                max(72, center[1] - span // 2),
            )
            card_centers = [(77, start + index * 56 + 24) for index in range(count)]
        elif center[0] > self.simulation.state.width - 100:
            span = count * 56
            start = min(
                self.simulation.state.height - span - 8,
                max(72, center[1] - span // 2),
            )
            card_centers = [
                (self.simulation.state.width - 77, start + index * 56 + 24)
                for index in range(count)
            ]
        else:
            angles = [-pi / 2 + index * 2 * pi / count for index in range(count)]
            card_centers = [
                (center[0] + cos(angle) * radius, center[1] + sin(angle) * radius)
                for angle in angles
            ]
        for index, (kind, text, color) in enumerate(signals[:5]):
            raw_x, raw_y = card_centers[index]
            x = round(min(self.simulation.state.width - 146, max(8, raw_x - 65)))
            y = round(min(self.simulation.state.height - 58, max(72, raw_y - 22)))
            rect = pygame.Rect(x, y, 138, 48)
            anchor = rect.center
            pygame.draw.line(self.screen, (*color,), center, anchor, 1)
            card = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(card, (10, 18, 25, 225), card.get_rect(), border_radius=8)
            pygame.draw.rect(card, (*color, 190), card.get_rect(), 1, border_radius=8)
            self.screen.blit(card, rect)
            self._text(kind, rect.x + 8, rect.y + 6, size=9, color=color, bold=True)
            lines = self._wrap(text, rect.width - 16, 10)
            self._text(lines[0] if lines else "—", rect.x + 8, rect.y + 22, size=10, color=INK)
            if len(lines) > 1:
                self._text(lines[1], rect.x + 8, rect.y + 34, size=10, color=MUTED)

    def _card(self, left: int, width: int, y: int, height: int) -> pygame.Rect:
        rect = pygame.Rect(left + 10, y, width - 20, height)
        pygame.draw.rect(self.screen, PANEL_CARD, rect, border_radius=9)
        pygame.draw.rect(self.screen, (38, 52, 63), rect, 1, border_radius=9)
        return rect

    def _bar(
        self,
        label: str,
        value: float,
        x: int,
        y: int,
        width: int,
        color: tuple[int, int, int],
    ) -> None:
        self._text(label, x, y, size=10, color=MUTED, bold=True)
        self._text(f"{value:.0f}", x + width - 23, y, size=10, color=INK, bold=True)
        bar = pygame.Rect(x + 61, y + 3, width - 90, 6)
        pygame.draw.rect(self.screen, (46, 57, 66), bar, border_radius=3)
        fill = bar.copy()
        fill.width = round(bar.width * max(0, min(100, value)) / 100)
        pygame.draw.rect(self.screen, color, fill, border_radius=3)

    def _metric(self, value: str, label: str, x: int, y: int, *, alert: bool = False) -> None:
        self._text(value, x, y, size=18, color=CORAL if alert else INK, bold=True)
        self._text(label, x, y + 20, size=8, color=MUTED, bold=True)

    def _pill(self, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
        font = self._font(10, True)
        label = str(text).replace("ActionType.", "").replace("AgentState.", "")
        label = label.upper()[:16]
        width = font.size(label)[0] + 14
        surface = pygame.Surface((width, 18), pygame.SRCALPHA)
        pygame.draw.rect(surface, (*color, 38), surface.get_rect(), border_radius=9)
        pygame.draw.rect(surface, (*color, 150), surface.get_rect(), 1, border_radius=9)
        surface.blit(font.render(label, True, color), (7, 4))
        self.screen.blit(surface, (x, y))

    def _label(self, text: str, x: int, y: int, *, selected: bool) -> None:
        font = self._font(11, selected)
        rendered = font.render(text, True, INK if selected else (207, 218, 215))
        rect = rendered.get_rect(midtop=(x, y))
        backing = rect.inflate(8, 4)
        surface = pygame.Surface(backing.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, (7, 14, 18, 185), surface.get_rect(), border_radius=6)
        self.screen.blit(surface, backing)
        self.screen.blit(rendered, rect)

    def _insight_tag(
        self,
        surface: pygame.Surface,
        text: str,
        position: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        font = self._font(10, True)
        rendered = font.render(text.upper(), True, color)
        rect = rendered.get_rect(center=position).inflate(8, 4)
        pygame.draw.rect(surface, (8, 15, 22, 215), rect, border_radius=5)
        surface.blit(rendered, rendered.get_rect(center=rect.center))

    @staticmethod
    def _dashed_line(
        surface: pygame.Surface,
        color: tuple[int, int, int, int],
        start: tuple[int, int],
        end: tuple[int, int],
        width: int,
    ) -> None:
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = max(1.0, (dx * dx + dy * dy) ** 0.5)
        for offset in range(0, round(distance), 12):
            end_offset = min(offset + 7, distance)
            a = (round(start[0] + dx * offset / distance), round(start[1] + dy * offset / distance))
            b = (
                round(start[0] + dx * end_offset / distance),
                round(start[1] + dy * end_offset / distance),
            )
            pygame.draw.line(surface, color, a, b, width)

    def _select_at(self, x: int, y: int) -> str | None:
        candidates = [
            entity
            for entity in self.simulation.state.entities.values()
            if entity.alive
            and entity.kind == EntityKind.HUMAN
            and abs(entity.position.x - x) <= 18
            and abs(entity.position.y - y) <= 18
        ]
        if not candidates:
            return None
        return min(
            candidates, key=lambda item: item.position.distance_to(type(item.position)(x, y))
        ).id

    def _wrap(self, text: object, width: int, size: int) -> list[str]:
        font = self._font(size)
        words = str(text).split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _relationship_color(relationship: str) -> tuple[int, int, int]:
        return {
            "love": (244, 104, 163),
            "family": (93, 174, 244),
            "friend": (83, 211, 145),
            "hate": (242, 88, 82),
            "fear": (171, 105, 225),
            "rival": (244, 155, 81),
            "faction_rival": (236, 111, 76),
            "mentor": (190, 145, 247),
            "student": (157, 135, 220),
            "partner": (241, 126, 183),
            "faction_ally": (75, 190, 184),
            "acquaintance": (105, 124, 137),
        }.get(relationship, (114, 132, 143))

    @staticmethod
    def _event_color(event_type: str) -> tuple[int, int, int]:
        if event_type in {"dream", "reflection", "memory_consolidated"}:
            return VIOLET
        if event_type in {"talk", "story_told", "teach", "inspire", "affection"}:
            return CYAN
        if event_type in {"innovation_proposed", "rule_activated", "work", "vocation_changed"}:
            return GOLD
        if event_type in {"attack", "death", "war_declared", "sabotage"}:
            return CORAL
        return (111, 145, 154)

    @staticmethod
    def _event_title(event_type: str) -> str:
        return {
            "ai_decision": "Decisione autonoma",
            "dream": "Sogno",
            "memory_consolidated": "Memoria consolidata",
            "innovation_proposed": "Nuova idea",
            "rule_activated": "Idea diventata regola",
            "vocation_changed": "Nuova vocazione",
            "work": "Impatto professionale",
            "talk": "Conversazione",
            "story_told": "Storia condivisa",
            "inspire": "Ispirazione",
            "death": "Morte",
        }.get(event_type, event_type.replace("_", " ").title())

    @staticmethod
    def _hue_color(hue: int, *, saturation: int, value: int) -> tuple[int, int, int]:
        color = pygame.Color(0)
        color.hsva = (hue % 360, saturation, value, 100)
        return color.r, color.g, color.b

    @staticmethod
    def _faction_color(faction_id: str) -> tuple[int, int, int]:
        value = sum((index + 1) * ord(character) for index, character in enumerate(faction_id))
        return (80 + value % 176, 80 + (value // 3) % 176, 80 + (value // 7) % 176)

    def _font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont("segoeui", size, bold=bold)
        return self._fonts[key]

    def _text(
        self,
        text: object,
        x: int,
        y: int,
        *,
        size: int = 14,
        color: tuple[int, int, int] = INK,
        bold: bool = False,
    ) -> None:
        self.screen.blit(self._font(size, bold).render(str(text), True, color), (x, y))

    def _centered_text(
        self,
        text: str,
        rect: pygame.Rect,
        *,
        size: int,
        color: tuple[int, int, int],
        bold: bool = False,
    ) -> None:
        rendered = self._font(size, bold).render(text, True, color)
        self.screen.blit(rendered, rendered.get_rect(center=rect.center))
