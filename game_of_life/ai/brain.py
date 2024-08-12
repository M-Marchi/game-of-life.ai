from dataclasses import dataclass


@dataclass
class Brain:
    # Intelligence Quotient
    IQ: int = 100
    # Long term memory
    LTM: list = None
    # Short term memory
    STM: list = None
    # Prompt to send to the LLM
    prompt: str = None
