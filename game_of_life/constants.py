from pathlib import Path


PARENT_DIR = Path(__file__).parent
PROJECT_DIR = PARENT_DIR.parent
STATIC_DIR = PROJECT_DIR / "static"
SPRITE_DIR = STATIC_DIR / "sprites"

WORLD_SPRITE_DIR = SPRITE_DIR / "world"
HUMAN_SPRITE_DIR = SPRITE_DIR / "humans"
ANIMAL_SPRITE_DIR = SPRITE_DIR / "animals"


# Human sprites
GENERIC_MALE_SPRITE = str(HUMAN_SPRITE_DIR / "generic_male.png")
GENERIC_FEMALE_SPRITE = str(HUMAN_SPRITE_DIR / "generic_female.png")

# Animal sprites
COW_SPRITE = str(ANIMAL_SPRITE_DIR / "cow.png")

# World sprites
LAKE_SPRITE = str(WORLD_SPRITE_DIR / "lake.png")
TREE_SPRITE = str(WORLD_SPRITE_DIR / "tree.png")

# LLM
MODEL_NAME = "qwen2:0.5b"

# Names
MALE_NAMES = [
    "Arthur",
    "Lancelot",
    "Gawain",
    "Percival",
    "Galahad",
    "Tristan",
    "Bors",
    "Kay",
    "Geraint",
    "Bedivere",
    "Gareth",
    "Lamorak",
    "Dagonet",
    "Mordred",
    "Agravain",
    "Uther",
    "Owain",
    "Pelleas",
    "Ector",
    "Balin",
]

FEMALE_NAMES = [
    "Guinevere",
    "Isolde",
    "Elaine",
    "Morgana",
    "Nimue",
    "Enid",
    "Lunete",
    "Ragnelle",
    "Blanchefleur",
    "Lynet",
    "Dindrane",
    "Clarissant",
    "Brangaine",
    "Sirwen",
    "Melusine",
    "Ygraine",
    "Argante",
    "Viviane",
    "Rhiannon",
    "Arianrhod",
]
