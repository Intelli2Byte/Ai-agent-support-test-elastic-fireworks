import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastembed import TextEmbedding

from es_client import get_client

INDEX_NAME = "kb_chunks"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
MIN_ABS_SCORE = 0.80
LOW_CONFIDENCE_SCORE = 0.86
TAIL_MARGIN = 0.12
CONFLICT_MARGIN = 0.08

CONTRADICTION_RULES = [
    {
        "topic_terms": ["tumbler"],
        "marker_a": re.compile(r"hand[- ]wash", re.IGNORECASE),
        "marker_b": re.compile(r"dishwasher safe", re.IGNORECASE),
    },
]

_embedder = None
_citable_filter = [
    {"term": {"status": "active"}},
    {"term": {"policy_authority": "official"}},
    {"term": {"audience": "customer"}},
]


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=MODEL_NAME)
    return _embedder


def embed_query(query: str) -> list[float]:
    return next(get_embedder().embed([query])).tolist()


def _hit_to_result(hit: dict) -> dict:
    src = hit["_source"]
    return {
        "filename": src["filename"],
        "heading": src["heading"],
        "document_id": src.get("document_id", ""),
        "doc_type": src.get("doc_type", ""),
        "title": src.get("title", ""),
        "text": src["text"],
        "score": hit["_score"],
    }


def _detect_conflicts(results: list[dict]) -> tuple[bool, list[str]]:
    if len({r["filename"] for r in results}) < 2:
        return False, []
    strong = [r for r in results if r["score"] >= results[0]["score"] - CONFLICT_MARGIN]
    by_file = {}
    for r in strong:
        by_file.setdefault(r["filename"], []).append(r)
    if len(by_file) < 2:
        return False, []

    for rule in CONTRADICTION_RULES:
        a_files, b_files = [], []
        for filename, chunks in by_file.items():
            joined = " ".join(c["text"].lower() for c in chunks)
            if not any(term in joined.lower() for term in rule["topic_terms"]):
                continue
            if any(rule["marker_a"].search(text) for text in (c["text"] for c in chunks)):
                a_files.append(filename)
            if any(rule["marker_b"].search(text) for text in (c["text"] for c in chunks)):
                b_files.append(filename)
        overlap = sorted((set(a_files) | set(b_files)) & set(by_file))
        if a_files and b_files and len(set(a_files) | set(b_files)) >= 2:
            return True, overlap
    return False, []


def retrieve(query: str, k: int = 8) -> dict:
    es = get_client()
    vector = embed_query(query)

    response = es.search(
        index=INDEX_NAME,
        knn={
            "field": "embedding",
            "query_vector": vector,
            "k": k,
            "num_candidates": 100,
            "filter": _citable_filter,
        },
        size=k,
        source_excludes=["embedding"],
    )

    results = [_hit_to_result(hit) for hit in response["hits"]["hits"]]
    if results:
        floor = max(MIN_ABS_SCORE, results[0]["score"] - TAIL_MARGIN)
        results = [r for r in results if r["score"] >= floor]

    conflict, conflict_files = _detect_conflicts(results)

    return {
        "query": query,
        "results": results,
        "conflict": conflict,
        "conflict_files": conflict_files,
        "low_confidence": bool(results) and results[0]["score"] < LOW_CONFIDENCE_SCORE,
        "insufficient": len(results) == 0,
    }


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "What is the return window?"
    output = retrieve(query)
    print(f"Query: {output['query']}")
    print(f"Conflict: {output['conflict']} {output['conflict_files']}")
    print(f"Insufficient: {output['insufficient']}")
    for i, r in enumerate(output["results"], 1):
        print(f"\n{i}. [{r['score']:.3f}] {r['filename']} :: {r['heading']}")
        print("   " + r["text"][:150].replace("\n", " ") + "...")
