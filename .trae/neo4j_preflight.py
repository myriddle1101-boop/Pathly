from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


KG_DIR = Path(__file__).resolve().parent.parent / "KG_construction"
if str(KG_DIR) not in sys.path:
    sys.path.insert(0, str(KG_DIR))

from env_loader import load_project_env

load_project_env()

from pathly_neo4j import require_neo4j


def main() -> None:
    parser = argparse.ArgumentParser(description="Require a real Neo4j query before Pathly starts.")
    parser.add_argument("--start-desktop", action="store_true")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    result = require_neo4j(start_desktop=args.start_desktop, timeout_seconds=args.timeout)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
