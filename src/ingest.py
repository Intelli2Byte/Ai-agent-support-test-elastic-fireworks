import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from elasticsearch import Elasticsearch, helpers
from fastembed import TextEmbedding

from config import KB_DIR
from es_client import get_client
from kb_parser import load_all_chunks

INDEX_NAME = "kb_chunks"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384

MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": DIMENSIONS,
                "index": True,
                "similarity": "cosine",
            },
            "filename": {"type": "keyword"},
            "heading": {"type": "keyword"},
            "status": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "audience": {"type": "keyword"},
            "policy_authority": {"type": "keyword"},
            "title": {"type": "keyword"},
        }
    },
}


def recreate_index(es: Elasticsearch) -> None:
    if es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
    es.indices.create(index=INDEX_NAME, **MAPPING)


def build_actions(chunks: list[dict], model: TextEmbedding):
    texts = [chunk["text"] for chunk in chunks]
    embeddings = [emb.tolist() for emb in model.embed(texts)]
    for chunk, embedding in zip(chunks, embeddings):
        doc_id = f"{chunk['filename']}::{chunk['heading']}"
        yield {
            "_op_type": "index",
            "_index": INDEX_NAME,
            "_id": doc_id,
            "_source": {**chunk, "embedding": embedding},
        }


def main() -> None:
    by_file = load_all_chunks(KB_DIR)
    if not by_file:
        print(f"No markdown files found in {KB_DIR}")
        sys.exit(1)

    total = sum(len(c) for c in by_file.values())
    print(f"Parsed {len(by_file)} files, {total} chunks total. Loading embedder...")

    model = TextEmbedding(model_name=MODEL_NAME)
    es = get_client()

    info = es.info()
    print(f"Connected to Elasticsearch cluster: {info['cluster_name']}")

    recreate_index(es)

    all_chunks = [chunk for chunks in by_file.values() for chunk in chunks]
    success, errors = helpers.bulk(
        es,
        build_actions(all_chunks, model),
        raise_on_error=False,
        refresh=True,
    )

    if errors:
        print(f"{len(errors)} indexing errors:")
        for err in errors[:10]:
            print(err)

    print("\nPer-file chunk counts:")
    skipped = False
    for filename in sorted(by_file):
        count = len(by_file[filename])
        flag = ""
        if count == 0:
            skipped = True
            flag = "  <-- WARNING: no chunks"
        print(f"  {filename}: {count}{flag}")
    if skipped:
        print("WARNING: some files produced zero chunks and were skipped!")

    indexed = es.count(index=INDEX_NAME)["count"]
    print(f"\nIndexed {success} docs; index '{INDEX_NAME}' now contains {indexed} docs.")
    if indexed != total:
        print(f"MISMATCH: expected {total}, got {indexed}")


if __name__ == "__main__":
    main()
