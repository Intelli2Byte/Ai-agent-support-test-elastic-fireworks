import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import FIREWORKS_API_KEY, FIREWORKS_BASE_URL, FIREWORKS_MODEL

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / ".llm_cache.sqlite"

_client = None


def _cache_lookup(key: str):
    conn = sqlite3.connect(CACHE_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, value TEXT)"
        )
        row = conn.execute(
            "SELECT value FROM responses WHERE key=?", (key,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _cache_store(key: str, value: str) -> None:
    conn = sqlite3.connect(CACHE_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO responses (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not FIREWORKS_API_KEY:
            raise RuntimeError(
                "Missing FIREWORKS_API_KEY. Copy .env.example to .env and fill it in."
            )
        _client = OpenAI(api_key=FIREWORKS_API_KEY, base_url=FIREWORKS_BASE_URL)
    return _client


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": (
                "Look up an order's current shipping status by its exact order ID "
                "(format ORD-1234). Call ONLY when the customer has actually given "
                "an order ID in the conversation; otherwise ask them for it. "
                "Returns limited customer-safe fields only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID as provided by the customer, e.g. ORD-1007",
                    }
                },
                "required": ["order_id"],
            },
        },
    }
]


class _CachedFunction:
    def __init__(self, data):
        self.name = data["name"]
        self.arguments = data["arguments"]


class _CachedToolCall:
    def __init__(self, data):
        self.id = data["id"]
        self.function = _CachedFunction(data["function"])

    def model_dump(self):
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


class _CachedMessage:
    def __init__(self, data):
        self.content = data.get("content")
        self.tool_calls = [_CachedToolCall(tc) for tc in data.get("tool_calls") or []]


class _CachedResponse:
    def __init__(self, message_data):
        self.choices = [type("Choice", (), {"message": _CachedMessage(message_data)})()]


def _cache_key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def chat(messages: list[dict], use_tools: bool = True):
    payload = {
        "model": FIREWORKS_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    if use_tools:
        payload["tools"] = TOOLS
        payload["tool_choice"] = "auto"

    key = _cache_key(payload)
    cached = _cache_lookup(key)
    if cached is not None:
        return _CachedResponse(json.loads(cached))

    response = get_client().chat.completions.create(**payload)
    message = response.choices[0].message
    serialized = {
        "content": message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in (message.tool_calls or [])
        ],
    }
    _cache_store(key, json.dumps(serialized))
    return _CachedResponse(serialized)
