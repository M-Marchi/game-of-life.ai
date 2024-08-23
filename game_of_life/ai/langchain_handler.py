from dataclasses import dataclass, field
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM
from loguru import logger as lg

from game_of_life.data_classes.action import Action, ActionType


@dataclass
class LangchainHandler:
    model_name: str
    model: OllamaLLM = field(init=False)

    def __post_init__(self):
        self.model = OllamaLLM(model=self.model_name)

    def call_model(self, prompt: str, human=None) -> str:
        chain = self.model
        lg.debug(f"{human.name} started the chain")
        response = chain.invoke(prompt)
        lg.debug(f"{human.name} response: {response}")
        return response
