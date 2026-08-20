# CHANGEME

## 2026-07-08 Runtime Infrastructure v1

Implemented the first runtime harness for reproducible KG execution and node-details quality control.

New scripts:

- `KG_construction/infra/node_details_audit.py`
- `KG_construction/infra/difficulty_calibration.py`
- `KG_construction/infra/benchmark_kg.py`
- `KG_construction/infra/reproducibility_check.py`
- `KG_construction/infra/harness.py`

New outputs:

- `KG_construction/web_data/manifests/harness_*.json`
- `KG_construction/web_data/global/global_knowledge_graph_calibrated.json`

Validation:

```text
node_details_audit.py:
  total_concepts = 183
  difficulty_level level-2 ratio = 0.918
  warning = difficulty_level is overly concentrated at level 2

difficulty_calibration.py:
  updated_concepts = 117
  unchanged_concepts = 66
  original graph not overwritten

benchmark_kg.py:
  concept_count = 183
  edge_count = 178
  duplicate_concept_count = 0

reproducibility_check.py:
  calibration_deterministic = true

harness.py --stage all:
  manifest written to web_data/manifests/
  status = warning because difficulty distribution is over-concentrated

harness.py --stage neo4j --live-neo4j:
  Concept = 183
  Topic = 8
  Resource = 27
  BELONGS_TO = 183
  forbidden learner state nodes = 0
```

App update:

- Added `Check Runtime Infrastructure`.
- Displays node details audit, KG benchmark, Profile Store verification, and latest harness manifest.

Notes:

- Runtime warning is a quality-control signal, not a crash.
- The main detected issue is difficulty collapse: too many concepts have `difficulty_level = 2`.
- Calibrated difficulty is written to a separate graph file and does not overwrite `global_knowledge_graph.json`.

## 2026-07-08 Runtime Harness tab and RAG/Planning stages

Extended `infra/harness.py` with safe `rag` and `planning` stages.

New harness stages:

- `rag`
- `planning`

Updated full harness order:

```text
audit -> calibrate -> kg_benchmark -> profile -> rag -> planning -> reproducibility -> neo4j
```

Validation:

```text
rag stage:
  collection = kg_chunks
  total_count = 424
  status = success

planning stage:
  goal = learn neural networks
  target_concept = Neural Networks
  json_neo4j_parity = true
  status = success

full harness:
  manifest = web_data/manifests/harness_2026-07-08_140156.json
  overall status = warning
  warning source = difficulty_level concentrated at level 2
```

App update:

- Added a `Runtime Harness` tab.
- The tab shows Runtime status and lets the user run individual harness stages or `all`.
- Stage results are displayed in a table and expandable JSON sections.

Safety notes:

- `rag` stage verifies existing ChromaDB chunks; it does not ingest new chunks.
- `planning` stage uses deterministic target concepts and avoids LLM goal parsing.
- `calibrate` still writes only `global_knowledge_graph_calibrated.json` and does not overwrite the original graph.
