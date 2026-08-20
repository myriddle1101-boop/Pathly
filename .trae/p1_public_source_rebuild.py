"""Rebuild Pathly's reusable public Concept-to-Source sidecar projection."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
KG_DIR = (PROJECT_ROOT / "KG_construction").resolve()
DEFAULT_OUTPUT = ROOT / "artifacts" / "p1_public_source_registry.json"


def load_environment() -> None:
    sys.path.insert(0, str(KG_DIR))
    try:
        from env_loader import load_project_env

        load_project_env()
    except (ImportError, AttributeError):
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env", override=False)
        load_dotenv(KG_DIR / ".env", override=False)
    os.environ["KG_BACKEND"] = "neo4j"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-empty", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    load_environment()
    from pathly_backend import PLAN_DB
    from public_source_registry import PublicConceptSourceRegistry

    registry = PublicConceptSourceRegistry(PLAN_DB, KG_DIR)
    if args.if_empty and registry.count() > 0:
        result = {
            "status": "already_populated",
            "concept_count": registry.count(),
            "records": registry.list_all(),
        }
    else:
        result = {"status": "rebuilt", **registry.rebuild()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
