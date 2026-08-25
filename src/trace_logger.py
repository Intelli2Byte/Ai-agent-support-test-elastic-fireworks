import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TRACES_DIR = BASE_DIR / "traces"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
FIREWORKS_KEY_RE = re.compile(r"fw_[A-Za-z0-9]{8,}")
ES_KEY_RE = re.compile(r"[A-Za-z0-9+/=]{40,}")


def _redact_string(value: str) -> str:
    value = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    value = FIREWORKS_KEY_RE.sub("[REDACTED_KEY]", value)
    return value


def redact(node):
    if isinstance(node, str):
        return _redact_string(node)
    if isinstance(node, dict):
        return {key: redact(value) for key, value in node.items()}
    if isinstance(node, list):
        return [redact(item) for item in node]
    return node


class TraceLogger:
    def __init__(self, session_id: str):
        TRACES_DIR.mkdir(exist_ok=True)
        self.path = TRACES_DIR / f"session-{session_id}.jsonl"

    def log_turn(self, trace: dict) -> None:
        entry = {
            "timestamp_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            **redact(trace),
        }
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, indent=None) + "\n")
