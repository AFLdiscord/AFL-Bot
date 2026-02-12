"""Path dei file usati dal bot per config e dati."""
from pathlib import Path

# Path della cartella del bot
BASE_DIR = Path(__file__).resolve().parent.parent

# File di config
CONFIG_DIR =        BASE_DIR / "config"
CONFIG_FILE =       CONFIG_DIR / "config.json"
EXTENSIONS_FILE =   CONFIG_DIR / "extensions.json"

# File contenenti lo stato del server
DATA_DIR =              BASE_DIR / "data"
AFLERS_FILE =           DATA_DIR / "aflers.json"
BANNED_WORDS_FILE =     DATA_DIR / "banned_words.json"
PROPOSALS_FILE =        DATA_DIR / "proposals.json"
SUBREDDITS_FILE =       DATA_DIR / "subreddits.json"
