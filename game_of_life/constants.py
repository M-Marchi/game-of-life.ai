from imaplib import Literal
from pathlib import Path


PARENT_DIR = Path(__file__).parent
PROJECT_DIR = PARENT_DIR.parent
STATIC_DIR = PROJECT_DIR / "static"

# Simulation parameters
HUNGER_THRESHOLD = 10000
HORNY_THRESHOLD = 100000

MODEL_NAME = "gemma2:2b"

# Names
MALE_NAMES = [
    "James",
    "John",
    "Robert",
    "Michael",
    "William",
    "David",
    "Richard",
    "Joseph",
    "Thomas",
    "Charles",
    "Christopher",
    "Daniel",
    "Matthew",
    "Anthony",
    "Mark",
    "Donald",
    "Steven",
    "Paul",
    "Andrew",
    "Joshua",
]

FEMALE_NAMES = [
    "Mary",
    "Patricia",
    "Jennifer",
    "Linda",
    "Elizabeth",
    "Sirwen",
    "Susan",
    "Jessica",
    "Sarah",
    "Karen",
    "Nancy",
    "Lisa",
    "Margaret",
    "Betty",
    "Sandra",
    "Ashley",
    "Dorothy",
    "Kimberly",
    "Emily",
    "Donna",
]
