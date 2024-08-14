import re

import re


def get_dictionary_from_response(response: str) -> str:
    """
    Extracts a dictionary from the response string
    """
    pattern = r"\{[^{}]*\}"
    match = re.search(pattern, response)
    if match:
        return match.group()
    return response
