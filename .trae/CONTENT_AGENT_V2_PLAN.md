# Pathly Content Agent v2 Plan: Source-First Annotated Learning Session

## 1. Decision

Do not replace the current Today Learning implementation directly.

Build Content Agent v2 as a parallel experience so the product can compare:

- `Content Agent v1`: current study-block lesson page.
- `Content Agent v2`: source-first annotated learning page.

The v2 page should be reachable from a separate route or toggle, for example:

- `/content-v2`
- `Today Learning -> Try Source-First Learning`
- `?content_agent=v2`

The current v1 page remains available and unchanged during development.

## 2. Product Thesis

Pathly's strongest demo is not generic AI-generated lessons.

The strongest demo is:

> A learner uploads many PDFs. Pathly understands the materials, extracts concept and prerequisite relationships, merges them with the public KG, builds a learning path, and then teaches each day by guiding the learner through selected source material with annotations, explanations, exercises, quiz, and future adaptation signals.

If the learner does not upload PDFs, the same experience still works by using public KG resources, public RAG material, or Pathly-generated fallback readings.

## 3. Core UX Shift

Current v1 flow:

```text
Lesson -> Resources -> Ask Pathly -> Quiz
```

New v2 flow:

```text
Learning Source -> Annotated Reading -> Concept Bridge -> Guided Exercise -> Checkpoint -> Quiz
```

Resource is no longer a side recommendation. Resource becomes the object the learner studies.

## 4. Source Selection Rules

Content Agent v2 uses a source-first hierarchy.

### 4.1 If private PDFs exist

Priority:

1. User-marked required PDFs.
2. PDF chunks strongly mapped to today's concepts.
3. PDF chunks that explain prerequisites for today's concepts.
4. Public KG resources to fill missing background.
5. Public RAG chunks for alternative explanations.
6. Pathly-generated fallback reading only if no usable source exists.

### 4.2 If no private PDFs exist

Priority:

1. Public KG-linked resources.
2. Public Chroma teaching chunks.
3. Curated built-in golden learning excerpts.
4. Pathly-generated fallback reading.

### 4.3 Source labels

Every reading item must clearly show source type:

```text
Your uploaded PDF
Public learning resource
Pathly-generated fallback
```

The UI must not pretend generated fallback is retrieved source material.

## 5. Content Agent v2 Output Contract

New contract name:

```text
annotated-session-v1
```

Top-level structure:

```json
{
  "contract_version": "annotated-session-v1",
  "content_agent_version": "content-agent-v2-source-first",
  "content_id": "uuid",
  "path_id": "path-id",
  "plan_id": "plan-v2-id",
  "day": 3,
  "scheduled_minutes": 120,
  "source_mode": "private_pdf_first | public_resource_first | generated_fallback",
  "session_overview": {},
  "reading_sequence": [],
  "concept_bridges": [],
  "guided_exercises": [],
  "checkpoint": {},
  "quiz_seed": {},
  "citations": [],
  "generation_metadata": {}
}
```

## 6. Data Model

### 6.1 Session Overview

```json
{
  "title": "Day 3: Reading RAG Architecture Through Your Papers",
  "goal_for_today": "Understand how retrieval, knowledge graphs, and generation connect in RAG systems.",
  "why_these_sources": "These excerpts explain the prerequisite relation between retrieval and generation, then connect it to your learning-path KG papers.",
  "estimated_minutes": 120,
  "source_summary": {
    "private_pdf_count": 2,
    "public_resource_count": 1,
    "generated_fallback_count": 0
  }
}
```

### 6.2 Reading Sequence

Each item is a learner-facing reading unit.

```json
{
  "reading_id": "reading-day3-01",
  "sequence": 1,
  "source_type": "private_pdf",
  "document_id": "doc-id",
  "document_title": "Graph Enhanced Learning Path Recommendation.pdf",
  "page_start": 2,
  "page_end": 4,
  "section_title": "Knowledge Concept Graph",
  "linked_concept_ids": ["knowledge_graph", "prerequisite_relation"],
  "estimated_minutes": 20,
  "reading_purpose": "Understand how the paper represents concepts and prerequisite relations.",
  "clean_excerpt": "...bounded cleaned excerpt...",
  "pathly_annotation": {
    "plain_explanation": "This paragraph defines the graph structure used later for planning.",
    "key_terms": [
      {
        "term": "knowledge concept",
        "meaning": "A unit of knowledge the learner may need to master.",
        "kg_concept_id": "knowledge_concept"
      }
    ],
    "why_it_matters": "Pathly uses this same node-edge idea when it creates your learning route.",
    "common_confusion": "Do not confuse prerequisite edges with similarity edges.",
    "read_this_way": [
      "First identify what the nodes represent.",
      "Then identify what the edges represent.",
      "Finally ask how this affects path order."
    ]
  },
  "learner_task": {
    "prompt": "In your own words, explain what nodes and edges represent in this excerpt.",
    "placeholder": "Nodes represent... Edges represent...",
    "minimum_words": 25
  }
}
```

