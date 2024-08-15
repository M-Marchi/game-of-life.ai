from dataclasses import dataclass
from typing import Any

from game_of_life.ai.langchain_handler import LangchainHandler
from game_of_life.ai.prompt import END_THINKING_PROMPT, generate_start_thinking_prompt
from game_of_life.constants import HUNGER_THRESHOLD, HORNY_THRESHOLD
from game_of_life.data_classes.action import Action, ActionType

from loguru import logger as lg

from game_of_life.data_classes.entity import get_entity_by_id


@dataclass
class Brain:
    # Intelligence Quotient
    IQ: int = 100
    # Long term memory
    LTM: dict = None
    # Short term memory
    STM: list = None
    # Prompt to send to the LLM
    prompt: str = None
    # AI engine
    langchain_handler: LangchainHandler = None
    # Human host
    host: Any = None

    def process(self):
        near_entities = self.host.get_nearby_entities()
        target_distance = 999999

        if self.host.action.action_type == ActionType.IDLE:
            self.prompt = self._build_prompt(near_entities)
            response = self.host.langchain_handler.call_model(self.prompt)
            self.host.action.parse_action(response)
        elif self.host.action.action_type == ActionType.FIND_FOOD:
            self.host.action = self.host.find_food(near_entities, target_distance)
        elif self.host.action.action_type == ActionType.FIND_PARTNER:
            self.host.action = self.host.find_partner(near_entities, target_distance)

    def _build_prompt(self, near_entities: dict) -> str:
        background = self.LTM["background"]
        prompt = generate_start_thinking_prompt(**background)
        # Temporary context
        for entity_id, distance in near_entities.items():
            entity = get_entity_by_id(self.host.world.entities, entity_id)
            prompt += f"- Entity type {entity.__class__}, entity ID {entity.id} (distance: {distance})\n"

        prompt += "\nBased on your current state:"
        prompt += f" You are a {self.host.age} years old"
        if self.host.hunger > HUNGER_THRESHOLD:
            prompt += " You are extremely hungry and need to find food immediately."
        elif self.host.horny > HORNY_THRESHOLD:
            prompt += " You have a strong urge to find a partner for mating."
        else:
            prompt += " You feel relatively stable and can decide what to do next."

        prompt += END_THINKING_PROMPT

        return prompt
