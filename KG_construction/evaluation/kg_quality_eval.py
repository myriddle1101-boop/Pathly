from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_topic_set(items: list[dict[str, Any]]) -> set[str]:
    values = set()
    for item in items:
        name = str(item.get("name", "")).strip().lower()
        if name:
            values.add(name)
    return values


def normalize_edge_set(items: list[dict[str, Any]]) -> set[tuple[str, str]]:
    values = set()
    for item in items:
        source = str(item.get("from", "")).strip().lower()
        target = str(item.get("to", "")).strip().lower()
        if source and target:
            values.add((source, target))
    return values


def metric_breakdown(predicted: set[Any], gold: set[Any]) -> dict[str, Any]:
    tp_items = sorted(predicted & gold)
    pred_only_items = sorted(predicted - gold)
    gold_only_items = sorted(gold - predicted)
    tp = len(tp_items)
    fp = len(pred_only_items)
    fn = len(gold_only_items)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "predicted": len(predicted),
        "gold": len(gold),
        "overlap_items": tp_items,
        "predicted_only_items": pred_only_items,
        "gold_only_items": gold_only_items,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_metrics_csv(path: Path, result: dict[str, Any]) -> None:
    rows = [
        ("topics", result["topic_metrics"]),
        ("prerequisites", result["prerequisite_metrics"]),
        ("similarity", result["similarity_metrics"]),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["metric_group", "precision", "recall", "f1", "tp", "fp", "fn", "predicted", "gold"],
        )
        writer.writeheader()
        for name, metrics in rows:
            writer.writerow(
                {
                    "metric_group": name,
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1": metrics["f1"],
                    "tp": metrics["tp"],
                    "fp": metrics["fp"],
                    "fn": metrics["fn"],
                    "predicted": metrics["predicted"],
                    "gold": metrics["gold"],
                }
            )


def evaluate_quality(
    *,
    predicted_topics_path: str | Path,
    predicted_prereq_path: str | Path,
    predicted_similarity_path: str | Path,
    gold_topics_path: str | Path,
    gold_prereq_path: str | Path,
    gold_similarity_path: str | Path,
    output_path: str | Path,
    sample_name: str = "default_quality_sample",
    metric_protocol: str = "set_precision_recall_f1",
) -> dict[str, Any]:
    predicted_topics_path = Path(predicted_topics_path).resolve()
    predicted_prereq_path = Path(predicted_prereq_path).resolve()
    predicted_similarity_path = Path(predicted_similarity_path).resolve()
    gold_topics_path = Path(gold_topics_path).resolve()
    gold_prereq_path = Path(gold_prereq_path).resolve()
    gold_similarity_path = Path(gold_similarity_path).resolve()
    output_path = Path(output_path).resolve()

    predicted_topics_data = load_json(predicted_topics_path)
    predicted_prereq_data = load_json(predicted_prereq_path)
    predicted_similarity_data = load_json(predicted_similarity_path)

    gold_topics_data = load_json(gold_topics_path)
    gold_prereq_data = load_json(gold_prereq_path)
    gold_similarity_data = load_json(gold_similarity_path)

    predicted_topics = normalize_topic_set(predicted_topics_data.get("topics", predicted_topics_data))
    predicted_prereq = normalize_edge_set(predicted_prereq_data.get("prerequisites", predicted_prereq_data))
    predicted_similarity = normalize_edge_set(predicted_similarity_data.get("similarity_edges", predicted_similarity_data))

    gold_topics = normalize_topic_set(gold_topics_data.get("topics", gold_topics_data))
    gold_prereq = normalize_edge_set(gold_prereq_data.get("prerequisites", gold_prereq_data))
    gold_similarity = normalize_edge_set(gold_similarity_data.get("similarity_edges", gold_similarity_data))

    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sample_name": sample_name,
        "metric_protocol": metric_protocol,
        "inputs": {
            "predicted_topics_path": str(predicted_topics_path),
            "predicted_prereq_path": str(predicted_prereq_path),
            "predicted_similarity_path": str(predicted_similarity_path),
            "gold_topics_path": str(gold_topics_path),
            "gold_prereq_path": str(gold_prereq_path),
            "gold_similarity_path": str(gold_similarity_path),
        },
        "topic_metrics": metric_breakdown(predicted_topics, gold_topics),
        "prerequisite_metrics": metric_breakdown(predicted_prereq, gold_prereq),
        "similarity_metrics": metric_breakdown(predicted_similarity, gold_similarity),
    }
    _write_json(output_path, result)
    summary_csv_path = output_path.with_name("kg_quality_eval_summary.csv")
    _write_metrics_csv(summary_csv_path, result)
    result["artifacts"] = {
        "quality_json": str(output_path),
        "quality_summary_csv": str(summary_csv_path),
    }
    _write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行固定输入的 KG 质量评测。")
    parser.add_argument("--predicted-topics", help="预测 stage2a 或 stage3 JSON 路径")
    parser.add_argument("--predicted-prereq", help="预测 stage2b JSON 路径")
    parser.add_argument("--predicted-similarity", help="预测 stage2c JSON 路径")
    parser.add_argument("--gold-topics", help="gold topics JSON 路径")
    parser.add_argument("--gold-prereq", help="gold prerequisites JSON 路径")
    parser.add_argument("--gold-similarity", help="gold similarity JSON 路径")
    parser.add_argument("--output-path", help="评测输出 JSON 路径")
    parser.add_argument("--sample-name", default="default_quality_sample", help="样本名称")
    parser.add_argument("--metric-protocol", default="set_precision_recall_f1", help="指标协议标识")
    return parser.parse_args()


def _ask_value(prompt: str, default: str | None = None) -> str:
    raw = input(prompt + "\n> ").strip().strip('"').strip("'")
    return raw or (default or "")


def main() -> None:
    args = parse_args()
    predicted_topics_path = args.predicted_topics or _ask_value("请输入预测 stage2a 或 stage3 JSON 路径：")
    predicted_prereq_path = args.predicted_prereq or _ask_value("请输入预测 stage2b JSON 路径：")
    predicted_similarity_path = args.predicted_similarity or _ask_value("请输入预测 stage2c JSON 路径：")
    gold_topics_path = args.gold_topics or _ask_value("请输入 gold topics JSON 路径：")
    gold_prereq_path = args.gold_prereq or _ask_value("请输入 gold prerequisites JSON 路径：")
    gold_similarity_path = args.gold_similarity or _ask_value("请输入 gold similarity JSON 路径：")
    output_path = args.output_path or _ask_value("请输入评测输出路径（回车使用 kg_quality_eval.json）：", "kg_quality_eval.json")

    result = evaluate_quality(
        predicted_topics_path=predicted_topics_path,
        predicted_prereq_path=predicted_prereq_path,
        predicted_similarity_path=predicted_similarity_path,
        gold_topics_path=gold_topics_path,
        gold_prereq_path=gold_prereq_path,
        gold_similarity_path=gold_similarity_path,
        output_path=output_path,
        sample_name=args.sample_name,
        metric_protocol=args.metric_protocol,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
