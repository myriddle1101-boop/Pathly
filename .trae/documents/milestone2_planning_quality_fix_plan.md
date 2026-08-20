# Milestone 2 Planning Quality Fix Plan

## Background

The real 30-day request "learn machine-learning fundamentals, especially RAG" exposed four connected defects: RAG was incorrectly mapped to `Latent Dynamics Models`, the prerequisite graph returned only two isolated topics, the allocator treated each topic as an indivisible day and padded the remaining 28 days, and stored learner preferences did not influence the schedule.

## Repair stages

### Stage 1 — Goal terminology and topic mapping

- Normalize case, punctuation, Chinese/English names, and common acronyms.
- Resolve aliases such as `RAG` to `Retrieval-Augmented Generation` before candidate search.
- Accept exact/alias matches immediately.
- Auto-accept fuzzy or embedding candidates only at confidence `>= 0.78`.
- Require confirmation for confidence `0.60–0.78`.
- Treat candidates below `0.60` as unmatched.
- Never generate a plan when a requested core concept is unmatched or awaiting confirmation.
- Return candidates, confidence, method, and explanation to the caller.

### Stage 2 — RAG knowledge-graph coverage

- Build KG data through the 8501 developer console, not Pathly.
- Use existing project material, beginning with `cs224n-2026-lecture10-rag-agents.pdf`.
- Ensure Neo4j contains a canonical `Retrieval-Augmented Generation` node, aliases, summaries, difficulty, time estimate, and prerequisite relationships.
- Cover retrieval, embeddings, chunking, vector databases, reranking, context construction, grounded generation, hallucination, and RAG evaluation.
- Verify the RAG node has at least four meaningful prerequisites and no incorrect prerequisite cycles.

### Stage 3 — Learner-profile correctness

- Remove invented defaults such as converting empty known topics to `Python`.
- Preserve both raw learner statements and structured mappings.
- Attach confidence and reasons to inferred prior knowledge.
- Explicitly trace how foundations, confidence, time, pace, and preferred learning style affect planning.

### Stage 4 — Concept path and daily activity plan

- Separate the prerequisite concept path from daily learning activities.
- Support concept, example, coding practice, project, review, quiz, reflection, and milestone activities.
- Split large topics into activities that never exceed `daily_minutes`.
- Use the requested horizon with spaced review, assessment, and project milestones instead of unexplained empty buffer days.
- If the goal needs less time, present an early-completion option and a paced-consolidation option.

### Stage 5 — Preference-aware allocation

- Project preference: 30% concepts, 40% practice/project, 15% review, 10% quiz, 5% reflection.
- Mathematical preference: 45% theory, 25% derivation exercises, 15% practice, 10% quiz, 5% reflection.
- Intuitive preference: 40% concept/analogy, 25% examples, 20% practice, 10% quiz, 5% reflection.
- Record the applied mix and profile effects in the reasoning trace.

### Stage 6 — Pathly confirmation and visualization

- Add a goal-understanding confirmation step before planning.
- Show original terms, normalized terms, candidates, confidence, and unresolved concepts.
- Render the concept path separately from the full daily timeline.
- Show all requested days, daily activities, total minutes, review points, quizzes, and project milestones.
- Explain how the learner profile changed the plan.

## Target schema

Planning output will include `goal_interpretation`, `topic_mappings`, `profile_effects`, `concept_path`, activity-bearing `days`, `feasibility`, `reasoning_trace`, `mode`, and `sources`.

## Acceptance case

For a learner requesting machine-learning fundamentals with emphasis on RAG, 30 days, 60 minutes per day, programming foundation, and project preference:

- RAG maps to `Retrieval-Augmented Generation`, never `Latent Dynamics Models`.
- The concept path has at least eight meaningful nodes.
- The plan contains 30 meaningful days with no day above 60 minutes.
- It contains at least three practices, three quizzes, spaced reviews, and one through-line project.
- The UI explains how the project preference affected activity allocation.
- Neo4j failure may use the real JSON KG; total KG failure returns an error and never produces a synthetic plan.

## Checkpoints

Each stage is logged and paused for user confirmation. Stage 2 requires the user to trigger KG construction in the 8501 developer console; Codex will provide the file selection and verify Neo4j after the run.
