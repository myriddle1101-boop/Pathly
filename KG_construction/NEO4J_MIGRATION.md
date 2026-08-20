# Neo4j / Cypher Migration Guide

This project now supports Neo4j as an optional Knowledge Graph backend.
The default backend remains JSON, so the existing pipeline and Streamlit app can run without Neo4j.

## Layer Boundary

- Neo4j stores structured domain knowledge only: `Concept`, `PREREQUISITE_OF`, `SIMILAR_TO`.
- SQLite / JSON stores learner profile and dynamic progress.
- ChromaDB stores resource chunks and embeddings.
- Agents combine these layers; learner state is not written into Neo4j.

## Environment

Copy `.env.example` to one of the supported `.env` locations, then fill in local secrets:

- `D:\ic\master project\project_code\.env`
- `D:\ic\master project\project_code\KG_construction\.env`

The loader reads the project-level file first, then the `KG_construction` file. Existing shell environment variables are not overwritten.

For temporary PowerShell configuration, set:

```powershell
$env:KG_BACKEND = "neo4j"
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<your-password>"
$env:NEO4J_DATABASE = "neo4j"
```

Leave `KG_BACKEND` unset, or set it to `json`, to use the existing JSON backend. Keep `KG_BACKEND=json` until Neo4j is running, imported, and acceptance checks pass.

## Diagnostics

Run this first when checking a Neo4j setup. By default it does not connect to Neo4j or mutate data:

```powershell
cd "D:\ic\master project\project_code"
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_diagnostics.py --graph KG_construction\web_data\global\global_knowledge_graph.json
```

It reports environment readiness, whether the Python driver is installed, optional CLI availability, and the dry-run graph mapping counts.

To also compare live Neo4j counts after import:

```powershell
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_diagnostics.py --graph KG_construction\web_data\global\global_knowledge_graph.json --live
```

## Offline Validation

This does not connect to Neo4j. It verifies how the current JSON graph will map to Neo4j:

```powershell
cd "D:\ic\master project\project_code"
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_verify.py --graph KG_construction\web_data\global\global_knowledge_graph.json
```

Expected current result:

```json
{
  "concepts": 76,
  "prerequisite_edges": 56,
  "similarity_edges": 12,
  "skipped_edges": 0
}
```

## Import

Run this after Neo4j is running and credentials are configured:

```powershell
cd "D:\ic\master project\project_code\KG_construction"
.\.venv\Scripts\python.exe infra\neo4j_importer.py --graph web_data\global\global_knowledge_graph.json
```

The importer is idempotent: it uses `MERGE` for concepts and relationships.

When importing a graph that clearly belongs to one source PDF/resource, optionally create a `Resource` node and connect every imported concept to it:

```powershell
.\.venv\Scripts\python.exe infra\neo4j_importer.py --graph web_data\runs\Security and Privacy in ML\knowledge_graph.json --resource-path "web_data\runs\Security and Privacy in ML\Security and Privacy in ML.pdf"
```

For a run-level `knowledge_graph.json`, you can let the importer bind the only sibling PDF automatically:

```powershell
.\.venv\Scripts\python.exe infra\neo4j_importer.py --graph web_data\runs\AIChallenges\knowledge_graph.json --auto-resource
```

`--auto-resource` is conservative: it only binds a resource when the graph file is named `knowledge_graph.json` and exactly one PDF exists in the same directory. If there are zero or multiple PDFs, no `Resource` is created unless `--resource-path` is provided explicitly.

Do not pass `--resource-path` for the global merged graph unless the global graph is intentionally treated as one resource.

To batch-create run-level `Resource` nodes and `HAS_RESOURCE` links from existing processed documents:

```powershell
cd "D:\ic\master project\project_code"
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_resource_batch_importer.py --runs-dir KG_construction\web_data\runs --dry-run
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_resource_batch_importer.py --runs-dir KG_construction\web_data\runs
```

The batch importer only processes run directories that contain both `knowledge_graph.json` and exactly one sibling PDF. It skips missing-graph, missing-PDF, and multi-PDF directories unless a future explicit resource mapping is added. The current reproducible batch should process 9 runs, create 9 `Resource` nodes, and create 87 `HAS_RESOURCE` links. It should not be run against `web_data\global\global_knowledge_graph.json`.

## Live Validation

After import, compare Neo4j live counts with the JSON graph:

```powershell
cd "D:\ic\master project\project_code"
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_verify.py --graph KG_construction\web_data\global\global_knowledge_graph.json --live
```

Passing criteria:

- `Concept` count equals JSON node count.
- `PREREQUISITE_OF` count equals JSON prerequisite edge count.
- `SIMILAR_TO` count equals JSON similarity edge count.
- No Neo4j node has learner dynamic state fields such as `mastery_vector`, `completed_topics`, or `current_day`.

After batch Resource import, run the resource-aware gate:

```powershell
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_verify.py --graph KG_construction\web_data\global\global_knowledge_graph.json --live --include-resources --min-resources 9 --min-has-resource-edges 87
```

Additional passing criteria:

- `Resource` count is at least the requested minimum.
- `HAS_RESOURCE` count is at least the requested minimum.
- Every `Resource` has `id`, `title`, `filename`, `path`, `sha256`, `doc_type`, and `source_type`.

## Cypher Checks

```cypher
MATCH (c:Concept) RETURN count(c);
MATCH ()-[r:PREREQUISITE_OF]->() RETURN count(r);
MATCH ()-[r:SIMILAR_TO]->() RETURN count(r);
MATCH (r:Resource) RETURN count(r);
MATCH ()-[r:HAS_RESOURCE]->() RETURN count(r);
```

