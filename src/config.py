import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL")
ELASTICSEARCH_API_KEY = os.environ.get("ELASTICSEARCH_API_KEY")
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY")
FIREWORKS_MODEL = os.environ.get("FIREWORKS_MODEL")
FIREWORKS_BASE_URL = os.environ.get(
    "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"
)
SUPPORT_CONTACT_MESSAGE = os.environ.get(
    "SUPPORT_CONTACT_MESSAGE", "please contact Aster & Row human support"
)

KB_DIR = BASE_DIR / "knowledge-base"
ORDERS_PATH = BASE_DIR / "data" / "orders.json"

REQUIRED_VARS = ["ELASTICSEARCH_URL", "ELASTICSEARCH_API_KEY"]

for var in REQUIRED_VARS:
    if not os.environ.get(var):
        raise RuntimeError(
            f"Missing required environment variable {var}. "
            f"Copy .env.example to .env and fill in your credentials."
        )
