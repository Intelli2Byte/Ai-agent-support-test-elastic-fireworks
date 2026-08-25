import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ORDERS_PATH

ORDER_ID_PATTERN = re.compile(r"^ORD-(\d{4,})$")
STALE_FIELD_STATUSES = {"cancelled", "returned"}

MALFORMED = "malformed"
NOT_FOUND = "not_found"
FOUND = "found"


def normalize_order_id(raw: str) -> str | None:
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().upper()
    candidate = re.sub(r"\s+", "-", candidate)
    candidate = re.sub(r"(?<=^ORD)(?=\d)", "-", candidate)
    candidate = candidate.strip("-")
    match = ORDER_ID_PATTERN.match(candidate)
    return f"ORD-{match.group(1)}" if match else None


def lookup_order(raw_order_id: str) -> dict:
    normalized = normalize_order_id(raw_order_id)
    if normalized is None:
        return {
            "result": MALFORMED,
            "submitted": str(raw_order_id)[:50],
            "message": (
                "The value provided does not look like an order ID. "
                "Order IDs look like ORD-1234."
            ),
        }

    with open(ORDERS_PATH, encoding="utf-8") as fh:
        orders = {o["order_id"]: o for o in json.load(fh)["orders"]}

    order = orders.get(normalized)
    if order is None:
        return {
            "result": NOT_FOUND,
            "order_id": normalized,
            "message": (
                "No order was found with this ID. "
                "Please check the ID or contact support."
            ),
        }

    status = order["status"]
    sanitized = {
        "order_id": order["order_id"],
        "status": status,
    }

    carrier = order.get("carrier")
    if status not in STALE_FIELD_STATUSES and carrier:
        sanitized["carrier"] = carrier

    tracking_number = order.get("tracking_number")
    if status not in STALE_FIELD_STATUSES and tracking_number:
        sanitized["tracking_number"] = tracking_number

    estimated_delivery = order.get("estimated_delivery")
    if status not in STALE_FIELD_STATUSES and estimated_delivery:
        sanitized["estimated_delivery"] = estimated_delivery

    return {"result": FOUND, "order": sanitized}


FORBIDDEN_KEYS = {
    "email",
    "address",
    "shipping_address",
    "customer",
    "internal",
    "risk_score",
    "warehouse_note",
    "support_tags",
    "membership_tier",
}


def assert_customer_safe(result: dict) -> None:
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key.lower() not in FORBIDDEN_KEYS, f"Forbidden key leaked: {key}"
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(result)


if __name__ == "__main__":
    test_ids = [
        ("ORD-1007", "valid shipped international"),
        ("ord-1004", "cancelled, lowercase - stale ETA must be stripped"),
        ("  ord 1011  ", "shipped, messy spacing, null ETA"),
        ("ORD-9999", "unknown"),
        ("hello world", "malformed"),
        ("1007", "malformed (no prefix)"),
    ]
    for raw, note in test_ids:
        result = lookup_order(raw)
        assert_customer_safe(result)
        print(f"\n--- {raw!r}  ({note})")
        print(json.dumps(result, indent=2))
