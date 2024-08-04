from pathlib import Path


PARENT_DIR = Path(__file__).parent
STATIC_DIR = PARENT_DIR / "static"
SPRITE_DIR = STATIC_DIR / "sprites"
HUMAN_SPRITE_DIR = SPRITE_DIR / "humans"

# Human sprites
GENERIC_MALE_SPRITE = str(HUMAN_SPRITE_DIR / "generic_male.png")
GENERIC_FEMALE_SPRITE = str(HUMAN_SPRITE_DIR / "generic_female.png")

KNIGHT_SPRITE = str(HUMAN_SPRITE_DIR / "knight.png")
WIZARD_SPRITE = str(HUMAN_SPRITE_DIR / "wizard.png")
BLACKSMITH_SPRITE = str(HUMAN_SPRITE_DIR / "blacksmith.png")
FARMER_SPRITE = str(HUMAN_SPRITE_DIR / "farmer.png")