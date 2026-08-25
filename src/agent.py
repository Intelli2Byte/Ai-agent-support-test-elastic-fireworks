import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import re

import llm
import prompts
from config import SUPPORT_CONTACT_MESSAGE
from es_client import get_client
from order_tool import lookup_order
from retriever import retrieve
from session import SESSIONS
from trace_logger import TraceLogger

MAX_TOOL_ROUNDS = 3


def _add_doc_context(retrieval: dict) -> None:
    if not retrieval["results"]:
        retrieval["doc_context"] = []
        return
    top_filename = retrieval["results"][0]["filename"]
    seen_headings = {chunk["heading"] for chunk in retrieval["results"]}
    try:
        response = get_client().search(
            index="kb_chunks",
            query={"term": {"filename": top_filename}},
            size=12,
            source_excludes=["embedding"],
        )
    except Exception:
        retrieval["doc_context"] = []
        return
    siblings = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        if src["heading"] in seen_headings:
            continue
        chunk = {
            "filename": src["filename"],
            "heading": src["heading"],
            "document_id": src.get("document_id", ""),
            "doc_type": src.get("doc_type", ""),
            "title": src.get("title", ""),
            "text": src["text"],
            "score": 0.0,
        }
        siblings.append(chunk)
        seen_headings.add(src["heading"])
    retrieval["doc_context"] = siblings

PRIVACY_DIRECTIVE = (
    "The customer is asking for internal-only or private data. Refuse to disclose it, "
    "do not repeat the sensitive values, explain that this data cannot be shared, "
    "and recommend human support."
)


def _build_directives(retrieval: dict, user_message: str) -> tuple[list[str], list[str]]:
    directives, reasons = [], []

    if retrieval["conflict"]:
        files = ", ".join(retrieval["conflict_files"])
        directives.append(
            f"The active official documents ({files}) genuinely conflict on this topic. "
            "State the inconsistency explicitly, present both versions, pick neither, "
            "and recommend human confirmation."
        )
        reasons.append(f"conflicting_active_sources:{files}")

    if retrieval["insufficient"]:
        directives.append(
            "No relevant knowledge-base passages were found. Say explicitly that the "
            "supplied information is insufficient for a reliable answer and recommend "
            "human support. Do not answer from general knowledge."
        )
        reasons.append("insufficient_kb_coverage")

    if prompts.is_privacy_probe(user_message):
        directives.append(PRIVACY_DIRECTIVE)
        reasons.append("privacy_request")

    if retrieval["low_confidence"] and len(retrieval["results"]) <= 1:
        directives.append(
            "Retrieval found no passage that directly and confidently answers this "
            "question. Treat the reference material as non-answerable for this topic: "
            "say the supplied information is insufficient and recommend human support."
        )
        reasons.append("low_confidence_kb_coverage")

    if re.search(
        r"damaged|defective|broken|cracked|torn|ripped|smashed|shattered|"
        r"doesn'?t work|not working|wrong item",
        user_message,
        re.IGNORECASE,
    ):
        directives.append(
            "The customer reports an item problem. Explain the reporting policy and "
            "available resolutions from references. Do NOT promise or approve any "
            "replacement, refund, or return: these require human review."
        )
        reasons.append("item_issue_requires_human_review")

    wants_action = re.search(
        r"\b(please|i want|i need|can you|could you|right now|immediately|now)\b",
        user_message,
        re.IGNORECASE,
    )
    action_request = re.search(
        r"\b(refund|cancel\w*|replacement|replace it|exchange|address change|"
        r"change (my|the) address|price adjustment)\b",
        user_message,
        re.IGNORECASE,
    )
    if wants_action and action_request:
        directives.append(
            "This system supports LOOKUP ONLY - it cannot perform refunds, "
            "cancellations, replacements, exchanges, or account changes. Explain "
            "politely that you cannot complete this action, share any relevant "
            "policy information from references, and recommend human support."
        )
        reasons.append("action_request_beyond_capabilities")

    return directives, reasons


def _should_re_retrieve(retrieval: dict) -> bool:
    return retrieval["insufficient"] or retrieval["low_confidence"]