### 6.3 Concept Bridge

Connects the reading material to the learning path and KG.

```json
{
  "bridge_id": "bridge-day3-kg",
  "concept_id": "knowledge_graph",
  "display_name": "Knowledge Graph",
  "source_reading_ids": ["reading-day3-01"],
  "prerequisites": ["graph", "node", "edge"],
  "next_unlocks": ["learning_path_planning", "rag_retrieval"],
  "explanation": "The PDF explains the graph representation; the public KG adds prerequisite and related-concept context.",
  "visual_hint": {
    "type": "mini_graph",
    "nodes": [],
    "edges": []
  }
}
```

### 6.4 Guided Exercise

Exercises are generated from the reading unit, not from a generic topic.

```json
{
  "exercise_id": "exercise-day3-01",
  "exercise_type": "locate_explain_apply",
  "source_reading_ids": ["reading-day3-01"],
  "linked_concept_ids": ["knowledge_graph"],
  "prompt": "Use the excerpt to identify the node type, edge type, and learning-path implication.",
  "steps": [
    "Locate the sentence defining nodes.",
    "Locate the sentence defining edges.",
    "Explain how this changes the order of a learning path."
  ],
  "hint": "Look for words such as concept, prerequisite, relation, and dependency.",
  "expected_answer_outline": [
    "Nodes are knowledge concepts.",
    "Edges encode prerequisite or dependency relations.",
    "A path planner uses edges to order what should be learned first."
  ],
  "learner_response_required": true
}
```

### 6.5 Checkpoint

```json
{
  "checkpoint_id": "checkpoint-day3",
  "prompt": "Explain how today's PDF excerpts support your learning path goal.",
  "required_elements": [
    "one source claim",
    "one KG concept",
    "one application to the learner's goal"
  ],
  "minimum_words": 40
}
```

## 7. UI Design: New Parallel Page

### 7.1 Route and Navigation

Add a parallel page without removing v1:

```text
Today Learning
  - Current Lesson View (v1)
  - Annotated Source View (v2)
```

Recommended initial route:

```text
state.dailyStage = "content_v2"
```

or a new view:

```text
view = "today_v2"
```

For comparison, keep both buttons visible in development:

```text
Study Blocks View | Annotated Source View
```

### 7.2 Page Layout

Desktop layout:

```text
Left/main:
- Session overview
- Reading sequence
- Annotated excerpt cards
- Concept bridge cards
- Guided exercises
- Checkpoint

Right/sidebar:
- Ask Pathly, scoped to current reading/excerpt
- Today's source map
- Completion progress
- Citations
```

### 7.3 Annotated Excerpt Card

Each card shows:

```text
PDF title / page range / source label
Clean excerpt
Pathly annotation
Key terms
Why this matters
Common confusion
Learner response box
Mark as read / Need explanation / Ask about this sentence
```

### 7.4 No PDF State

If no user PDFs exist, the same page appears with public sources:

```text
Source: Public learning resource
```

If public sources are weak:

```text
Source: Pathly-generated fallback reading
```

The learner still gets reading, annotation, exercise, and checkpoint.

## 8. API Plan

Keep existing v1 APIs stable.

Add v2 APIs:

```text
GET  /api/plans/{plan_id}/days/{day}/annotated-session
POST /api/plans/{plan_id}/days/{day}/annotated-session
POST /api/plans/{plan_id}/days/{day}/readings/{reading_id}/complete
PATCH /api/plans/{plan_id}/days/{day}/readings/{reading_id}/response
POST /api/plans/{plan_id}/days/{day}/exercises/{exercise_id}/submit
POST /api/annotated-chat
```

Existing chat can later be reused, but first implementation should keep `current_reading_id` and `current_excerpt_id` explicit.

## 9. Storage Plan

Add new SQLite tables without changing current v1 content tables:

```text
annotated_daily_sessions
annotated_reading_units
annotated_reading_progress
annotated_exercise_attempts
annotated_source_citations
```

The v1 tables remain intact:

```text
daily_contents
daily_sessions
daily_study_blocks
study_block_progress
```

This makes comparison safe.

## 10. Generation Pipeline

### Stage A: Source Selector

Input:

- plan day activities
- concept IDs
- user selected PDFs
- private chunks
- public KG
- public RAG

Output:

- ordered reading sequence
- source confidence
- coverage gaps

### Stage B: Evidence Cleaner

Reuse current `EvidencePreparer`, but strengthen it for PDF teaching:

