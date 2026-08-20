from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infra.device_manager import get_embedding_batch_size
from infra.neo4j_importer import _resolve_auto_resource_path, _resource_params
from infra.rag_repository import RAGRepository


def load_stage1_chunks(path: str | Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("stage1_chunks.json 格式错误，应为列表。")
    return data


def build_rag_rows(stage1_path: str | Path) -> list[dict[str, Any]]:
    chunk_path = Path(stage1_path)
    doc_name = chunk_path.parent.name
    resource = None
    resource_path = _resolve_auto_resource_path(chunk_path.parent / "knowledge_graph.json")
    if resource_path:
        resource = _resource_params(resource_path)
    chunks = load_stage1_chunks(chunk_path)
    rows = []
    for item in chunks:
        chunk_id = int(item.get("chunk_id", 0))
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        rows.append(
            {
                "id": f"{doc_name}-{chunk_id}",
                "doc_name": doc_name,
                "chunk_id": chunk_id,
                "doc_type": str(item.get("doc_type", "")),
                "resource_id": resource["id"] if resource else "",
                "resource_filename": resource["filename"] if resource else "",
                "concept_id": str(item.get("concept_id", item.get("concept_name", ""))),
                "concept_name": str(item.get("concept_name", item.get("concept_id", ""))),
                "topic_id": str(item.get("topic_id", item.get("topic_name", ""))),
                "topic_name": str(item.get("topic_name", item.get("topic_id", ""))),
                "word_count": int(item.get("word_count", len(text.split()))),
                "text": text,
            }
        )
    return rows


def ingest_stage1_chunks(stage1_path: str | Path, collection_name: str = "kg_chunks") -> int:
    report = ingest_stage1_chunks_with_report(stage1_path, collection_name=collection_name)
    return int(report["inserted"])


def ingest_stage1_chunks_with_report(
    stage1_path: str | Path,
    collection_name: str = "kg_chunks",
    force_device: str | None = None,
) -> dict[str, Any]:
    rows = build_rag_rows(stage1_path)
    repository = RAGRepository(collection_name=collection_name, force_device=force_device)
    inserted = repository.upsert_chunks(rows)
    device_info = repository.last_device_info or {}
    return {
        "stage": "rag_ingestion",
        "collection_name": collection_name,
        "input_path": str(Path(stage1_path)),
        "row_count": len(rows),
        "inserted": inserted,
        "batch_size": get_embedding_batch_size(device_info.get("selected_device")),
        "device_info": device_info,
    }


def ask_stage1_path() -> str:
    return input("请输入 stage1_chunks.json 完整路径：\n> ").strip().strip('"').strip("'")


def main() -> None:
    stage1_path = ask_stage1_path()
    report = ingest_stage1_chunks_with_report(stage1_path)
    print(
        "[OK] 已写入 ChromaDB chunk 数量: "
        f"{report['inserted']} | requested={report['device_info'].get('requested_device', 'cpu')} "
        f"selected={report['device_info'].get('selected_device', 'cpu')}"
    )


if __name__ == "__main__":
    main()
