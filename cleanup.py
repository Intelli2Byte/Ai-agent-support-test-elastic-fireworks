import argparse
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TRACES_DIR = BASE_DIR / "traces"
CACHE_PATH = BASE_DIR / ".llm_cache.sqlite"


def cleanup_traces(keep_days: int, max_sessions: int) -> None:
    if not TRACES_DIR.exists():
        print("No traces directory yet.")
        return

    files = sorted(
        TRACES_DIR.glob("session-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    cutoff = time.time() - keep_days * 86400

    removed = 0
    for path in files:
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1

    remaining = sorted(
        TRACES_DIR.glob("session-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for path in remaining[max_sessions:]:
        path.unlink()
        removed += 1

    kept = len(list(TRACES_DIR.glob("session-*.jsonl")))
    total_kb = sum(p.stat().st_size for p in TRACES_DIR.glob("*.jsonl")) / 1024
    print(f"Removed {removed} trace files. Kept {kept} sessions ({total_kb:.1f} KB total).")


def cache_stats() -> None:
    if not CACHE_PATH.exists():
        print("No LLM cache yet.")
        return
    import sqlite3

    conn = sqlite3.connect(CACHE_PATH)
    count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    conn.close()
    size_mb = CACHE_PATH.stat().st_size / (1024 * 1024)
    print(f"LLM cache: {count} responses, {size_mb:.2f} MB.")
    print("Each entry saves one Fireworks call - clearing it only costs API credit on re-runs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up local traces and inspect cache.")
    parser.add_argument("--keep-days", type=int, default=7)
    parser.add_argument("--max-sessions", type=int, default=50)
    args = parser.parse_args()

    cleanup_traces(args.keep_days, args.max_sessions)
    cache_stats()


if __name__ == "__main__":
    main()
