def generate_start_thinking_prompt(**kwargs):
    return f"""You are {kwargs['name']}, a {kwargs['gender']} with the following characteristics:
- IQ: {kwargs['IQ']}
- Attack Power: {kwargs['attack']} (low 0- high 100)
Nearby entities:
"""


END_THINKING_PROMPT = """
        Consider your goals and the situation around you. Decide on one of the following actions:
        MOVE, ATTACK, FIND_FOOD, SLEEP, FIND_PARTNER, DIE, IDLE, GO_TO_TARGET, TALK, BUILD.
        Your response should be in the format:
    /ACTION_NAME TARGET(optional) -END 
Explain why you chose this action in the next line.
        """


def generate_memory_prompt(LTM: dict, STM: list):
    return f"""Given a list of strings called "STM" that represents short-term memories: {STM};
     insert the most relevant of these strings into the dictionary "LTM" which represents long-term memory: {LTM}.
    """
