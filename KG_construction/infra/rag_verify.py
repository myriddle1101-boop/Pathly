from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import CHROMA_PATH


def _collection(collection_name: str):
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(name=collection_name)


def verify_rag(
    *,
    collection_name: str = "kg_chunks",
    resource_id: str | None = None,
    min_chunks: int = 1,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "collection_name": collection_name,
        "chroma_path": str(CHROMA_PATH),
        "resource_id": resource_id,
        "min_chunks": min_chunks,
        "passed": True,
        "checks": [],
    }
    collection = _collection(collection_name)
    total_count = collection.count()
    result["total_count"] = int(total_count)
    result["checks"].append({"name": "collection_has_chunks", "actual": int(total_count), "passed": total_count > 0})
    if total_count <= 0:
        result["passed"] = False

    if resource_id:
        rows = collection.get(where={"resource_id": resource_id}, limit=5)
        ids = rows.get("ids", [])
        metadatas = rows.get("metadatas", [])
        documents = rows.get("documents", [])
        resource_count = len(ids)
        resource_passed = resource_count >= min_chunks
        result["resource_count_sampled"] = resource_count
        result["checks"].append(
            {
                "name": "resource_id_chunks",
                "resource_id": resource_id,
                "minimum": min_chunks,
                "sampled": resource_count,
                "passed": resource_passed,
            }
        )
        if not resource_passed:
            result["passed"] = False
        required_metadata = ["resource_id", "resource_filename", "chunk_id", "doc_name"]
        metadata_examples = metadatas[:5]
        missing_metadata = []
        for metadata in metadata_examples:
            missing = [field for field in required_metadata if field not in metadata or metadata.get(field) in [None, ""]]
            if missing:
                missing_metadata.append({"metadata": metadata, "missing": missing})
        metadata_passed = not missing_metadata and bool(metadata_examples)
        result["checks"].append(
            {
                "name": "resource_metadata_fields",
                "required": required_metadata,
                "passed": metadata_passed,
                "examples": missing_metadata,
            }
        )
        if not metadata_passed:
            result["passed"] = False
        result["examples"] = [
            {
                "id": doc_id,
                "metadata": metadata,
                "text_preview": str(document)[:240],
            }
            for doc_id, metadata, document in zip(ids, metadatas, documents)
        ]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify ChromaDB RAG chunk storage.")
    parser.add_argument("--collection", default="kg_chunks", help="ChromaDB collection name")
    parser.add_argument("--resource-id", default=None, help="Optional Resource.id to verify")
    parser.add_argument("--min-chunks", type=int, default=1, help="Minimum chunks required for --resource-id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_rag(
        collection_name=args.collection,
        resource_id=args.resource_id,
        min_chunks=args.min_chunks,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
