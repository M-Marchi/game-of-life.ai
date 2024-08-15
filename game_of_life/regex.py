import re

import re


def get_dictionary_from_response(response: str) -> dict:
    """
    Extracts a dictionary from the response string
    """
    pattern = r"\{[^{}]*\}"
    match = re.search(pattern, response)
    if match:
        return eval(match.group())
    else:
        return {}