Use the directed `->` count for `SIMILAR_TO` validation. Undirected Cypher patterns are still useful for retrieval, but they can produce duplicate rows when used as aggregate count checks.

Layer boundary check:

```cypher
MATCH (n)
WITH n, labels(n) AS labels,
     [field IN [
       "goal", "timeline_days", "prior_knowledge", "skill_tree",
       "learning_preferences", "interests", "mastery_vector",
       "completed_topics", "last_practice", "current_day"
     ] WHERE n[field] IS NOT NULL] AS fields
WHERE size(fields) > 0
RETURN labels, coalesce(n.id, n.user_id, "") AS id, fields
LIMIT 10;
```

## Planning Backend Comparison

After Neo4j import and live validation pass, compare Planning Agent's stable output between JSON and Neo4j backends:

```powershell
cd "D:\ic\master project\project_code"
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\planning_backend_compare.py --graph KG_construction\web_data\global\global_knowledge_graph.json --goal "learn neural networks" --target-concept "Neural Networks" --days 7 --daily-minutes 60
```

The comparison ignores unstable fields such as `plan_id` and free-text reasons. It compares target mapping, prerequisite paths, ordered topics, day focus topics, prerequisite bridges, and overflow topics.

## Content And Adaptation Context Smoke

Validate that Content and Adaptation can read KG structure context without touching Profile Store or running LLM generation:

```powershell
cd "D:\ic\master project\project_code"
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\agent_context_smoke.py --backend json --graph KG_construction\web_data\global\global_knowledge_graph.json --concept "Neural Networks"
```

After Neo4j import and live validation pass, run the same smoke check against Neo4j:

```powershell
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\agent_context_smoke.py --backend neo4j --graph KG_construction\web_data\global\global_knowledge_graph.json --concept "Neural Networks"
```

The smoke check verifies:

- Content Agent context can retrieve the concept, prerequisites, similar concepts, and optional resources.
- Adaptation Agent candidate retrieval can inspect the same KG context.
- Profile Store is not accessed or updated.
- LLM generation is not executed.

## End-To-End Neo4j Acceptance

After Neo4j is running and credentials are configured, run the read-only acceptance gates:

```powershell
cd "D:\ic\master project\project_code"
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_migration_acceptance.py --graph KG_construction\web_data\global\global_knowledge_graph.json --concept "Neural Networks" --goal "learn neural networks" --target-concept "Neural Networks"
```

This runs:

- live diagnostics
- live count and layer-boundary verification
- JSON vs Neo4j Planning backend comparison
- Neo4j Content/Adaptation context smoke

To import before running the same gates, pass `--import-first`. This writes to Neo4j:

```powershell
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_migration_acceptance.py --graph KG_construction\web_data\global\global_knowledge_graph.json --concept "Neural Networks" --goal "learn neural networks" --target-concept "Neural Networks" --import-first
```

Example prerequisite query:

```cypher
MATCH (pre:Concept)-[:PREREQUISITE_OF]->(c:Concept {id: "Neural Networks"})
RETURN pre.id AS prerequisite
ORDER BY prerequisite;
```

Example similarity query:

```cypher
MATCH (c:Concept {id: "Neural Networks"})-[r:SIMILAR_TO]-(sim:Concept)
RETURN sim.id AS similar_concept, r.score AS score
ORDER BY score DESC;
```

## Planning Agent Backend Switch

Default:

```powershell
$env:KG_BACKEND = "json"
```

Neo4j:

```powershell
$env:KG_BACKEND = "neo4j"
```

Then run the existing Planning Agent entrypoints. If Neo4j is unavailable, switch back to `json`.

## Agent Structure Context

Both JSON and Neo4j KG repositories expose `get_concept_context(concept_id)`.
This is the intended Knowledge Graph Layer interface for future Content Agent and Adaptation Agent work.
It returns concept properties, prerequisite concept IDs, similar concepts, and optional resources.

`agents/content_context_service.py` composes this KG context with optional RAG chunks.
It is retrieval/context assembly only; it does not call an LLM or generate lesson content.
RAG chunk metadata now includes `resource_id` and `resource_filename` when `stage1_chunks.json` is next to a run-level `knowledge_graph.json` and exactly one sibling PDF. `resource_id` uses the same value as the Neo4j `Resource.id`, so ChromaDB chunks can be aligned to `(:Resource)` without storing chunk text in Neo4j.

When a learner profile is provided, Content context also computes `recommended_resources`.
Resource difficulty is derived dynamically from the average `difficulty_level` of concepts linked to the same resource; it is not written back to Neo4j.
The first matching policy only uses `known_topics` and `prior_knowledge_level`, not anxiety, confidence, motivation, math foundation, or programming foundation.
If a recommended resource exists and a RAG repository is available, chunks are first queried with `resource_id`; empty results fall back to topic-only retrieval.

Example resource-matching smoke check:

```powershell
.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\agent_context_smoke.py --backend neo4j --graph KG_construction\web_data\global\global_knowledge_graph.json --concept "Neural Networks" --known-topic "Linear Separability"
```

`agents/adaptation_candidate_service.py` uses the same KG context to suggest remediation candidates.
It prefers `SIMILAR_TO` concepts and falls back to prerequisite bridges.
It does not update learner profile state or reallocate the learning calendar.

`tests/test_agent_services_smoke.py` verifies that Planning, Content context assembly, and Adaptation candidate retrieval can share the same KG repository in offline JSON mode before live Neo4j validation.
