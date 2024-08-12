from dataclasses import dataclass, field
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM
from loguru import logger as lg


@dataclass
class LangchainHandler:
    model_name: str
    model: OllamaLLM = field(init=False)

    def __post_init__(self):
        self.model = OllamaLLM(model=self.model_name)

    def call_model(self, prompt: str) -> str:
        chain = self.model
        lg.debug("Started the chain")
        response = chain.invoke(prompt)
        lg.debug(f"Response: {response}")
        return response
