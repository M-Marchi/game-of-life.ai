NEW_BACKGROUND_PROMPT = (
    "Generate a short background for a character named {name}. "
    "The character has an IQ of {IQ}, is {gender}, belongs to the {faction_name} faction, "
    "has an attack level of {attack} (0-100), and is {age} years old. "
    "The story should include one life event, one skill, and one mission.\n"
    "The response will be:\n"
    "{{\n"
    "life_event: life event description in max 50 words,\n"
    "skill: skill description in max 20 words,\n"
    "mission: mission description in max 20 words\n"
    "}}"
)
