"""Loads configuration from environment variables (.env)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

TRELLO_API_KEY = os.environ.get("TRELLO_API_KEY")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN")

DUST_API_KEY = os.environ.get("DUST_API_KEY")
DUST_WORKSPACE_ID = os.environ.get("DUST_WORKSPACE_ID")
DUST_SPACE_ID = os.environ.get("DUST_SPACE_ID")
DUST_DATASOURCE_ID = os.environ.get("DUST_DATASOURCE_ID")
DUST_API_URL = os.environ.get("DUST_API_URL", "https://dust.tt/api")

# Comma-separated list of Trello board IDs to sync.
TRELLO_BOARD_IDS = [
    b.strip() for b in os.environ.get("TRELLO_BOARD_IDS", "").split(",") if b.strip()
]

# A card with no activity for this many days is considered "stale" in the board digest.
STALE_DAYS_THRESHOLD = int(os.environ.get("STALE_DAYS_THRESHOLD", "7"))

# Number of most recent comments to include per card document.
COMMENTS_PER_CARD = int(os.environ.get("COMMENTS_PER_CARD", "5"))

TRELLO_REQUIRED_VARS = {
    "TRELLO_API_KEY": TRELLO_API_KEY,
    "TRELLO_TOKEN": TRELLO_TOKEN,
}

DUST_REQUIRED_VARS = {
    "DUST_API_KEY": DUST_API_KEY,
    "DUST_WORKSPACE_ID": DUST_WORKSPACE_ID,
    "DUST_SPACE_ID": DUST_SPACE_ID,
    "DUST_DATASOURCE_ID": DUST_DATASOURCE_ID,
}


def validate(require_dust=True):
    required = dict(TRELLO_REQUIRED_VARS)
    if require_dust:
        required.update(DUST_REQUIRED_VARS)

    missing = [name for name, value in required.items() if not value]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in the values.", file=sys.stderr)
        sys.exit(1)

    if not TRELLO_BOARD_IDS:
        print("TRELLO_BOARD_IDS is empty — set at least one Trello board ID to sync.", file=sys.stderr)
        sys.exit(1)
