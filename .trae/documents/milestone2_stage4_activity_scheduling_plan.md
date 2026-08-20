# Milestone 2 Stage 4 — Concept Decomposition and Daily Activity Scheduling Plan

## 1. Background and problem definition

Pathly can now identify common learning goals reliably, but the generated schedule is still sparse. A 7-day or 30-day request can contain only 2–3 non-empty days because the current `TimeAllocator` treats every knowledge-graph topic as one indivisible item. After all topics have been placed, it pads the remaining horizon with zero-minute buffer days.

This is not only a UI problem. The current plan model conflates two different layers:

1. **Concept path**: what knowledge must be learned and in what prerequisite order.
2. **Daily activity plan**: how the learner studies, practises, reviews, assesses, and applies those concepts over time.

Stage 4 will separate these layers. It must not fabricate new KG concepts merely to fill the calendar. Extra days will be made meaningful through evidence-based learning activities linked to real concepts.

## 2. Product outcome

For a requested horizon of 7 or 30 days, Pathly should provide:

- A real prerequisite concept path sourced from Neo4j or the JSON KG fallback.
- At least one meaningful activity on every scheduled learning day.
- No day above the learner's `daily_minutes` limit.
- Concepts divided into learnable blocks instead of indivisible multi-hour topics.
- Worked examples, guided practice, coding labs, spaced review, quizzes, reflection, and project milestones.
- A visible explanation of how foundations, confidence, pace, and preferred learning style changed the activity mix.
- Two feasibility strategies when the requested horizon is longer than the minimum needed:
  - `paced_consolidation`: use the requested horizon for practice, review, assessment, and a through-line project.
  - `early_completion`: recommend a shorter honest completion horizon without artificial padding.

The default Pathly experience will use `paced_consolidation`, while showing the estimated minimum completion duration.

## 3. Architecture change

The Planning pipeline will become:

`Goal interpretation → Topic mapping → Concept path → Concept decomposition → Activity generation → Preference-aware scheduling → Feasibility validation → UI rendering`

### Data sources

- **Neo4j**: primary source for canonical concepts, prerequisites, parts, related topics, difficulty, and learning-time metadata.
- **Calibrated JSON KG**: fallback concept source when Neo4j is unavailable.
- **LearnerProfile SQLite**: foundations, confidence, pace, preferences, known topics, mastery, and time constraints.
- **Deterministic activity templates**: stable fallback for examples, practice, review, quiz, reflection, and project activities.
- **LLM**: may improve wording, objectives, and task descriptions, but may not invent canonical concept IDs or prerequisite relations.

## 4. Target data model

### ConceptPathNode

- `concept_id`
- `title`
- `prerequisite_ids`
- `relationship_source`
- `difficulty`
- `estimated_total_minutes`
- `mastery_before`
- `planning_reason`
- `source_mode`: `neo4j / json`

### LearningActivity

- `activity_id`
- `activity_type`: `concept / worked_example / guided_practice / coding_lab / project / review / quiz / reflection`
- `concept_ids`
- `title`
- `objective`
- `instructions`
- `deliverable`
- `estimated_minutes`
- `difficulty`
- `reason`
- `source_mode`: `template / live / cached`
- `prerequisite_activity_ids`

### DailyPlanV2

- `day`
- `theme`
- `objectives`
- `activities`
- `estimated_minutes`
- `new_concept_minutes`
- `practice_minutes`
- `review_minutes`
- `assessment_minutes`
- `project_minutes`
- `reason`
- `is_milestone`

For backward compatibility, each day will continue returning `focus_topics`, derived from `activities[].concept_ids`.

### Planning output additions

- `schema_version: 2`
- `concept_path`
- `activity_mix`
- `scheduling_strategy`
- `minimum_recommended_days`
- `requested_days`
- `days: DailyPlanV2[]`
- `profile_effects`
- `coverage_warnings`

Existing saved plans remain readable and are not rewritten. New plans use schema version 2.

## 5. Implementation checkpoints

Each checkpoint must update `LOG.md`, report tests and known limitations, and stop for user confirmation.

### Stage 4.1 — Concept decomposition and schema

Goal: produce a concept path and split heavy concepts into bounded learning units without scheduling them yet.

Implementation:

