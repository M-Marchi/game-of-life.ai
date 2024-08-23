def generate_start_thinking_prompt(**kwargs):
    return f"""You are {kwargs['name']}, a {kwargs['gender']} human with the following characteristics:
- IQ: {kwargs['IQ']}
- Attack Power: {kwargs['attack']} (low 0- high 100)
Nearby entities:
"""


END_THINKING_PROMPT = """
        Consider your goals and the situation around you. Decide on one of the following actions:
        - MOVE target_id (move to target)
        - ATTACK target_id (attack target)
        - FIND_FOOD (find food around you)
        - SLEEP (rest to recover energy and clear memory)
        - FIND_PARTNER (find a partner to mate)
        - IDLE (do nothing)
        - TALK target_id (talk to target)
        - BUILD (start building something near you)
        Your response should be in the format:
    /ACTION_NAME TARGET(optional) -END 
Explain why you chose this action in the next line.
        """


def generate_memory_prompt(LTM: dict, STM: list):
    return f"""Given a list of strings called "STM" that represents short-term memories: {STM};
     insert the most relevant of these strings into the dictionary "LTM" which represents long-term memory: {LTM}.
    """


def generate_build_prompt():
    return f"""You have decided to build something. 
    Describe the object you want to build using pygame command.
    You response should be in the format (example):
    {
    'CODE': 'pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(self.x, self.y, 2, 2))',
    'EXPLANATION': 'I am building a white rectangle at my current position'
    }
    """
