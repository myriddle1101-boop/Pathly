# K1 Golden Knowledge Chain Audit

Date: 2026-08-11  
Mode: read-only  
Formal KG source: Neo4j (`query_verified=true`, 366 Concept nodes)

## Outcome

The five-concept chain has usable, manually validated PDF coverage, but it is not yet a fully reusable public Neo4j-to-Chroma source chain. All five concepts therefore require relationship or provenance review before P1 publication.

| Concept | Neo4j node | Relationships | PDF source | Chroma traceability | Overall |
|---|---|---|---|---|---|
| Linear Separability | Present | Missing explicit bridge to XOR | `06_mlp.pdf`, pp. 2–3 | 34 resource chunks; no page/concept metadata | needs_relationship_review |
| XOR | Missing | No canonical relationships | `06_mlp.pdf`, pp. 2–7 | 34 resource chunks; no page/concept metadata | needs_relationship_review |
| Neural Networks | Present | Noisy prerequisites; cycle with Activation Functions | `cs224n-2026-lecture03-neuralnets.pdf`, pp. 13–14 | 13 resource chunks; no page/concept metadata | needs_relationship_review |
| Activation Functions | Present | Cycle with Neural Networks | same PDF, pp. 15–17 | 13 resource chunks; no page/concept metadata | needs_relationship_review |
| Gradient Descent | Present | Backpropagation currently precedes Gradient Descent | same PDF, pp. 18–20 | 13 resource chunks; no page/concept metadata | needs_relationship_review |

## Important distinction

- The PDF pages are pedagogically usable and have been validated against required terms.
- That does **not** yet mean the full production provenance chain exists.
- Page sequences currently come from the reviewed golden-source registry. Public Chroma chunks are resource-level and do not preserve page or concept metadata.
- Neo4j resources do not currently carry enough origin/license metadata for an authorization conclusion. Both PDFs remain `needs_source_review` for provenance/licensing.

## Required K1 follow-up for P1

1. Create or merge a canonical `XOR` Concept node.
2. Review and publish the intended prerequisite chain without cycles.
3. Remove or demote irrelevant Concept–Resource matches, especially for Neural Networks.
4. Backfill public Chroma chunks with canonical concept IDs and page metadata.
5. Register stable public Concept–Resource–Document–Ordered Pages relations.
6. Add source URL and licensing/reuse-review metadata before public publication.

## Reproduction

```powershell
$env:KG_BACKEND='neo4j'
& 'D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe' kg_golden_audit.py
```

Machine-readable evidence: `artifacts/k1_golden_chain_audit.json`.