- Add a `ConceptExpander` service.
- Build the concept path from canonical target nodes and prerequisite relationships.
- Include meaningful KG child/part/related nodes only when supported by explicit graph relationships.
- Deduplicate aliases and repeated nodes.
- Keep the core target as the final anchor of the concept path.
- Convert each concept's estimated time into 15–30 minute conceptual units.
- Add schema-versioned `concept_path` and activity-ready units to Planning output.
- Emit `coverage_warnings` when the KG is too sparse; never invent fake concept nodes.

Acceptance:

- Machine Learning and Transformer produce an ordered, duplicate-free concept path.
- RAG uses real Neo4j RAG/retrieval nodes when available.
- No unit exceeds the learner's daily limit.
- Sparse KG coverage is visible as a warning rather than hidden.
- Existing v1 plans continue to load.

### Stage 4.2 — Activity generation and preference mix

Goal: turn concept units into meaningful learning activities.

Implementation:

- Add an `ActivityPlanner` with deterministic templates.
- Generate concept explanation, worked example, guided practice, coding lab, project, review, quiz, and reflection activities.
- Require every activity to reference at least one real concept ID.
- Generate a through-line project for project-oriented learners.
- Apply target activity mixes:
  - Project preference: 30% concept, 40% practice/project, 15% review, 10% quiz, 5% reflection.
  - Mathematical preference: 45% theory, 25% derivation, 15% practice, 10% quiz, 5% reflection.
  - Intuitive preference: 40% concept/analogy, 25% worked examples, 20% practice, 10% quiz, 5% reflection.
- Record applied ratios and deviations in `activity_mix` and `profile_effects`.
- Allow an LLM to improve wording only after deterministic activity structure exists.

Acceptance:

- Changing learner preference changes activity types and minute ratios while preserving the concept path.
- Every activity has an objective, duration, concept link, reason, and expected deliverable where relevant.
- LLM failure still produces a complete, explicitly labelled template-based activity plan.

### Stage 4.3 — Horizon-aware scheduler

Goal: distribute activities across all requested days without empty padding or daily overload.

Implementation:

- Refactor `TimeAllocator` into an activity-level scheduler.
- Split activities when they exceed the daily budget.
- Preserve prerequisite order for new-concept activities.
- Schedule reviews using approximate spaced intervals of +1, +3, +7, and +14 days where the horizon permits.
- Place formative quizzes after concept clusters and cumulative quizzes at milestones.
- Divide projects into proposal, setup, implementation, evaluation, and reflection milestones.
- Guarantee `sum(activity.estimated_minutes) <= daily_minutes` for every day.
- Guarantee at least one meaningful activity on every scheduled day in `paced_consolidation` mode.
- Calculate `minimum_recommended_days` independently of requested horizon.
- If requested capacity is insufficient, return an explicit overload warning and unscheduled activities; never silently drop them.
- If requested capacity is excessive, use consolidation activities or offer `early_completion`; never create zero-minute buffer days.

Acceptance:

- 7-day plans contain 7 meaningful days.
- 30-day plans contain 30 meaningful days in `paced_consolidation` mode.
- No day exceeds the daily limit.
- Review activities refer to concepts introduced on earlier days.
- Quiz and project prerequisites occur before assessment milestones.
- Re-running the same input produces a deterministic schedule when live generation is disabled.

### Stage 4.4 — Pathly visualization and final acceptance

Goal: clearly present both the concept relationship and the complete daily journey.

Implementation:

- Keep the knowledge-map view for `concept_path` only.
- Render all `DailyPlanV2` days in the timeline, including activity chips and minute totals.
- Add filters for concepts, practice, review, quiz, and project.
- Show activity-mix visualization and profile-effect explanations.
- Show requested duration versus minimum recommended duration.
- Allow the learner to switch between paced consolidation and early completion before saving the plan.
- Preserve selected strategy and generated schedule after refresh.
- Ensure narrow screens use a vertical daily timeline.

Acceptance:

- The map does not duplicate a concept merely because it appears in multiple activities.
- The timeline shows every requested day and makes review/project days visibly meaningful.
- Strategy changes produce a new independent plan draft and do not overwrite an accepted path.
- Refresh restores the chosen path, strategy, activity data, and current view.