def _retrieve_with_context(session_id: str, user_message: str) -> dict:
    retrieval = retrieve(user_message)
    if not _should_re_retrieve(retrieval):
        _add_doc_context(retrieval)
        return retrieval

    history = SESSIONS.get_history(session_id)
    previous_user = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), None
    )
    if previous_user:
        combined = retrieve(f"{previous_user} {user_message}")
        if combined["results"] and (
            not retrieval["results"]
            or combined["results"][0]["score"] > retrieval["results"][0]["score"]
        ):
            combined["follow_up_resolved"] = True
            retrieval = combined
    _add_doc_context(retrieval)
    return retrieval


def _execute_tool(name: str, arguments: dict) -> dict:
    if name != "lookup_order":
        return {"result": "error", "message": f"Unknown tool: {name}"}
    return lookup_order(arguments.get("order_id", ""))


def handle_turn(session_id: str, user_message: str) -> dict:
    retrieval = _retrieve_with_context(session_id, user_message)
    directives, handoff_reasons = _build_directives(retrieval, user_message)

    system_prompt = prompts.build_system_prompt(retrieval, directives)
    history = SESSIONS.get_history(session_id)
    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": user_message}
    ]

    tool_events = []
    final_text = ""
    for _ in range(MAX_TOOL_ROUNDS):
        response = llm.chat(messages, use_tools=True)
        message = response.choices[0].message

        if message.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [tc.model_dump() for tc in message.tool_calls],
                }
            )
            for tool_call in message.tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                result = _execute_tool(tool_call.function.name, arguments)
                tool_events.append(
                    {
                        "tool": tool_call.function.name,
                        "arguments": arguments,
                        "sanitized_result": result,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )
            continue

        final_text = message.content or ""
        break
    else:
        final_text = (
            "I'm sorry, I couldn't complete this request reliably. "
            f"{SUPPORT_CONTACT_MESSAGE}."
        )

    for event in tool_events:
        result = event["sanitized_result"]
        if result.get("result") == "not_found":
            handoff_reasons.append("order_not_found")
        elif result.get("result") == "malformed":
            handoff_reasons.append("malformed_order_id")
        elif result.get("result") == "found" and result["order"]["status"] == "exception":
            handoff_reasons.append("order_exception_status")

    if any(event["sanitized_result"].get("result") == "found" for event in tool_events):
        handoff_reasons = [
            reason
            for reason in handoff_reasons
            if reason not in ("insufficient_kb_coverage", "low_confidence_kb_coverage")
        ]

    human_handoff = bool(handoff_reasons)

    sources = []
    if not any(r.startswith("privacy_request") for r in handoff_reasons):
        seen = set()
        for chunk in retrieval["results"]:
            key = (chunk["filename"], chunk["heading"])
            if key not in seen:
                seen.add(key)
                sources.append({"filename": chunk["filename"], "heading": chunk["heading"]})
            if len(sources) >= 4:
                break

    SESSIONS.append(session_id, "user", user_message)
    SESSIONS.append(session_id, "assistant", final_text)

    trace = {
        "session_id": session_id,
        "user_message": user_message,
        "history_used": history,
        "retrieval": {
            "query": retrieval["query"],
            "results": [
                {k: v for k, v in c.items() if k != "text"} | {"text_excerpt": c["text"][:200]}
                for c in retrieval["results"]
            ],
            "doc_context_headings": [c["heading"] for c in retrieval.get("doc_context", [])],
            "conflict": retrieval["conflict"],
            "low_confidence": retrieval["low_confidence"],
            "insufficient": retrieval["insufficient"],
        },
        "tool_calls": tool_events,
        "handoff_reasons": handoff_reasons,
        "human_handoff": human_handoff,
        "final_response": final_text,
    }

    TraceLogger(session_id).log_turn(trace)

    return {
        "answer": final_text,
        "sources": sources,
        "human_handoff": human_handoff,
        "trace": trace,
    }


def main() -> None:
    import uuid

    session_id = str(uuid.uuid4())
    print(f"Aster & Row support agent (session {session_id[:8]}). Type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            break
        outcome = handle_turn(session_id, user_input)
        print(f"\nAgent: {outcome['answer']}")
        if outcome["sources"]:
            print("\nSources:")
            for s in outcome["sources"]:
                print(f"  - {s['filename']} :: {s['heading']}")
        if outcome["human_handoff"]:
            print("\n[HUMAN HANDOFF RECOMMENDED]")
        print()


if __name__ == "__main__":
    main()
