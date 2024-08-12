from dataclasses import dataclass, field
import pygame
import random

from game_of_life.ai.langchain_handler import LangchainHandler
from game_of_life.constants import (
    GENERIC_MALE_SPRITE,
    GENERIC_FEMALE_SPRITE,
    MODEL_NAME,
)
from game_of_life.data_classes.human import Human, GenericMale, GenericFemale
from game_of_life.data_classes.world_entity import Tree, Lake


@dataclass
class World:
    width: int
    height: int
    screen_width: int
    screen_height: int
    num_trees: int
    num_lakes: int
    zoom_level: float = 1.0
    offset_x: int = 0
    offset_y: int = 0
    trees: list = field(init=False)
    lakes: list = field(init=False)
    dragging: bool = field(default=False, init=False)
    drag_start_x: int = field(default=0, init=False)
    drag_start_y: int = field(default=0, init=False)
    humans: list = field(init=False)
    langchain_handler: LangchainHandler = field(init=False)

    def __post_init__(self):
        self.langchain_handler = LangchainHandler(model_name=MODEL_NAME)

        self.trees = [
            (random.randint(0, self.width - 10), random.randint(0, self.height - 10))
            for _ in range(self.num_trees)
        ]
        self.lakes = [
            (random.randint(0, self.width - 100), random.randint(0, self.height - 100))
            for _ in range(self.num_lakes)
        ]

        self.humans = []

    def draw_background(self, screen):
        light_green = (51, 204, 51)  # Light green color
        screen.fill(light_green)

    def draw_trees(self, screen):
        for x, y in self.trees:
            tree = Tree(x, y, 50)
            tree.draw(screen, self.zoom_level, self.offset_x, self.offset_y)

    def draw_lakes(self, screen):
        for x, y in self.lakes:
            lake = Lake(x, y, 100)
            lake.draw(screen, self.zoom_level, self.offset_x, self.offset_y)

    def draw_minimap(self, screen):
        minimap_width = 200
        minimap_height = 200
        minimap_surface = pygame.Surface((minimap_width, minimap_height))
        minimap_surface.fill((0, 0, 0))  # Black background for minimap

        # Draw trees on minimap
        for x, y in self.trees:
            minimap_x = int(x * minimap_width / self.width)
            minimap_y = int(y * minimap_height / self.height)
            points = [
                (minimap_x, minimap_y),
                (minimap_x + 2, minimap_y - 4),
                (minimap_x + 4, minimap_y),
            ]
            pygame.draw.polygon(minimap_surface, (0, 255, 0), points)

        # Draw lakes on minimap
        for x, y in self.lakes:
            minimap_x = int(x * minimap_width / self.width)
            minimap_y = int(y * minimap_height / self.height)
            pygame.draw.ellipse(
                minimap_surface, (0, 0, 255), (minimap_x, minimap_y, 10, 5)
            )

        # Draw current view rectangle on minimap
        view_rect = pygame.Rect(
            int(self.offset_x * minimap_width / self.width),
            int(self.offset_y * minimap_height / self.height),
            int(self.screen_width * minimap_width / self.width / self.zoom_level),
            int(self.screen_height * minimap_height / self.height / self.zoom_level),
        )
        pygame.draw.rect(minimap_surface, (255, 0, 0), view_rect, 2)

        # Blit minimap to the main screen
        screen.blit(
            minimap_surface,
            (
                self.screen_width - minimap_width - 10,
                self.screen_height - minimap_height - 10,
            ),
        )

    def spawn_humans(self, count):
        for _ in range(count):
            x = random.randint(0, self.width - 10)
            y = random.randint(0, self.height - 10)
            gender = random.choice(["male", "female"])
            if gender == "male":
                human = GenericMale(
                    x=x,
                    y=y,
                    size=50,
                    langchain_handler=self.langchain_handler,
                )
            else:
                human = GenericFemale(
                    x=x,
                    y=y,
                    size=50,
                    langchain_handler=self.langchain_handler,
                )
            human.start_thread()
            self.humans.append(human)

    def update_humans(self):
        for human in self.humans:
            dx = random.randint(1, 5)
            dy = random.randint(1, 5)
            human.update(dx, dy, self.width, self.height)

    def draw_humans(self, screen):
        for human in self.humans:
            human.draw(screen, self.zoom_level, self.offset_x, self.offset_y)

    def draw(self, screen):
        self.draw_background(screen)
        self.draw_trees(screen)
        self.draw_lakes(screen)
        self.draw_humans(screen)
        self.draw_minimap(screen)

    def zoom_in(self):
        max_zoom_level = min(
            self.width / self.screen_width, self.height / self.screen_height
        )
        if self.zoom_level * 1.1 <= max_zoom_level:
            self.zoom_level *= 1.1
        else:
            self.zoom_level = max_zoom_level

    def zoom_out(self):
        min_zoom_level = max(
            self.screen_width / self.width, self.screen_height / self.height
        )
        if self.zoom_level / 1.1 >= min_zoom_level:
            self.zoom_level /= 1.1
        else:
            self.zoom_level = min_zoom_level

    def update_offset(self, dx, dy):
        new_offset_x = self.offset_x - dx
        new_offset_y = self.offset_y - dy

        max_offset_x = self.width - self.screen_width / self.zoom_level
        max_offset_y = self.height - self.screen_height / self.zoom_level

        self.offset_x = max(0, min(new_offset_x, max_offset_x))
        self.offset_y = max(0, min(new_offset_y, max_offset_y))

    def handle_mouse_wheel(self, event):
        if event.y > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def start_drag(self, x, y):
        self.dragging = True
        self.drag_start_x = x
        self.drag_start_y = y

    def end_drag(self):
        self.dragging = False

    def drag(self, x, y):
        if self.dragging:
            dx = x - self.drag_start_x
            dy = y - self.drag_start_y
            self.update_offset(dx, dy)
            self.drag_start_x = x
            self.drag_start_y = y