## 6. End-to-end acceptance cases

### Case A — 7-day Machine Learning

- Input: Machine Learning, 7 days, 90 minutes/day.
- Exactly 7 non-empty days.
- Every day is at most 90 minutes.
- Includes concept learning, at least two practices, one review, one quiz, and one application milestone.
- Concept nodes remain canonical KG nodes.

### Case B — 30-day RAG with project preference

- Input: RAG, 30 days, 60 minutes/day, project practice preference.
- Exactly 30 non-empty days in paced-consolidation mode.
- Every day is at most 60 minutes.
- Uses real RAG/retrieval concepts from Neo4j.
- Contains at least three guided/coding practices, three quizzes, spaced reviews, and a through-line RAG project with at least five milestones.
- Practice/project minutes are the largest activity category.
- No `Reserved for review, rest, or buffer` zero-minute days.
- If KG coverage is insufficient, the UI shows a coverage warning without inventing nodes.

### Case C — Insufficient capacity

- Input requires more time than `requested_days × daily_minutes`.
- No day exceeds the limit.
- Remaining activities are listed as unscheduled with a feasibility explanation.
- UI offers to extend the horizon or reduce scope.

### Case D — Excess capacity

- Minimum plan is shorter than requested horizon.
- UI shows both the honest minimum and requested duration.
- Paced consolidation fills the requested horizon with meaningful linked activities.
- Early completion uses fewer days and does not create padding.

## 7. Test strategy

- Unit tests for concept expansion, deduplication, canonical IDs, and sparse-KG warnings.
- Unit tests for activity template generation and preference ratios.
- Unit tests for activity splitting, prerequisite order, spaced review, quiz placement, project milestones, and capacity constraints.
- Property-style tests: no day over budget, no empty day in paced mode, every activity linked to a concept, deterministic fallback output.
- Planning Agent integration tests for Neo4j and JSON fallback.
- API persistence tests for schema version 2 and strategy selection.
- Frontend tests for map/timeline separation, all-day rendering, strategy switching, and refresh recovery.
- Failure tests for Neo4j, JSON KG, and LLM unavailability.

## 8. Scope boundaries

Included:

- Planning output through daily activity scheduling and its visualization.
- Stable activity descriptions sufficient to explain and inspect the plan.

Not included yet:

- Full Content Agent lecture generation.
- Resource retrieval and recommendation.
- Daily Chat, Quiz attempts, and Adaptation decisions.
- Automatic modification of an accepted path.

These later systems will consume `DailyPlanV2.activities` rather than recreate scheduling logic.

## 9. Recommended implementation order

1. Stage 4.1: schema and concept decomposition.
2. Stop for user confirmation.
3. Stage 4.2: activity generation and preference mix.
4. Stop for user confirmation.
5. Stage 4.3: scheduling and feasibility strategies.
6. Stop for user confirmation.
7. Stage 4.4: Pathly visualization and end-to-end acceptance.
8. Stop for final Stage 4 confirmation before continuing to Content Agent work.

## 10. Capacity-first revision — 2026-07-24

The requested duration is user-defined and may be any supported value from 1 to 90 days. Scheduling must not use a fixed 7/14/30-day assumption.

The calculation order is:

1. Estimate the source-grounded total required minutes from the goal and learner profile.
2. Add concept learning, practice, review, assessment, reflection, and project workload.
3. Calculate recommended_daily_minutes = ceil(total_required_minutes / requested_days).
4. Compare it with the learner's maximum available daily minutes.
5. If capacity is insufficient, report the exact minute gap and offer more days, more daily time, or reduced scope.
6. If capacity is excessive, offer paced consolidation or honest early completion.

For example, a 1,000-minute goal requested in 10 days requires an average of 100 minutes per day. A learner with only 60 available minutes per day has a 400-minute capacity shortfall; Pathly must not silently remove content.

The future Onboarding order should be:

goal and current foundation → preliminary workload estimate → desired days/deadline → recommended daily time → daily availability → feasibility confirmation.

Stage 4.1 returns a provisional concept-only estimate marked is_final=false. Stage 4.2 adds practice, review, quiz, reflection, and project minutes and marks the total estimate final. The Onboarding UI will be changed only after that final workload model is stable.