- remove author/email/institution metadata
- remove references and headers
- preserve page and section metadata
- split into learner-readable excerpts
- label evidence role:
  - definition
  - example
  - method
  - prerequisite
  - limitation
  - exercise_basis

### Stage C: Annotation Generator

For each reading unit, generate:

- plain explanation
- key terms
- why this matters
- common confusion
- read-this-way guidance
- learner task

### Stage D: Exercise Generator

Generate exercises from selected reading units:

- locate
- explain
- apply
- compare
- build

### Stage E: Quiz Seed

Quiz should use:

- completed readings
- learner responses
- guided exercises
- concept bridges

Do not quiz unseen material.

## 11. Fallback Behavior

Fallback must remain useful.

If PDF exists but model fails:

- display cleaned excerpt
- deterministic annotation template
- deterministic concept bridge from KG
- deterministic locate/explain/apply exercise

If no PDF and no public source:

- generate a clearly labeled Pathly fallback reading
- do not claim citation or page number

## 12. Implementation Stages

### A1: Parallel Contract and Backend Skeleton

- Define `annotated-session-v1` schema.
- Add service module, for example `pathly_annotated_content.py`.
- Add storage tables for annotated sessions.
- Add read-only API to create/get annotated session.
- No frontend replacement.

Acceptance:

- Existing v1 tests still pass.
- New v2 endpoint returns source-first session JSON.
- If private PDFs exist, session uses private source first.
- If no PDFs exist, session falls back to public/generated source and labels it clearly.

### A2: Annotated Source Page

- Add a new page or tab beside current Today Learning.
- Render reading sequence and annotations.
- Show PDF title, page range, excerpt, source label, key terms, why it matters, and learner task.
- Add response boxes and completion state.
- Do not remove current v1 page.

Acceptance:

- User can compare v1 Study Blocks View and v2 Annotated Source View.
- v2 has no direct private IDs or raw metadata noise on screen.
- Learner can complete readings and exercises.

### A3: Source-Grounded Exercises

- Generate exercises from reading units.
- Save exercise attempts.
- Show expected answer outline after submission.
- Feed exercise signals into quiz seed.

Acceptance:

- Exercises reference exact readings.
- User cannot complete the day by only clicking through without responses.

### A4: Annotated Ask Pathly

- Chat context includes current reading, selected sentence/excerpt, source metadata, KG concept, and learner response.
- Add quick actions:
  - Explain this sentence
  - Give another example
  - What should I focus on here?
  - Turn this into a practice question

Acceptance:

- Chat answers the selected source/excerpt, not only the broad day topic.
- Private source references are shown safely.

### A5: Quiz and Adaptation Integration

- Quiz uses completed reading units and exercises.
- Adaptation receives weak signals from:
  - reading response quality
  - skipped readings
  - repeated Ask Pathly confusion
  - exercise mistakes

Acceptance:

- Quiz no longer asks about unseen content.
- Adaptation reasons can cite specific source units and concept bridges.

## 13. Comparison Plan

Keep a visible comparison switch during development:

```text
Study Blocks View v1 | Annotated Source View v2
```

Comparison criteria:

| Criterion | v1 Study Blocks | v2 Annotated Source |
|---|---|---|
| Uses uploaded PDFs visibly | weak | strong |
| Shows exact source material | partial | central |
| Makes learner do work | moderate | strong |
| Supports demo narrative | moderate | strong |
| Depends on resource quality | medium | high |
| Works without PDFs | yes | yes, via public/generated source |

## 14. Risks

- Poor PDF parsing can produce weak excerpts. Mitigation: strengthen evidence cleaning and allow public/generated fallback.
- Some PDFs may be research-heavy and not beginner-friendly. Mitigation: annotation explains what to focus on and what to skip.
- Page can become too dense. Mitigation: collapsible reading cards and one active reading at a time.
- Full PDF rendering may be costly. Initial version can show clean excerpts and page metadata before adding embedded PDF viewer.

## 15. Recommended Next Step

Implement A1 first.

Do not touch v1 Today Learning except adding a link or toggle later.

A1 should produce a backend JSON session that can be inspected before building the full UI.

Recommended files:

- New: `pathly_annotated_content.py`
- Update: `pathly_server.py` with v2 endpoints
- New tests: `tests/test_pathly_annotated_content.py`
- Later update: `pathly-app.js` only for the separate v2 page/toggle

## 16. Definition of Done for First Demo Version

A successful v2 demo should show:

1. User uploaded PDFs are visible in daily learning.
2. Pathly chooses specific excerpts/pages for the day.
3. Each excerpt has learner-facing annotation.
4. KG concepts are connected to the excerpt.
5. Exercises are based on the excerpt.
6. Ask Pathly can explain the current excerpt.
7. If no PDFs exist, public/generated source is used with clear labeling.
8. v1 and v2 can be compared side by side or by toggle.
