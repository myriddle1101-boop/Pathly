# Pathly evaluation pack

This folder keeps **research evaluation** separate from unit and integration
tests.  The package has two complementary KG protocols:

1. `kg_corpus_audit.py` audits every available KG pipeline run.  It reports
   data quality and structural health; it does not claim semantic accuracy.
2. `KG_construction/evaluation/kg_quality_eval.py` reports topic and
   prerequisite Precision/Recall/F1 only for a manually annotated gold sample.

Run the static pack from `.trae`:

```powershell
& ..\KG_construction\.venv\Scripts\python.exe evaluation\build_static_pack.py
```

The command creates `evaluation/results/` and never changes an existing KG
run, benchmark or production database.  A fresh live golden-chain audit is
optional and explicitly queries Neo4j/Chroma:

```powershell
& ..\KG_construction\.venv\Scripts\python.exe kg_golden_audit.py --output evaluation\results\kg_golden_chain_audit.json
```

`goal_catalog.json` is the allowed input catalogue for the controlled
end-to-end study.  The five "full experience" goals are different learner
intent phrasings, not five independent subject domains: at present they all
resolve to the same verified neural-foundations chain.  This is deliberate and
must be stated in the thesis.

## Manual work still required

* Complete `templates/kg_gold_annotation_template.csv` for one bounded topic
  (20--30 concepts and 20--30 prerequisite edges).
* Score the blinded planning/content outputs with the rubrics in
  `templates/manual_scoring_template.csv`.
* If running the optional user pilot, collect consent and use the questionnaire
  in `templates/pilot_questionnaire.md`.

Do not turn passing tests, corpus-health results, or LLM scores into claims of
learning effectiveness.
