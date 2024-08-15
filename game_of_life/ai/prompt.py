NEW_BACKGROUND_PROMPT = (
    "Generate a short background for a character named {name}. "
    "The character has an IQ of {IQ}, is {gender}, "
    "has an attack level of {attack} (0-100), and is {age} years old. "
    "Keep in mind that the world is a sandbox environment, so the information should be straightforward and not overly complex. "
    "The story should include one simple life event, one basic skill, and one clear mission.\n"
    "The response is a python dictionary that must follow this style:\n"
    "{{\n"
    "name: character name,\n"
    "IQ: IQ value,\n"
    "gender: gender value,\n"
    "attack: attack value,\n"
    "life_event: life event description in max 50 words,\n"
    "skill: skill description in max 20 words,\n"
    "mission: mission description in max 20 words\n"
    "}}\n"
    "Don't write the response in markdown format, just the dictionary.\n"
    "Response:"
)


def generate_start_thinking_prompt(**kwargs):
    return f"""You are {kwargs['name']}, a {kwargs['gender']} with the following characteristics:
- IQ: {kwargs['IQ']}
- Attack Power: {kwargs['attack']} (low 0- high 100)
- Life Event: {kwargs['life_event']}
- Skill: {kwargs['skill']}
- Mission: {kwargs['mission']}
Nearby entities:
"""


END_THINKING_PROMPT = """
        Consider your goals and the situation around you. Decide on one of the following actions:
        MOVE, ATTACK, FIND_FOOD, SLEEP, FIND_PARTNER, DIE, IDLE, GO_TO_TARGET, TALK, BUILD.
        Your response should be in the format:
    /ACTION_NAME TARGET(optional) --END 
Explain why you chose this action in the next line.
        """
