# Pathly Implementation Log

## 2026-08-18 Self-Attention gold-source pilot v1

- Added two validated public source PDFs under `D:\\ic\\master project\\gold source\\self_attention`: Stanford CS224N Lecture 5 for foundational treatment and *Attention Is All You Need* for advanced treatment.
- Published 2 tiered source records, 16 evidence-linked teaching assets, 85 page chunks to Chroma, and a scoped Self-Attention manifest.
- Added 4 Self-Attention canonical concepts, 3 prerequisite edges, and 2 Neo4j Resource bindings through the scoped graph import.
- Runtime source resolution now accepts a learner tier and selects the corresponding document/page sequence; existing shared/legacy resolution remains compatible.
- Verification: PDF extraction and SHA-256 checks passed; tier resolver returned Stanford page 42 for Foundation Q/K/V and Vaswani page 4 for Advanced Q/K/V; 89 targeted tests passed, including the new gold-source resolver checks.

## 2026-08-18 Controlled Evaluation audit-history layout

- Replaced the reused library-card grid with a purpose-built compact run list.
- Each row now separates system version, full goal, status/generation mode, run ID, and local timestamp.
- The page shows the latest 12 artifacts for readability; **Export JSON** continues to include the complete history.
- Verified with `node --check pathly-app.js` and the Pathly frontend regression suite: 58 passed.

The pre-R0 historical log is preserved unchanged at
`documents/LOG_ARCHIVE_PRE_R0_2026-07-28.md`. This file is the authoritative,
UTF-8 implementation status from R0 onward.

## Product boundary

Pathly is the learner-facing product. The Streamlit service on port 8501 is the
separate administrator workspace for public KG and RAG construction. Pathly
owns onboarding, private documents, learner profiles, planning, scheduling,
daily learning, assessment, and learner-confirmed adaptation.

## Completed foundation

| Stage | Result |
|---|---|
| O1 Private PDF ingestion | Internally accepted |
| O2 Goal interpretation and private concept overlay | Internally accepted |
| O3 Cognitive and affective learner profile | Internally accepted |
| O4 Duration-independent workload estimate | Internally accepted |
| O5 Capacity negotiation and plan v1 | Internally accepted |
| O6 Activity scheduling and plan v2 | Internally accepted |
| O7 Real onboarding workspace and dashboard | Internally accepted; manual visual checks performed iteratively |
| O8 Anonymous security, fallbacks, deployment contract | Internally accepted; Docker runtime build still pending |

Recent UI fixes include multi-PDF upload, incremental repeat onboarding,
recoverable errors, fixed notifications, explicit strategy confirmation,
clickable onboarding steps, selected view states, and removal of private hash
labels from the knowledge map and activity timeline. The final pre-R0 regression
was 103 passed with two third-party deprecation warnings.

## R0 Formal product closure

- Status: internal acceptance passed.
- Started: 2026-07-28 Asia/Shanghai.
- Completed: 2026-07-28 Asia/Shanghai.
- Result: secure defaults enabled, demo semantics and legacy public assets removed, implementation documentation normalized, and the R0 quality gate passed.

## Planned next stages

- R1: hybrid calendar, daily content, RAG, and resource recommendations.
- R2: contextual chat, feedback, and confusion aggregation.
- R3: quiz, learning sessions, and unlock state.
- R4: adaptation proposals and plan v3+.
- R5: deployment and final end-to-end acceptance.

## R0 Internal acceptance - 2026-07-28

- Status: internal acceptance passed; continuous implementation authorization applies.
- Removed demo-mode runtime behavior and capability output.
- Product mode now defaults to anonymous session authorization; tests use an explicit compatibility flag.
- Local launcher enforces session ownership with a non-Secure localhost cookie; Docker keeps Secure cookies.
- Legacy `/app.js` and `/styles.css` now return 404.
- Archived the pre-R0 log without modification and rebuilt UTF-8 status, runbook, and privacy documentation.
- Syntax checks passed.
- R0 focused suite: 37 passed, 1 third-party warning.
- Full regression: 104 passed, 2 third-party warnings.
- Real 4173: ready=true, session required=true, demo field absent, anonymous session 201, unauthenticated private API 401, legacy asset 404.
- Real cross-session ownership: owner profile created; second anonymous session received 403.
- Docker runtime build remains assigned to R5 because Docker is unavailable on this host.

## R1 Hybrid calendar and daily content

- Status: implementation and internal automated acceptance passed; awaiting user visual acceptance.
- Started: 2026-07-28 Asia/Shanghai.
- Acceptance candidate completed: 2026-07-28 Asia/Shanghai.

### Implemented

- Added `path_runtime`, `path_day_dates`, and `daily_contents` SQLite storage.
- A scheduled plan can be activated with a start date and IANA timezone; Day N maps to `start_date + N - 1`.
- Today resolution returns the earliest due learning day, or the next scheduled day when none is due.
- Moving a day shifts that day and every later day by the same delta, preserving review spacing.
- A shift beyond the confirmed deadline returns a preview and persists nothing until explicit confirmation.
- Content Agent inputs include plan version, scheduled activities, current learner profile, KG context, public RAG, and linked private document chunks.
- KG retrieval attempts Neo4j first and transparently falls back to calibrated JSON.
- Lesson output includes objectives, structured sections, explanations, examples, applications, summary, citations, retrieval counts, generation mode, and fallback reason.
- Resource recommendations reuse the existing recommendation service and expose source, difficulty, duration, and learner-fit reason.
- Cache identity includes plan, day, current profile version, and retrieved source context. Profile or source changes invalidate the cached lesson; refresh does not repeat the model call when the identity is unchanged.
- The learner UI now includes `Today Learning`, a Dashboard continuation action, daily lesson rendering, recommendations, citations, mode/cache labels, and an in-page deadline impact confirmation.
- The v26 UI is responsive; narrow screens use a single-column daily learning layout.
- Private concept hashes are converted to neutral display names before they reach lesson titles.

### Public APIs

- `POST /api/plans/{plan_id}/activate`
- `GET /api/paths/{path_id}/today`
- `POST /api/paths/{path_id}/days/{day}/reschedule`
- `GET|POST /api/plans/{plan_id}/days/{day}/content`
- `GET /api/plans/{plan_id}/days/{day}/resources`

### Verification

- Python and JavaScript syntax checks passed.
- R1 focused suite: 6 passed.
- R1 API/frontend/server suite: 38 passed.
- Full regression after final cache correction: 112 passed, 2 third-party deprecation warnings.
- Real 4173 formal mode: ready=true, session required=true, daily learning available=true, v26 assets served.
- Real anonymous-session boundary: authenticated private API returned 200; the same URL without its cookie returned 401.
- Real Content Agent request: generation mode `live`, 3 lesson sections, public RAG chunks=3, citations=3, first request cache miss and second request cache hit.
- The real KG request returned calibrated JSON context when Neo4j did not supply a matching concept; the source was labelled `json`.
- Deterministic model-failure fallback passed automated verification and exposes `fallback` plus its reason.
- The temporary live acceptance plan, runtime rows, dates, and content cache were removed after verification.

### Known acceptance boundary

- Chat, feedback aggregation, Quiz, learning-session completion state, and Adaptation are intentionally not exposed in this candidate.
- Because completion state belongs to R3, the current Today selector cannot yet skip a day marked complete; it resolves the earliest due/next scheduled day. Completed-day locking will be introduced with the real learning-session state.
- Automated in-app browser screenshot validation was blocked by host error `CreateProcessWithLogonW 1385`. Static responsive assertions passed, and v26 is running at 4173 for user visual acceptance.
- Docker runtime build remains assigned to R5 because Docker is unavailable on this host.

## R2 Contextual chat and learning feedback

- Status: implementation passed automated acceptance; bundled with R3 for the next user validation point.
- Started: 2026-07-28 Asia/Shanghai.
- Completed: 2026-07-28 Asia/Shanghai.

### Implemented

- Added persistent chat, daily feedback, and confusion-signal storage.
- Daily chat is scoped to the active plan, selected day, learner profile, lesson content, plan context, and retrieved citations.
- Chat stores role, mode, citations, concept IDs, latency, and timestamps; structured service logs do not need to store full message bodies.
- OpenAI chat generation is attempted when configured; deterministic lesson-grounded fallback is used when the model is unavailable.
- Feedback actions include not understood, too hard, too easy, need example, review later, and content progress.
- Repeated confusion aggregation combines hard feedback and learner questions for later quiz/adaptation use.
- The Today Learning UI includes a contextual Q&A stage with quick prompts and visible live/fallback mode labels.

### Public APIs

- `POST /api/plans/{plan_id}/days/{day}/feedback`
- `GET /api/plans/{plan_id}/days/{day}/chat`
- `POST /api/chat`
- `GET /api/paths/{path_id}/confusions`

### Verification

- R3 learning-loop suite includes R2 checks: fallback chat returns cited answers, and repeated confusion signals are persisted and aggregated.
- Focused R2/R3 backend and frontend suite: 31 passed, 1 third-party deprecation warning.
- Full regression after R2/R3 completion: 117 passed, 2 third-party deprecation warnings.

## R3 Quiz, learning state, and Activity Timeline unlock

- Status: implementation passed automated acceptance; awaiting user validation.
- Started: 2026-07-28 Asia/Shanghai.
- Completed: 2026-07-28 Asia/Shanghai.

### Implemented

- Added persistent learning-day progress, stable daily quizzes, and quiz attempts.
- Day access is sequential: Day 1 starts unlocked; Day N is locked until Day N-1 is completed.
- Opening an unlocked learning day writes an `in_progress` record. Starting an already completed day no longer overwrites completion.
- Quiz generation is cached by day content source hash, so refresh does not change the questions.
- Public quiz API removes `correct_answer` and `expected_terms`; grading remains server-side.
- Quiz attempts record answer, correctness, explanation, confidence, time, score, weak concepts, and strong mastery signal.
- Completing a quiz marks the day completed, records actual minutes, and returns the updated `path_progress` payload.
- Activity Timeline now consumes `path_progress` and shows locked, unlocked, in progress, and completed states.
- Every unlocked or completed day in Activity Timeline has an entry button. Locked days show the previous day required.
- Quiz result UI shows the next unlocked day entry and a button back to the updated Activity Timeline.
- Completed learning days are read-only in the UI; chat, feedback, and quiz mutation controls are disabled for completed days.
- R4 Adaptation APIs remain in backend groundwork, but the user-facing Adaptation stage is not exposed as completed R3 functionality.

### Public APIs

- `GET /api/paths/{path_id}/progress`
- `POST /api/plans/{plan_id}/days/{day}/start`
- `GET /api/plans/{plan_id}/days/{day}/quiz`
- `POST /api/plans/{plan_id}/days/{day}/quiz-attempts`

### Verification

- JavaScript syntax: passed with `node --check pathly-app.js`.
- Python syntax: passed with `py_compile pathly_server.py pathly_learning_loop.py`.
- R3 learning-loop suite: 5 passed, 1 third-party deprecation warning.
- Frontend v2 suite: 26 passed, 1 third-party deprecation warning.
- Focused R1-R3 plus security regression: 41 passed, 1 third-party deprecation warning.
- Full regression: 117 passed, 2 third-party deprecation warnings.
- The R3 API test verifies that Day 2 cannot start before Day 1 completion, public quiz payloads do not expose answers, quiz submission unlocks Day 2 in `path_progress`, and Day 2 can then enter `in_progress`.

### Known acceptance boundary

- R4 learner-confirmed Adaptation is not part of this validation stop. Weak concepts and strong mastery signals are stored now so R4 can consume them after user acceptance.
- Docker runtime build remains assigned to R5 because Docker availability has not been confirmed on this host.

## R3 UI follow-up - Ask Pathly sidebar

- Status: completed; awaiting user visual validation with the rest of R3.
- Completed: 2026-07-28 Asia/Shanghai.

### Implemented

- Moved `Ask Pathly` out of the Today Learning stage tabs and into the `Lesson & Resources` right sidebar.
- Kept Today Learning tabs focused on `Lesson & Resources` and `Daily Quiz`.
- Moved resource recommendations from the first right-sidebar slot into a main-column `Recommended Resources` section below the lesson.
- Kept the schedule/reschedule panel in the sidebar below Ask Pathly.
- Completed days remain read-only: prior messages can be reviewed, but new chat input and quick prompts are hidden.
- Bumped frontend asset references to v28 to avoid stale browser cache.

### Verification

- JavaScript syntax check passed with `node --check pathly-app.js`.
- Frontend v2 suite: 26 passed, 1 third-party deprecation warning.
- Final full regression after v28 asset bump: 117 passed, 2 third-party deprecation warnings.

## R3 UI follow-up - Ask Pathly compose restored

- Status: completed; awaiting user visual validation.
- Completed: 2026-07-28 Asia/Shanghai.

### Implemented

- Restored the Ask Pathly quick prompts and message input inside the Lesson & Resources sidebar.
- Review of a completed day still keeps lesson feedback and quiz mutation read-only, but learners can ask follow-up questions while reviewing the lesson.
- Bumped frontend asset references to v29 to avoid stale browser cache.

### Verification

- JavaScript syntax check passed with `node --check pathly-app.js`.
- Focused frontend/R3 suite: 31 passed, 1 third-party deprecation warning.
- Full regression: 117 passed, 2 third-party deprecation warnings.
- Running service references `pathly-app.js?v=29` and serves the asset with HTTP 200.

## R3 UI follow-up - Busy loading keeps navigation

- Status: completed; awaiting user visual validation.
- Completed: 2026-07-28 Asia/Shanghai.

### Implemented

- Changed global busy loading from a full-screen replacement to an in-shell loading section.
- Sidebar navigation, privacy note, header, and dismissable notices remain visible while My Library or other async actions are loading.
- Users can navigate away instead of being trapped on the loading state.
- Bumped frontend asset references to v30 to avoid stale browser cache.

### Verification

- JavaScript syntax check passed with `node --check pathly-app.js`.
- Added frontend regression test `test_busy_loading_preserves_navigation_shell`.
- Frontend v2 suite: 27 passed, 1 third-party deprecation warning.
- Full regression: 118 passed, 2 third-party deprecation warnings.
- Running service references `pathly-app.js?v=30` and serves the asset with HTTP 200.


## C1-C5 Content Agent v2 - executable daily learning session

- Status: internal acceptance passed; awaiting user visual acceptance.
- Started: 2026-07-28 Asia/Shanghai.
- Completed: 2026-07-28 14:32:59 +08:00.
- Frontend asset version: v31.

### C1 - contract and evidence preparation

- Added `daily-content-v2` and `content-agent-v2` to the daily content source hash so old short-lesson cache entries cannot masquerade as the new contract.
- Added a bounded Evidence Preparation layer that deduplicates chunks and removes emails, DOI text, author/affiliation lines, headers, copyright text, and reference sections before teaching use.
- Separated teaching-safe evidence from provenance-only citations. Low-quality chunks remain traceable but report `used_in_teaching=false` and do not increase RAG teaching counts.
- Added the complete Content Agent input context: learner/profile version, path/plan, scheduled day activities, concept path, KG context, clean evidence, resources, and persisted prior learning signals.
- Preserved legacy `lesson` output as a compatibility projection while all new generation uses the v2 session contract.

### C2 - session planner and complete fallback

- Added deterministic activity-to-block mapping for explanation, example, required reading, practice, code, review, quiz preparation, project, reflection, and optional activities.
- Every scheduled activity keeps its stable activity ID and receives a study block.
- Required block minutes are validated against required scheduled activity minutes; the session total is validated against the O6 day total.
- Replaced the old raw-chunk fallback example with complete block-specific teaching structures: mental models, worked steps, guided reading, practice/code scaffolding, retrieval review, quiz readiness, project milestones, and reflection.
- Private concept IDs continue to use display labels rather than appearing as learner-facing titles.

### C3 - live block generation and partial fallback

- Replaced the one-shot concise lesson prompt with block-level OpenAI generation proportional to scheduled minutes.
- Each block receives only clean relevant evidence and strict no-invented-source/page/URL constraints.
- Invalid JSON or a failed block keeps that block's deterministic fallback while other blocks can remain live.
- Added per-block generation mode and fallback reason plus block-level regeneration API.
- Actual OpenAI network generation was not executed in this acceptance run; live-path structure is covered with injected model tests, while deterministic fallback is executed end to end.

### C4 - Today Learning executable session UI

- Replaced the short continuous lesson view with an expandable Study Block timeline.
- Added session overview, objectives, personalization reason, total planned minutes, completed-block progress, and fallback/source status.
- Added block-specific rendering for concept teaching, worked examples, guided reading, practice/code, review, quiz preparation, projects, and reflection.
- Required resources now appear inside the linked learning block with reading scope, focus questions, clean excerpt, and after-reading task.
- Optional resources are clearly separated and excluded from required progress.
- Added sequential block availability, completion controls, persisted recovery, actual block time, feedback controls, and a disabled Quiz action until all required blocks are complete.
- Ask Pathly remains in the sidebar and displays/receives the current block context.
- Added responsive vertical session layout for narrow screens.

### C5 - learning loop linkage

- Chat now receives content ID, current block, completed block IDs, and current resource context.
- Quiz v2 is derived from completed study blocks and is unavailable until every required block is completed.
- Block feedback maps back to concept IDs and existing confusion/adaptation signals.
- Study block progress synchronizes to daily `content_progress` and actual minutes.
- Activity Timeline shows daily session completion percentage and retains entry buttons for every unlocked/completed day.
- Daily Quiz completion still unlocks the next day; completed days remain reviewable and read-only for learning progress.

### Public APIs added

- `GET /api/plans/{plan_id}/days/{day}/session`
- `PATCH /api/plans/{plan_id}/days/{day}/blocks/{block_id}/progress`
- `POST /api/plans/{plan_id}/days/{day}/blocks/{block_id}/complete`
- `POST /api/plans/{plan_id}/days/{day}/blocks/{block_id}/feedback`
- `POST /api/plans/{plan_id}/days/{day}/blocks/{block_id}/regenerate`
- `GET /api/resources/{resource_id}/reading-context`

### SQLite migrations

- `daily_sessions`
- `daily_study_blocks`
- `study_block_progress`
- `prepared_evidence`
- `resource_interactions`

All migrations are additive and preserve existing daily content, plans, sessions, Quiz attempts, and path versions.

### Verification

- Python syntax checks passed for `pathly_daily.py`, `pathly_learning_loop.py`, and `pathly_server.py`.
- JavaScript syntax passed with `node --check pathly-app.js`.
- Content Agent/Learning Loop focused suite: 15 passed, 1 third-party deprecation warning.
- Content Agent/frontend focused suite: 37 passed, 1 third-party deprecation warning.
- Final full regression: 122 passed, 2 third-party deprecation warnings.
- Running service: HTTP 200, `daily-content-v2` capability present, v31 assets loaded, and new block/session routes present in OpenAPI.
- The automated in-app visual pass could not run because the browser-control runtime failed to start on this Windows host with `CreateProcessWithLogonW failed: 1385`. No visual click result is claimed. User visual acceptance remains required.

### Known limitations

- Live OpenAI block generation still depends on server-side credentials and provider availability; this run validates its contract with injected generation and validates fallback end to end.
- The guided reading experience currently uses an inline clean excerpt and reading scope. A full paginated PDF viewer is not added in this stage.
- Resource interaction storage exists, but optional resource click analytics are not yet surfaced as a product report.
- R4 Adaptation decision logic was not redesigned in this Content Agent stage; it can consume the new feedback, confusion, Quiz, progress, and actual-time signals.

## Content quality hotfix - student-facing teaching material (2026-07-28)

Status: internally verified; pending user visual acceptance.

### Root cause

- Incomplete learning days could keep displaying a legacy v1 lesson upgraded only at the schema level. The page therefore showed deterministic scaffolding such as “place the concept…” and “complete the scheduled practice” instead of newly generated teaching content.
- The first v3 quality gate rejected otherwise usable live model output when it narrowly missed a word-count target, causing the whole block to fall back to the thin deterministic template.
- The model prompt previously received filled fallback prose as its shape example, which encouraged it to repeat the scaffolding.

### Changes

- `content-agent-v3` now invalidates and regenerates unfinished sessions generated by an older generator version; completed days preserve their historical content.
- Model requests receive a type-only output schema, not fallback prose.
- The prompt explicitly requires finished learner-facing teaching, current-topic relevance, multiple explanatory sections, a mental model, misconception correction, and a meaningful checkpoint.
- Added per-block quality and relevance validation.
- Added a bounded 2,500-token output budget, 75-second per-request timeout, and no SDK retry loop; Pathly retains its explicit one-time quality-repair attempt.
- The quality gate now uses a practical hard floor while the prompt still requests material sized for the scheduled block. Blocks expose `generation_mode`, `fallback_reason`, and diagnostic detail.
- Unfinished old sessions regenerate automatically because the generator version is part of the source hash. No manual database deletion is required.

### Actual verification

- Focused Content Agent / learning-loop / frontend suite: `42 passed, 1 warning`.
- Full regression suite: `122 passed, 2 warnings`.
- Real configured OpenAI call for a 29-minute Computational Linguistics concept block:
  - result mode: `live`
  - elapsed time: approximately 36 seconds
  - core teaching body: 371 words
  - plain explanation: 78 words
  - detailed subsections: 4
  - misconception corrections: 1
  - fallback reason: none
  - content explicitly taught Computational Linguistics and connected it to language understanding applications.

### Known limitation / acceptance

- Browser-control automation remains unavailable in this Windows environment (`CreateProcessWithLogonW 1385`), so the final visual check must be performed by the user after refresh.
- Live generation latency varies by model/network. The request is bounded and falls back explicitly if generation or validation fails.

### Running service check

- Restarted the local Pathly service on `http://127.0.0.1:4173/` after the content-quality hotfix.
- `GET /api/health`: HTTP 200, service ready, anonymous sessions required, SQLite/KG JSON/Chroma/private documents/daily learning available.
- `GET /api/capabilities`: HTTP 200, `daily_learning.content_contract=daily-content-v2`, `content_generation=two_stage_block_generation_with_deterministic_fallback`, `learning_loop.stable_daily_quiz=true`.
- `GET /`: HTTP 200 and serves the current Pathly app shell.

## Content length and chat responsiveness hotfix (2026-07-28)

Status: internally verified; pending user visual acceptance.

### Problem

- User reported that daily learning content still felt too short for real study.
- User reported Ask Pathly felt laggy and sometimes appeared unresponsive after clicking.

### Changes

- Bumped Content Agent generator version to `content-agent-v4`, forcing unfinished old daily sessions to regenerate instead of reusing thin cached content.
- Increased live block generation budget from a fixed 2,500 tokens to a block-size-aware budget of 3,200-6,500 tokens.
- Increased concept lesson target depth while bounding it to avoid runaway generation.
- Added OpenAI chat timeout, disabled SDK retries for chat, and capped chat output to keep sidebar answers responsive.
- Changed Ask Pathly frontend from global `act()` loading to local optimistic chat state:
  - user message appears immediately;
  - sidebar shows a pending assistant message;
  - buttons show `Sending...` locally;
  - errors stay inside the chat panel instead of taking over the page.
- Bumped frontend assets to `v32` and cleaned one mojibake label in the Quiz confidence control.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Python syntax: `py_compile` for `pathly_daily.py`, `pathly_learning_loop.py`, and `pathly_server.py` passed.
- Focused regression: `42 passed, 1 warning`.
- Full regression: `122 passed, 2 warnings`.
- Restarted local Pathly service on `http://127.0.0.1:4173/`.
- `GET /api/capabilities`: HTTP 200; daily content contract is `daily-content-v2`; contextual chat and stable daily quiz are enabled.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=32` plus `pathly-ui.css?v=32`.

### Known limitation

- Existing completed learning days remain read-only and are not regenerated. To see thicker `content-agent-v4` content, open an unfinished day or create a new path/day.
- Browser-control automation is still unavailable in this Windows environment, so final visual acceptance must be performed manually in the browser.

## Mojibake cleanup in daily learning UI (2026-07-28)

Status: internally verified; pending user visual acceptance.

### Problem

- Daily Learning displayed broken punctuation such as `?` in `today?s`, `blocks ? days`, and generated fallback copy.

### Changes

- Replaced corrupted `today?s` / `Today?s` template text with normal English apostrophes in `pathly_daily.py`.
- Replaced the Daily Learning header separator from `?` to `/` in `pathly-app.js`.
- Bumped Content Agent generator to `content-agent-v5` so unfinished sessions regenerate without the corrupted template text.
- Bumped frontend assets to `v33`.

### Verification

- Mojibake scan for `today?s`, `Today?s`, `blocks ?`, `鈥`, `鈫`, and replacement characters returned no matches in the main learner-facing files.
- JavaScript syntax check passed.
- Python syntax check passed.
- Focused regression: `37 passed, 1 warning`.
- Full regression: `122 passed, 2 warnings`.
- Restarted local Pathly service and confirmed `/` returns `pathly-app.js?v=33` and `pathly-ui.css?v=33`.

## False completed block isolation fix (2026-07-28)

Status: internally verified; pending user visual acceptance.

### Problem

- A newly opened learning day could appear partially completed on first entry.
- Root cause: study block IDs used only day and sequence, such as `block-day3-01`, so regenerated or newly created content for the same plan/day could inherit old block progress records.

### Changes

- Changed block ID generation to include a stable hash of path ID, plan ID, day, activity ID/type, and sequence.
- Updated required-resource block links to use the same block ID helper.
- Bumped Content Agent generator to `content-agent-v6` so unfinished sessions regenerate with isolated block IDs.
- Replaced completed block sequence display from `?` to a checkmark entity and fixed `I didn't understand` text.
- Bumped frontend assets to `v34`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Python syntax: `py_compile` for `pathly_daily.py`, `pathly_server.py`, and `pathly_learning_loop.py` passed.
- Focused regression: `42 passed, 1 warning`.
- Full regression: `122 passed, 2 warnings`.
- Restarted local Pathly service on `http://127.0.0.1:4173/`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=34` plus `pathly-ui.css?v=34`.
- `GET /api/capabilities`: HTTP 200; daily content contract is `daily-content-v2` and contextual chat is enabled.

## Content Agent learner-session scaffolding fix (2026-07-29)

Status: internally verified; pending user visual acceptance.

### Problem

- Daily Learning content was still too close to a teacher-facing outline. Blocks described what should happen, but did not consistently make the learner produce an answer or work through a concrete learning action on the page.
- The `Need another example` feedback button only saved a signal; it did not immediately help the learner continue studying.

### Changes

- Bumped Content Agent generator version to `content-agent-v7`, so unfinished sessions regenerate with the new learner-session scaffold.
- Upgraded deterministic fallback block content with explicit learner-facing structures:
  - concept lessons now include intuition, mechanism, concrete example, boundary, misconception, mini task, and self-check;
  - required reading now includes why to read, what to look for, cleaned excerpt, and an after-reading learner task;
  - practice/code/review/quiz/project/reflection blocks now include `learner_task` prompts.
- Updated live Content Agent prompt rules so generated blocks must include concrete learner actions where the schema supports them and must not return teacher-facing instructions.
- Updated Today Learning UI:
  - renders `learning_flow` as visible teaching steps;
  - renders a `Your response` textarea for block mini tasks / learner tasks / checkpoints;
  - requires a short response before completing blocks that have a learner task;
  - sends the learner answer to the existing block completion API and persists it in SQLite progress;
  - makes `Need another example` save feedback and immediately ask Pathly for a concrete example in the chat sidebar.
- Bumped frontend assets to `v35`.

### API and data changes

- No new public endpoint was added.
- Existing `POST /api/plans/{plan_id}/days/{day}/blocks/{block_id}/complete` now receives the frontend-provided `answer` field in normal use.
- Existing `study_block_progress.answer_json` persists the learner's block response.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Python syntax: `py_compile` for `pathly_daily.py`, `pathly_server.py`, and `pathly_learning_loop.py` passed.
- Focused Content/Frontend regression: `39 passed, 1 warning`.
- Full regression: `124 passed, 2 warnings`.
- Restarted local Pathly service on `http://127.0.0.1:4173/`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=35`.
- `GET /api/health`: HTTP 200.

### Known limitation

- This is still a scaffold-level improvement. It makes the page more study-action-oriented and prevents empty completion, but truly high-quality subject teaching still depends on better KG/RAG evidence quality and stronger live generation outputs.
- Completed days remain read-only and are not regenerated. To see `content-agent-v7`, open an unfinished day or create a new path/day.


## Capacity time-allocation preview fix (2026-07-29)

Status: internally verified; pending user visual acceptance.

### Problem

- On the Create Path / Capacity confirmation step, selecting `paced_consolidation` showed the same allocation before and after confirmation, for example `10 days / 60 minutes/day` in both places.
- This was misleading because paced consolidation does not change the core required average; it uses surplus capacity for optional reinforcement during scheduling.
- Frontend strategy cards only passed `suggested_days` and `required_daily_minutes`, so the confirmation UI lost the richer strategy metadata needed to explain time allocation.

### Changes

- Updated strategy cards to pass the full selected strategy object to the local confirmation preview.
- Added readable strategy labels:
  - `paced_consolidation` -> `Paced consolidation`
  - `early_completion` -> `Early completion`
  - `proceed` -> `Keep current plan`
- Rewrote the confirmation preview to separate:
  - core required workload;
  - recommended daily average;
  - total available capacity;
  - surplus capacity;
  - optional consolidation usage.
- `paced_consolidation` now explains that the required workload stays unchanged and surplus may be used for optional review/practice/reinforcement within the daily cap.
- `early_completion` now shows the shorter suggested horizon, approximate daily work, and freed days.
- `proceed` now explains that surplus capacity remains unused instead of becoming optional consolidation work.
- Backend feasibility options now include explicit time-allocation metadata for comfortable plans:
  - `required_daily_minutes`
  - `daily_capacity_minutes`
  - `horizon_days`
  - `optional_consolidation_budget_minutes`
  - `freed_days`
  - `unused_capacity_minutes`
- Bumped frontend assets to `v36`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Python syntax: `py_compile` for `pathly_feasibility.py` and `pathly_server.py` passed.
- Focused frontend/feasibility regression: `40 passed, 1 warning`.
- Full regression: `125 passed, 2 warnings`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=36` plus `pathly-ui.css?v=36`.
- `GET /pathly-app.js?v=36`: HTTP 200.

### Known limitation

- This fix clarifies the capacity-decision preview. The actual optional consolidation activities are still created later by the scheduler after the strategy is confirmed.


## Knowledge Map first-node clipping fix (2026-07-29)

Status: internally verified; pending user visual acceptance.

### Problem

- In Knowledge Map view, the first concept card was often partially hidden on the left side of the map container.
- Root cause: the horizontal flex map used `justify-content:center`. When the total node row was wider than the visible container, centered flex overflow could place the first node into negative horizontal overflow, making it look clipped even at the start of the scroll area.

### Changes

- Changed Knowledge Map layout from centered overflow to left-aligned safe overflow.
- Added explicit internal padding and `scroll-padding-inline` so the first and last nodes have breathing room inside the scroll area.
- Fixed concept node flex sizing with `flex: 0 0 145px` so nodes do not shrink unpredictably.
- Bumped frontend assets to `v37`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Frontend regression: `28 passed, 1 warning`.
- Full regression: `126 passed, 2 warnings`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=37` plus `pathly-ui.css?v=37`.

### Known limitation

- The map is still a horizontal scroll layout for wide paths. A future graph layout could add zoom/pan, but this fix prevents the first card from being clipped in the current design.

## Content Agent v2 A1: Parallel annotated-session backend skeleton (2026-07-29)

Status: internally verified; pending user acceptance before A2 UI work.

### Scope

- Implemented the first step of the parallel Content Agent v2 plan.
- Did not replace or mutate the existing v1 Today Learning / Study Blocks page.
- v2 is backend-only at this stage so the JSON contract can be inspected before building the comparison UI.

### Changes

- Added `pathly_annotated_content.py`.
- Added `annotated-session-v1` contract.
- Added deterministic source-first session generation:
  - private PDF chunks first when available;
  - public RAG/resource chunks when no private PDF source exists;
  - clearly labeled generated fallback when no source exists.
- Added source-grounded objects:
  - `reading_sequence`;
  - `pathly_annotation`;
  - `concept_bridges`;
  - `guided_exercises`;
  - `checkpoint`;
  - `quiz_seed`;
  - `citations`.
- Added FastAPI endpoints:
  - `GET /api/plans/{plan_id}/days/{day}/annotated-session`
  - `POST /api/plans/{plan_id}/days/{day}/annotated-session`
- Added independent SQLite tables:
  - `annotated_daily_sessions`
  - `annotated_reading_units`
  - `annotated_reading_progress`
  - `annotated_exercise_attempts`
  - `annotated_source_citations`
  - `content_agent_v2_implementation_log`

### Tracking record

- Wrote A1 verification into new SQLite table `content_agent_v2_implementation_log`.
- Entry ID: `b8486f7e-f100-4629-9687-b244ebd0bf56`.

### Verification

- Python syntax: `py_compile pathly_annotated_content.py pathly_server.py` passed.
- Focused A1 tests: `3 passed, 1 warning`.
- Full regression: `129 passed, 2 warnings`.

### Known limitations

- No v2 frontend page yet. The current learner-facing UI remains v1.
- A1 uses deterministic annotation templates. Live model annotation and richer PDF-page rendering are planned for later stages.
- A1 shows cleaned excerpts and metadata, not embedded full PDF pages.

### Next step

- A2: Build the parallel Annotated Source View UI beside the current Study Blocks View, without removing v1.

Runtime verification update for A1:
- Restarted local Pathly service on http://127.0.0.1:4173/.
- GET /api/health returned HTTP 200.
- /openapi.json contains the annotated-session endpoints.

## Content Agent v2 - A2 Annotated Source View UI

- Status: internal verified
- Completed at: 2026-07-29T07:18:44.544190+00:00
- DB log entry: 0a7482fb-c5da-4517-9aff-ccba5c2b3f9d
- Product change: Added a parallel `Annotated Source View v2` tab next to the existing `Study Blocks View v1`. The old v1 learning session remains available for comparison.
- UI change: v2 displays a source-first reading sequence, cleaned excerpt, Pathly annotations, focus questions, key terms, concept bridges, source-centered exercises, and sidebar Ask Pathly.
- API change: Added persisted reading completion and exercise submission flows through annotated-session progress endpoints.
- Persistence: Reading notes are saved in `annotated_reading_progress`; exercise answers are saved in `annotated_exercise_attempts`.
- Tests:
  - `node --check .\pathly-app.js` passed.
  - `python -m py_compile .\pathly_annotated_content.py .\pathly_server.py` passed.
  - `pytest .\tests\test_pathly_annotated_content.py .\tests\test_pathly_frontend_v2.py -q` -> 35 passed, 1 warning.
  - `pytest -q` -> 133 passed, 2 warnings.
- Runtime verification:
  - `/api/health` returned 200.
  - `/` serves `pathly-app.js?v=38` and `pathly-ui.css?v=38`.
  - `/openapi.json` contains annotated reading progress and exercise submit endpoints.
  - Pathly service restarted on 127.0.0.1:4173 using the project venv; 8501 Streamlit was not modified.
- Known limits:
  - v2 is intentionally parallel, not yet the default.
  - Chat is prefilled from source context but still uses the existing chat pipeline.
  - Exercise submission is recorded and compared against an expected outline; no auto-grading yet.
- Next stage: A3 should improve the actual source-first teaching quality: richer annotations around PDF excerpts, stronger learner-facing explanations, and better use of selected resources as the center of the lesson.

## Content Agent v2 - A3 Rich Source-First Teaching Layers

- Status: internal verified
- Completed at: 2026-07-29T07:46:43.091566+00:00
- DB log entry: 7ac2a7b5-7fe0-4341-ab5e-449ff9e827cf
- Product change: Improved `Annotated Source View v2` from source cards into learner-facing source-annotated lesson blocks.
- Backend change:
  - Bumped `ANNOTATED_AGENT_VERSION` to `content-agent-v2-source-first-a3`.
  - Added `teaching_expansion` to every reading unit: concept intro, mental model, worked source interpretation, source-to-goal explanation, common traps, prerequisite bridge.
  - Added `source_walkthrough` to every reading unit: selected source lines, what each line means, why it matters, and a self-check.
  - Added richer `focus_questions`, `learner_task`, and exercise `scaffold` sentence starters.
  - Updated cache/version logic so old A1/A2 annotated sessions are not reused as current A3 content.
- Frontend change:
  - `Annotated Source View v2` now renders: First learn the idea, Mental model, How Pathly reads the source, Source excerpt, Annotated walkthrough, Read this way, Focus questions, Key terms, and scaffolded exercises.
  - Static assets bumped to `v39`.
- Tests:
  - `node --check .\pathly-app.js` passed.
  - `python -m py_compile .\pathly_annotated_content.py .\pathly_server.py` passed.
  - `pytest .\tests\test_pathly_annotated_content.py .\tests\test_pathly_frontend_v2.py -q` -> 38 passed, 1 warning.
  - `pytest -q` -> 136 passed, 2 warnings.
- Runtime verification:
  - `/api/health` returned 200.
  - `/` serves `pathly-app.js?v=39` and `pathly-ui.css?v=39`.
  - `/openapi.json` still exposes annotated-session endpoints.
  - Pathly service restarted on 127.0.0.1:4173; 8501 Streamlit was not modified.
- Known limits:
  - A3 is still deterministic source-first teaching; not yet a live LLM block generator.
  - It is not a visual PDF page annotator yet; excerpts are displayed as cleaned text with sentence-level Pathly notes.
  - Exercise answers are stored and compared to an outline, not auto-graded.
- Next stage: A4 should add live LLM generation per source block or a PDF-page annotation viewer, depending on whether the priority is content depth or source-document visual fidelity.

## Content Agent v2 - A4 Safe Source Context Viewer

- Status: internal verified
- Completed at: 2026-07-29T08:12:15.975319+00:00
- DB log entry: df1e079f-5595-4971-9b9e-38c7e383646d
- Product change: Added an on-demand source context viewer inside `Annotated Source View v2`.
- Backend change:
  - Added `AnnotatedContentService.source_context(...)`.
  - Added `GET /api/plans/{plan_id}/days/{day}/annotated-session/readings/{reading_id}/source-context`.
  - The endpoint validates user, plan, day, and reading membership before returning source context.
  - For private PDFs, it returns selected/nearby stored chunks and page labels; it does not expose original PDF file URLs.
- Frontend change:
  - Added `View source context` action per annotated reading.
  - Added source context panel with annotation targets, selected excerpt, nearby context chunks, and access boundary note.
  - Static assets bumped to `v40`.
- Tests:
  - `node --check .\pathly-app.js` passed.
  - `python -m py_compile .\pathly_annotated_content.py .\pathly_server.py` passed.
  - `pytest .\tests\test_pathly_annotated_content.py .\tests\test_pathly_frontend_v2.py -q` -> 41 passed, 1 warning.
  - `pytest -q` -> 139 passed, 2 warnings.
- Runtime verification:
  - `/api/health` returned 200.
  - `/` serves `pathly-app.js?v=40` and `pathly-ui.css?v=40`.
  - `/openapi.json` contains `source-context`.
  - Pathly service restarted on 127.0.0.1:4173; 8501 Streamlit was not modified.
- Known limits:
  - This is not a rendered PDF page viewer yet; it is a safe text-chunk source context viewer.
  - No PDF highlight overlay yet.
  - Source context loads per reading on demand.
- Next stage: A5 can either implement a true PDF page render/annotation viewer or add live LLM source-block generation on top of the current source context contract.

## Content Agent v2 - A4 Hotfix: Annotated Tab Switch

- Status: internal verified
- Completed at: 2026-07-29T09:06:06.035284+00:00
- DB log entry: 1c318e80-7e3d-4d4c-ba30-3d5a19ca0dfb
- Bug: Clicking `Annotated Source View v2` did not open the v2 page.
- Root cause: `todayLearning()` still had old logic that reset any non-`content` stage back to `content`; this made the annotated tab appear unresponsive.
- Fix:
  - Added an explicit `state.dailyStage === "annotated"` render branch for `annotatedSourceView()`.
  - Changed completed-day tab disabling so only `Daily Quiz` is disabled, not `Annotated Source View v2`.
  - Static assets bumped to `v41`.
- Clarification: This bug was not caused by the missing PDF page render / annotation viewer. The tab should work independently of that future A5 capability.
- Tests:
  - `node --check .\pathly-app.js` passed.
  - `pytest .\tests\test_pathly_frontend_v2.py -q` -> 33 passed, 1 warning.
  - `pytest -q` -> 140 passed, 2 warnings.
- Runtime verification:
  - `/api/health` returned 200.
  - `/` serves `pathly-app.js?v=41`.
  - Served JS contains the annotated stage branch and quiz-only disabled logic.

## Content Agent v2 - A5 Objective Source-Grounded Exercises

- Status: internal verified
- Completed at: 2026-07-29T09:47:01.797340+00:00
- DB log entry: d7e2cf92-a15e-475a-95f8-53dd0b86929e
- Product change: Converted `Annotated Source View v2` exercises from open-ended written responses into objective checks.
- Backend change:
  - Bumped `ANNOTATED_AGENT_VERSION` to `content-agent-v2-source-first-a5` so old open-ended exercise sessions are not reused.
  - Each reading now generates an `objective_check` exercise.
  - Each exercise includes three question types: single choice, true/false, and multi-select.
  - `submit_exercise` now performs deterministic grading and returns score, pass/fail, correct answers, submitted answers, and per-question explanation.
- Frontend change:
  - Replaced free-text answer box with objective question UI.
  - Added radio/checkbox options, selected state, submit-disabled-until-complete behavior, score display, and per-question feedback.
  - Static assets bumped to `v42`.
- Tests:
  - `node --check .\pathly-app.js` passed.
  - `python -m py_compile .\pathly_annotated_content.py .\pathly_server.py` passed.
  - `pytest .\tests\test_pathly_annotated_content.py .\tests\test_pathly_frontend_v2.py -q` -> 44 passed, 1 warning.
  - `pytest -q` -> 142 passed, 2 warnings.
- Runtime verification:
  - `/api/health` returned 200.
  - `/` serves `pathly-app.js?v=42`.
  - Served JS contains objective exercise UI and grading display logic.
- Known limits:
  - Objective questions are deterministic templates, not live LLM-generated yet.
  - These source checks do not yet feed Adaptation Agent signals.
  - PDF source context remains text-chunk based; no rendered PDF annotation overlay yet.
- Next stage: A6 should connect objective exercise results into learning signals / Daily Quiz / Adaptation, or implement live LLM-authored objective questions if content variety becomes the priority.



## Content Agent v2 - A5 Hotfix: Domain-Focused Objective Questions

- Status: internal verified
- Completed at: 2026-07-29T11:03:32.591741+00:00
- DB log entry: 4f7fba99-5845-4a08-8dc5-c840212e6321
- User-reported issue: Objective questions and lesson notes were testing Pathly/source-reading behavior instead of the knowledge point itself.
- Root cause: A5 deterministic templates hard-coded meta-learning phrases such as `source claim`, `mastery`, `learning path`, and `Pathly's recommended reading strategy`.
- Backend change:
  - Bumped `ANNOTATED_AGENT_VERSION` to `content-agent-v2-source-first-a5-domain-hotfix` so old cached annotated sessions are not reused.
  - Rewrote objective question templates to test concept definition, mechanism, use case, assumptions, and limitations.
  - Rewrote annotated reading notes to remove `Pathly annotation`, `source claim`, and learning-method framing from learner-facing content.
  - Checkpoint now asks for definition, mechanism, example/application, and limitation/assumption.
- Frontend change:
  - Replaced labels such as `How Pathly reads the source` and `Source-annotated lesson sequence` with concept-focused labels.
  - Updated grading success copy from source-claim/path wording to concept-application wording.
  - Static assets bumped to `v43`.
- Tests:
  - `node --check .\pathly-app.js` passed.
  - `python -m py_compile .\pathly_annotated_content.py .\pathly_server.py` passed.
  - `pytest .\tests\test_pathly_annotated_content.py .\tests\test_pathly_frontend_v2.py -q` -> 45 passed, 1 warning.
  - `pytest -q` -> 143 passed, 2 warnings.
- Runtime verification:
  - `/api/health` returned 200.
  - `/` serves `pathly-app.js?v=43` and `pathly-ui.css?v=43`.
  - Local service is listening on `127.0.0.1:4173`.
- Known limits:
  - Questions are still deterministic templates, not live LLM-authored domain questions.
  - The hotfix removes meta-learning wording, but truly richer subject-specific questions still require either stronger KG/RAG extraction or LLM question generation.
- Next stage:
  - Improve the content generator so examples/exercises are grounded in concrete PDF passages or KG facts, not generic concept templates.


## Goal & Sources vertical flow layout (2026-07-30)

Status: internally verified; pending user visual acceptance.

### Problem

- The Goal & Sources onboarding page used a left/right layout.
- The visual order did not clearly communicate the intended sequence: first enter the learning goal, then decide whether to upload private materials, then choose the resource strategy.

### Changes

- Rebuilt the Goal & Sources page as a vertical three-step flow:
  1. Describe the learning outcome.
  2. Optionally upload private PDF materials.
  3. Choose the source strategy: public KG only, private materials plus KG, or private materials only.
- Kept PDF upload optional and explicitly explains that private materials stay private to this learning path.
- Moved the Continue action to the final source-strategy card so the page reads top-to-bottom before advancing.
- Added selected-state styling and explanatory helper text to source strategy cards.
- Scoped the new layout to this onboarding step only; existing two-column layouts for later steps remain unchanged.
- Bumped frontend assets to `v44`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Frontend regression: `35 passed, 1 warning`.
- Full regression: `144 passed, 2 warnings`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=44` plus `pathly-ui.css?v=44`.

### Known limitation

- This is a layout and clarity improvement. It does not change document parsing, source selection semantics, or downstream planning logic.


## Goal & Sources layout sizing fix (2026-07-30)

Status: internally verified; pending user visual acceptance.

### Problem

- After the Goal & Sources page was changed to a vertical flow, the step cards did not adapt to the page width.
- The card column still had a fixed `max-width:1040px`, which left a large empty area on wide screens and made the layout feel misaligned with the hero section.
- The first goal card also felt too tall because the goal textarea used a larger 5-row input inside a full card.

### Changes

- Changed `.goal-flow` to use the full available page width with `width:100%; max-width:none`.
- Ensured each `.flow-step` fills the available width and clips internal overflow safely.
- Reduced the learning-goal textarea from 5 rows to 3 rows and added a controlled minimum height.
- Bumped frontend assets to `v45`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Frontend regression: `35 passed, 1 warning`.
- Full regression: `144 passed, 2 warnings`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=45` plus `pathly-ui.css?v=45`.

### Known limitation

- This improves desktop and responsive sizing for the current vertical flow. It does not redesign the document list density; that can be refined separately if the material list still feels too long.


## Personal Knowledge Map staged redesign plan (2026-07-30)

Status: planning completed; pending user confirmation before implementation.

### Product decision

Pathly should distinguish three layers instead of treating every learning path as a linear concept row:

1. Personal Knowledge Map
   - A goal-specific, learner-specific subgraph generated from the public KG, private materials, goal interpretation, and learner profile.
   - Non-linear by design. It shows prerequisite, related, supports, example/application, and private-evidence relationships.
   - User-editable as a personal overlay. It must never mutate the public Neo4j graph directly.

2. Learning Path
   - A planned learning sequence derived from the confirmed personal knowledge map.
   - It can still have an ordered route, but the route is an interpretation of the graph, not the graph itself.

3. Activity Timeline
   - A daily schedule derived from the learning path, capacity decision, and scheduler.
   - This remains linear because it is about execution by day.

### Current-state audit

- Frontend Dashboard currently uses `plan.concept_path` and renders it through `conceptMap(concepts)` as a horizontal flex row.
- The current UI therefore implies a linear chain even when concepts may have non-linear prerequisite or support relationships.
- Existing plan data already carries useful seeds for a graph:
  - `concept_id`
  - `display_name` / `requested_term` / `label` / `name`
  - `source`
  - `is_target`
  - `estimated_total_minutes`
  - `prerequisite_ids`
  - private concept IDs and display names
- Scheduler already respects `prerequisite_ids`, so adding a graph view can be additive and should not break scheduling.
- Public KG remains hidden from students; only the goal-relevant personal subgraph should be shown.

### Safety principle

Implement this as additive schema and UI first. Do not replace planning, workload, scheduler, daily learning, quiz, or adaptation logic until the new graph layer is proven stable.

### Stage PKM-1: Read-only non-linear Personal Knowledge Map on Dashboard

Goal: Replace the current linear Knowledge Map display with a non-linear, goal-scoped graph view while preserving the existing Activity Timeline.

Implementation scope:

- Add a deterministic Personal Knowledge Map builder from the existing `concept_path`.
- Store or expose a graph-shaped object with:
  - `nodes`
  - `edges`
  - `source_summary`
  - `reason`
- Use `prerequisite_ids` to create prerequisite edges.
- If there are no explicit prerequisites, use conservative fallback edges marked as `sequence_hint`, not as real KG evidence.
- Distinguish node types visually:
  - target
  - prerequisite
  - private material concept
  - public KG concept
  - skipped/known, if available
- Dashboard Knowledge Map should render the graph as a non-linear layout, while Activity Timeline remains the linear day-by-day plan.
- Clicking a node should show source, reason, estimated minutes, and relationship details.
- No user editing in this stage.

Acceptance criteria:

- Existing paths still load.
- Knowledge Map no longer appears as a single linear row.
- Private nodes and public nodes are visually distinct.
- Edges are visible and labeled by relationship type.
- The map only shows concepts relevant to the selected path, not the full Neo4j graph.
- Activity Timeline still works and each unlocked day still has an entry to learning content.
- Full regression passes.

### Stage PKM-2: Planning-stage Knowledge Map Review

Goal: Let the learner inspect the personalized subgraph before workload/capacity planning is finalized.

Implementation scope:

- Insert a new onboarding step after goal/source interpretation and before workload estimation.
- Show the draft Personal Knowledge Map generated from public KG + selected private materials + goal interpretation.
- Let the learner confirm included nodes and inspect explanations.
- Keep edits limited to include/exclude/mark-known in this stage.
- The confirmed map becomes the input to workload estimation.

Acceptance criteria:

- User sees a draft Knowledge Map before workload calculation.
- Confirmed node selections affect workload estimate.
- Rejected nodes are not silently removed if they are required prerequisites; the UI must explain dependency impact.
- Public Neo4j is not modified.
- Refresh restores the draft review state.

### Stage PKM-3: Student-added nodes

Goal: Allow learners to add missing concepts to their personal map.

Implementation scope:

- Add `Add concept` interaction from Knowledge Map Review.
- User provides name, reason, and optional connection target.
- System attempts to match public KG first.
- If no match is confirmed, create a private/custom node in the personal overlay.
- Added nodes can be included in workload and schedule after confirmation.

Acceptance criteria:

- Added nodes appear in the Personal Knowledge Map.
- Added private/custom nodes do not modify the public KG.
- Added nodes are included in workload and scheduling only after user confirmation.
- Duplicate or similar public KG matches require user confirmation.

### Stage PKM-4: Editable Dashboard map after path creation

Goal: Let learners make controlled edits after a path exists without corrupting existing completed learning records.

Implementation scope:

- Allow edit requests from Dashboard map.
- Edits create a pending map-change proposal.
- Changes to incomplete portions can trigger workload/schedule recalculation.
- Completed days remain read-only.

Acceptance criteria:

- Editing the map does not mutate completed learning history.
- Accepted map edits create a new plan version.
- Rejected edits leave the current plan unchanged.
- The UI explains what changes in the map and what changes in the timeline.

### Stage PKM-5: Adaptation updates the Personal Knowledge Map

Goal: Adaptation should propose graph changes first, then timeline changes.

Implementation scope:

- Quiz/chat/feedback signals can propose weak concept nodes, bridge prerequisites, extra review edges, or compressed known nodes.
- Adaptation Review shows before/after Personal Knowledge Map and before/after Activity Timeline.
- User confirmation remains mandatory.

Acceptance criteria:

- Weak concepts appear as graph annotations or added support nodes.
- Accepted adaptation generates a new plan version.
- Rejected adaptation leaves both map and timeline unchanged.

### Recommended next implementation step

Start with Stage PKM-1 only. It is the safest high-value change because it changes the visible Knowledge Map without changing onboarding decisions, workload estimation, scheduling, daily learning, quiz, or adaptation behavior.

Do not begin PKM-2 until PKM-1 is visually accepted.


## PKM-1 read-only Personal Knowledge Map (2026-07-30)

Status: completed; pending user visual acceptance before PKM-2.

### Scope control

- Implemented only the Dashboard read-only Personal Knowledge Map.
- Did not change Neo4j writes.
- Did not change workload estimation.
- Did not change capacity negotiation.
- Did not change scheduler behavior.
- Did not change daily learning, chat, quiz, or adaptation behavior.

### Problem

- Dashboard Knowledge Map previously rendered `concept_path` as a horizontal linear row.
- This made the map look like a simple ordered path, not a personalized goal-relevant knowledge subgraph.
- Existing plan data already contains graph seeds such as `prerequisite_ids`, source type, target flags, private concept IDs, display names, estimated time, and planning reasons.

### Changes

- Replaced the Dashboard Knowledge Map renderer with a read-only Personal Knowledge Map view.
- Added a deterministic frontend graph builder from existing `concept_path`:
  - nodes are derived from path concepts;
  - prerequisite edges are derived from `prerequisite_ids` when available;
  - when explicit prerequisite metadata is missing, dashed `sequence_hint` edges are shown and labeled as hints, not true KG relationships.
- Added a non-linear positioned graph surface using SVG edges and absolute-positioned concept nodes.
- Added visual distinctions for:
  - public KG nodes;
  - private material nodes;
  - target nodes;
  - prerequisite nodes;
  - dashed sequence hints.
- Added a node detail panel showing:
  - display name;
  - source type;
  - target/prerequisite role;
  - estimated work;
  - reason for inclusion;
  - related edge labels.
- Added explicit copy that this map is read-only in PKM-1 and student editing starts in a later reviewed stage.
- Preserved Activity Timeline as the linear execution schedule with day-entry buttons.
- Bumped frontend assets to `v46`.

### Test and recovery note

- During implementation, the frontend test file was accidentally overwritten with frontend script content due to a local script variable reuse issue.
- This was corrected before completion:
  - the product JS file was verified separately;
  - the frontend test file was rebuilt as static contract coverage for the same learner-facing flows;
  - the frontend test count was restored to 35 tests;
  - full regression returned to 144 passing tests.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Frontend regression: `35 passed, 1 warning`.
- Full regression: `144 passed, 2 warnings`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=46` plus `pathly-ui.css?v=46`.

### Acceptance checklist for user

- Open Dashboard > Knowledge Map.
- Confirm the map is no longer just a single horizontal row of cards.
- Confirm the title says `Personal Knowledge Map` / goal-relevant subgraph.
- Confirm public KG, private material, target, and sequence hint legend is visible.
- Click different nodes and confirm the right-side details panel changes.
- Switch to Activity Timeline and confirm the daily learning entry buttons still work.

### Known limitations

- PKM-1 is read-only.
- The graph is derived from existing `concept_path`; it does not yet create or persist a separate backend `personal_knowledge_graph` object.
- `sequence_hint` edges are fallback display hints when prerequisite metadata is missing; they are not presented as real KG evidence.
- Student editing, add-node, and planning-stage map review are intentionally deferred to PKM-2/PKM-3 after visual acceptance.


## PKM-2 planning-stage Knowledge Map review (2026-07-30 16:36:08)

Status: completed; pending user visual acceptance before PKM-3.

### Scope control

- Implemented a planning-stage Personal Knowledge Map review gate inside onboarding.
- Did not change Neo4j writes.
- Did not change workload estimation or total minute calculation.
- Did not change capacity negotiation, scheduler, daily learning, quiz, or adaptation behavior.
- Did not add student node editing yet; that remains PKM-3.

### Problem

- Students could only see the personalized map after a path was already created.
- The planning flow did not show which goal-related concepts would enter learner profiling and workload planning.
- The Dashboard map was improved in PKM-1, but onboarding still jumped from Goal & Sources directly to profile questions.

### Changes

- Added a `Personal Knowledge Map Review` step after Goal & Sources and before Learner Profile.
- The review map is generated from the current draft goal scope:
  - confirmed public KG mappings when available;
  - confirmed private-material concepts when available;
  - goal-derived target terms when no interpretation object exists.
- Restored saved goal interpretation data during draft hydration so refresh does not degrade the review map.
- Persisted per-draft map-review confirmation in local storage so refresh does not force the user to reconfirm the same draft.
- Added `Confirm Map and Continue` and `Back to Goal & Sources` actions.
- Reused the Personal Knowledge Map graph renderer with separate Review/Dashboard copy:
  - Review mode says timing is pending and prerequisite metadata is resolved in later planning steps;
  - Dashboard mode remains a read-only path map.
- Fixed pre-workload timing display so pending estimates show as `pending`, not `pendingm`.
- Bumped frontend assets to `v47`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Frontend regression: `37 passed, 1 warning`.
- Full regression: `146 passed, 2 warnings`.
- `GET /`: HTTP 200 and serves `pathly-app.js?v=47` plus `pathly-ui.css?v=47`.

### Acceptance checklist for user

- Start `+ New Path` and complete Goal & Sources.
- Confirm the next page is `Personal Knowledge Map Review`, not the learner profile questions.
- Confirm the map only shows goal-related public/private concepts, not the whole Neo4j KG.
- Confirm map nodes are clickable and the detail panel updates.
- Click `Back to Goal & Sources` and confirm goal/source edits are possible.
- Confirm `Confirm Map and Continue` moves into Learner Profile.
- Refresh on the review page or after confirming it and verify the draft state is recovered.

### Known limitations

- PKM-2 is a scope confirmation gate. It does not yet let students add/edit/delete nodes.
- The review map does not persist a separate backend `personal_knowledge_graph` object yet.
- When explicit prerequisite metadata is missing, dashed edges remain `sequence_hint` edges rather than real KG prerequisite claims.
- Student map editing and backend persistence are PKM-3.


## PKM-3 review-map editing and softer workload estimates (2026-08-01)

Status: completed; user acceptance confirmed.

### Scope control

- Implemented only:
  - softer workload and capacity estimate wording in onboarding;
  - Personal Knowledge Map Review for every source mode;
  - private draft-level connection editing inside the review map.
- Did not change Neo4j writes.
- Did not write student-edited edges into the public KG.
- Did not change scheduler, daily session generation, quiz scoring, or adaptation logic.

### Changes

- Replaced exact onboarding workload copy such as per-activity minute rows with coarser estimate language:
  - `around X hours`;
  - source/context explanation;
  - category tags instead of explicit minute bars.
- Kept capacity negotiation logic intact while making the user-facing estimate less judgeable and less over-precise.
- Ensured Personal Knowledge Map Review can still render when the learner chooses `kg_only`:
  - falls back to draft `target_terms`;
  - if needed, derives a limited set of goal terms directly from the goal text.
- Added private, draft-only connection editing in the review map:
  - choose a node as connection source;
  - connect source to another node;
  - remove user-added links;
  - render user-added links as `student_link` edges.
- Persisted edited review edges in local storage per draft, alongside the existing map-review confirmation state.
- Reset review confirmation and edited edges whenever a new draft is created or a goal is revised, so the learner must re-review the updated scope.
- Bumped frontend assets to `v48`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Frontend regression: `39 passed, 1 warning`.
- Full regression: `148 passed, 2 warnings`.
- Local service serves `pathly-app.js?v=48` and `pathly-ui.css?v=48`.

### Acceptance checklist for user

- In onboarding workload/capacity review, confirm the estimate reads like `around X hours` rather than exposing detailed per-activity minutes.
- Start a new path with `Use the public knowledge graph` only and confirm Personal Knowledge Map Review still appears.
- On the review map:
  - click a node;
  - set it as connection source;
  - connect it to another node;
  - remove a user-added link.
- Refresh and confirm the edited review-map links for that draft are restored.
- Confirm the review-map editing feels private to the draft and does not alter the broader dashboard/public KG language.

### Known limitations

- Review-map edge editing is still frontend-local and draft-scoped; it is not yet persisted to the backend plan object.
- Student-edited edges do not yet influence workload estimation or scheduler ordering.
- Node add/delete is still deferred to a later PKM stage.

### User confirmation

- 2026-08-01: user accepted PKM-3 visual and behavior changes.

## Public KG sparse-target expansion hotfix (2026-08-01)

Status: completed; awaiting user verification.

### Problem

- With `Use the public knowledge graph` and a goal such as `machine learning`,
  the planning path could contain only the exact target because the target had
  sparse or unavailable prerequisite metadata.
- This made the Personal Knowledge Map appear to contain a single node even
  when the public KG contained related concepts.

### Changes

- Added a bounded sparse-target expansion in `pathly_workload.py`.
- When the confirmed public/canonical path has fewer than four concepts, the
  planner adds one-hop dependent concepts and up to six similarity neighbors
  exposed by the active KG repository.
- The expansion is capped at twelve concepts, preserves the target and does not
  expose the full KG or change public KG data.
- Existing prerequisite-safe ordering and learner-profile prioritization remain
  authoritative.

### Verification

- Workload and planning regression: `16 passed, 1 warning`.
- Calibrated public KG check: `Machine Learning` has related dependents including
  `Classification`, `Deep Learning`, `Neural Networks`, and `Regression`.

### Known limitation

- The visible result still depends on the active Neo4j/JSON KG containing related
  edges. If both sources are sparse, the map will remain appropriately small.

### Acceptance checklist

- Start a new path with `Use the public knowledge graph`.
- Use a goal containing `machine learning`.
- Confirm the Personal Knowledge Map shows the target plus related public
  concepts, rather than only one node.
- Confirm private-material concepts are not added when no private source is
  selected.

## PKM review-stage public concept expansion hotfix (2026-08-01)

Status: completed; awaiting user verification.

### Problem found after verification

- The previous sparse-target fix only affected workload generation after the
  review page. The review page itself still rendered only `draft.target_terms`,
  so `Machine Learning` remained a single node before confirmation.

### Changes

- Added review-stage public concept expansion for common goal families,
  including Machine Learning, Neural Networks, and RAG.
- The expansion adds related public concepts as non-target nodes while keeping
  the user's goal as the target node.
- Private concepts remain separate and are not introduced for `kg_only` paths.
- Bumped frontend assets to `v49`.

### Verification

- JavaScript syntax: `node --check pathly-app.js` passed.
- Existing full regression remains green before this frontend-only change:
  `148 passed, 2 warnings`.

### Acceptance checklist

- Refresh the browser with a cache-busting reload.
- Start a new `kg_only` path for `machine learning`.
- On Personal Knowledge Map Review, confirm the target plus related public
  concepts are visible before proceeding to Learner Profile.

## PKM review ordering hotfix (2026-08-01)

Status: completed; awaiting user verification.

- Fixed the review-map fallback ordering so related/prerequisite concepts are
  placed before the target instead of after it.
- The target remains the final learning objective in the left-to-right review
  sequence, with default sequence edges flowing toward it.
- Bumped frontend assets to `v50`.
- Verification: JavaScript syntax passed; frontend regression `39 passed, 1 warning`.

## Anonymous session startup resilience hotfix (2026-08-02)

Status: completed; awaiting user verification.

- Added explicit same-origin credentials to all frontend API requests so the
  secure session cookie is reliably retained.
- Extended transient connection retries during startup.
- Added a dedicated `Retry` action when anonymous session creation cannot reach
  the local service.
- Verified `POST /api/sessions/anonymous` returns HTTP 201 and a fresh browser
  reaches the workspace without an error banner.
- Bumped frontend assets to `v58`.
- Verification: JavaScript syntax passed; frontend regression `39 passed, 1 warning`.

## Network fetch resilience hotfix (2026-08-01)

Status: completed; awaiting user verification.

- Added one short retry for transient frontend API connection failures.
- Replaced the raw browser `Failed to fetch` message with a specific Pathly
  endpoint error and recovery guidance.
- Confirmed both `127.0.0.1:4173` and `localhost:4173` health endpoints return
  HTTP 200.
- Bumped frontend assets to `v57`.
- Verification: JavaScript syntax passed; frontend regression `39 passed, 1 warning`.

## PKM review self-validation and sequence-edge fix (2026-08-01)

Status: completed; awaiting user verification.

- Fixed the fallback sequence edge index bug that created self-edges and made
  paths appear invisible or reversed.
- Review concepts now form valid left-to-right orthogonal paths, for example
  `A → B → C`, and excluded middle nodes are bypassed using active neighbors.
- Browser self-check confirmed the live page serves `v56` and rendered paths such
  as `M 201 91 H 234 V 119 H 266`.
- API/homepage self-check returned HTTP 200; frontend regression `39 passed, 1 warning`.

## PKM dashed-edge visibility hotfix (2026-08-01)

Status: completed; awaiting user verification.

- Strengthened the `sequence_hint` SVG path styling with explicit dashed,
  rounded strokes so the fallback relationship type is visibly distinct from
  confirmed prerequisite edges.
- Bumped frontend assets to `v53`.
- Verification: frontend asset assertions updated; JavaScript remains syntactically valid.

## PKM review-page dashed-line rendering hotfix (2026-08-01)

Status: completed; awaiting user verification.

- Corrected the actual Review Map SVG path rendering so `sequence_hint` edges
  receive an explicit dashed stroke inline, independent of stylesheet caching or
  selector precedence.
- Bumped frontend assets to `v54`.
- Verification: JavaScript syntax passed; frontend regression `39 passed, 1 warning`.

## PKM connection-toggle interaction (2026-08-01)

Status: completed; awaiting user verification.

- Removed the review-stage connection-source editor from the rendered map flow;
  nodes are now the direct interaction surface.
- Clicking a non-target node toggles it between included and `Excluded from
  path`; excluded nodes remain visible but are dimmed and their edges are
  removed from the map.
- The target node remains fixed and cannot be excluded.
- Review state is persisted per draft in local storage and reset when the goal
  or draft changes.
- Added an `Excluded from path` legend and visual treatment.
- Bumped frontend assets to `v51`.
- Verification: JavaScript syntax passed; frontend regression expected to remain
  green after the asset-version assertion update.

### Known limitation

- The exclusion state is currently draft-local UI state. The next backend step
  must persist it into the draft and apply it when generating workload/plans;
  this change prevents misleading map interactions while that integration is
  completed.

## PKM orthogonal edges and excluded-node bypass (2026-08-01)

Status: completed; awaiting user verification.

- Replaced diagonal SVG relationship lines with horizontal-vertical orthogonal
  paths.
- When a middle node is excluded, the fallback learning sequence is rebuilt
  from active nodes so the preceding and following nodes remain connected.
- Excluded nodes stay visible as a dimmed, dashed card and are not silently
  deleted.
- Bumped frontend assets to `v52`.
- Verification: JavaScript syntax passed; frontend regression `39 passed, 1 warning`.
## Secure session startup correction (2026-08-02, v59)

- Status: internally verified; ready for user acceptance.
- Root cause: the frontend created the anonymous session and restored saved lesson state inside one shared error boundary. A failure while restoring an old `Today Learning` reference was therefore incorrectly relabelled as a secure-session connection failure.
- Changes:
  - separated anonymous-session creation from saved-state hydration;
  - only a real failure of `POST /api/sessions/anonymous` now shows the secure-session error;
  - a stale/unavailable lesson now returns to Learning Paths with a recoverable notice;
  - clears draft, plan and lesson references when the server resolves a different anonymous user;
  - increased transient network attempts from two to four and made network errors identify the failed endpoint;
  - restored a visible Retry action for genuine session/network failures;
  - bumped frontend assets to v59.
- Verification:
  - live `POST http://127.0.0.1:4173/api/sessions/anonymous`: HTTP success response with a new anonymous session;
  - `node --check pathly-app.js`: passed;
  - `pytest -q tests/test_pathly_frontend_v2.py`: 39 passed, 1 dependency deprecation warning;
  - fresh in-app browser load at `/?v=59`: navigation and onboarding restored without a session error;
  - browser reload after hydration: no session error and no browser console errors.

## Personal Knowledge Map exclusion data closure (2026-08-02, v60)

- Status: internally accepted; ready for user acceptance.
- Goal: make review-map exclusions authoritative backend data and ensure excluded concepts do not contribute workload or scheduled activities.
- Backend and API:
  - added `PUT /api/onboarding-drafts/{draft_id}/knowledge-map-review`;
  - stores reviewed concepts, included/excluded concept IDs, active edges and confirmation time inside the server-owned onboarding draft;
  - rejects unknown exclusions, target exclusion and changes after profile confirmation;
  - goal revision invalidates the old map review;
  - legacy drafts without a map review remain readable.
- Workload and scheduling:
  - workload generation applies the confirmed exclusion after KG concept expansion and before activity generation;
  - excluded concepts are removed from `concept_path`, `concept_units`, estimate sources and generated learning activities;
  - total workload is recalculated from the remaining concepts;
  - O6 scheduler receives only the filtered concept path and activities, so excluded concepts cannot appear in scheduled days;
  - learning targets remain protected from exclusion;
  - required document reading remains governed by its explicit required-material scope and is not silently deleted by excluding one extracted concept.
- Frontend:
  - `Confirm Map and Continue` now saves the review to the backend before opening Learner Profile;
  - saved exclusions and edges are hydrated from the server on refresh;
  - assets bumped to v60.
- Verification:
  - JavaScript syntax passed;
  - focused onboarding/workload/scheduler/frontend suite: 71 passed, 1 third-party warning;
  - full regression: 150 passed, 2 third-party warnings, exit code 0;
  - focused data test: excluding `Foundation` reduces total workload, removes it from every generated activity, and removes it from every scheduled day;
  - live service restarted on `127.0.0.1:4173`, health returned 200 and OpenAPI exposed the new review endpoint;
  - live browser v60: excluding `Regression` visibly changed the map, backend confirmation advanced to Learner Profile, refresh restored the profile step, and the browser console contained no errors.
- Known boundary:
  - this stage makes include/exclude authoritative. Student-created custom edges are stored with the review but do not yet override canonical prerequisite ordering; that requires a separately reviewed relationship-editing policy.

## Capacity confirmation simplification and path-create recovery (2026-08-02, v61)

- Status: internally verified; ready for user acceptance.
- UX issue:
  - an insufficient-capacity learner already selected and confirmed `extend_days` or `increase_daily_time`, but the Create Path step displayed the strategy cards again;
  - the repeated choice made the second confirmation look ineffective and hid the final create action behind another confirmation;
  - if plan v1 creation succeeded but O6 scheduling failed, the frontend presented the whole action as failed.
- Changes:
  - a confirmed feasible timing adjustment now opens a single `Ready to Create` summary;
  - the summary shows completion window and daily limit, with only `Edit Capacity` and `Confirm and Create Path` actions;
  - the already-confirmed adjustment is not expanded or selected again;
  - initially feasible plans still offer meaningful alternatives once; after one is confirmed they also reach the same final summary;
  - plan confirmation and timeline scheduling now have separate recovery handling;
  - when plan v1 succeeds but scheduling fails, Learning Paths still opens and explains that timeline generation can be retried;
  - assets bumped to v61.
- Verification:
  - JavaScript syntax passed;
  - focused frontend/feasibility/scheduler suite: 62 passed, 1 third-party warning;
  - full regression: 151 passed, 2 third-party warnings, exit code 0;
  - live service serves v61;
  - fresh browser load retained navigation, showed no session error and produced no console errors.

## Edit Capacity repeated-decision hotfix (2026-08-02, v62)

- Status: internally verified; ready for user acceptance.
- Root cause: `Edit Capacity` returned to the form, but `Check Feasibility` created a new feasible decision without a selected strategy. The Create Path step therefore opened the strategy chooser again even though the learner's edited inputs already covered the goal.
- Change:
  - every feasible `Check Feasibility` result now explicitly saves `proceed`, meaning “use these exact inputs”;
  - the flow goes directly to the `Ready to Create` summary after initial feasible input or edited feasible input;
  - strategy cards remain reserved for a genuinely insufficient result and its explicit correction flow;
  - final copy describes the confirmed time window instead of exposing internal strategy terminology;
  - assets bumped to v62.
- Verification:
  - JavaScript syntax passed;
  - focused frontend/feasibility suite: 54 passed, 1 third-party warning;
  - full regression: 152 passed, 2 third-party warnings, exit code 0;
  - live v62 browser opened with navigation, no secure-session error and no console errors.

## Knowledge Map role semantics and target-last layout (2026-08-02, v64)

- Status: internally verified; ready for user acceptance.
- Root cause:
  - sparse public-KG expansion added related/dependent concepts after the target;
  - the Dashboard treated every non-target concept as a prerequisite, even when it was only a related expansion;
  - this produced misleading copy such as a “required prerequisite scheduled after Machine Learning”.
- Changes:
  - workload now assigns an explicit `path_role`: `prerequisite`, `supporting`, or `target`;
  - only the recursive prerequisite closure of the target is labelled prerequisite;
  - related expansion nodes without prerequisite evidence are labelled `Supporting concept`;
  - canonical ordering is now prerequisite, supporting concept, then target;
  - supporting concepts no longer retain an outgoing prerequisite claim from the target;
  - Dashboard re-derives these roles for old plan versions, so existing maps also receive the corrected label and target-last layout without regenerating the path;
  - supporting concepts use dashed sequence hints toward the target;
  - added a Supporting concept legend and bumped assets to v64.
- Verification:
  - focused workload/frontend/scheduler suite: 63 passed, 1 third-party warning;
  - full regression: 154 passed, 2 third-party warnings, exit code 0;
  - semantic test verifies `Artificial Intelligence` prerequisite → `Deep Learning` supporting → `Machine Learning` target ordering;
  - live service restarted and serves v64; fresh browser load produced no console errors.

## Knowledge Map adaptive semantic layout (2026-08-02, v65)

- Status: internally verified; ready for user acceptance.
- Problem closed:
  - concept cards used a fixed 165 x 110 pixel box, so long labels could be clipped;
  - every concept in the same semantic stage was stacked in one tall column, creating excessive empty space and vertical scrolling;
  - edge labels were positioned from fixed card dimensions and could collide with cards.
- Implementation:
  - the graph now lays out prerequisite, supporting, and target stages from left to right;
  - stages automatically wrap into additional columns after three or four rows;
  - each card is 210 pixels wide and its height is calculated from the full concept title;
  - stage columns are vertically centered against the tallest column;
  - orthogonal edge geometry and labels use each card's actual dimensions;
  - long labels wrap without truncation, with a narrower card override on small screens;
  - assets bumped to v65.
- Verification:
  - JavaScript syntax check passed;
  - focused frontend/workload suite: 55 passed, 1 warning;
  - complete regression: 155 passed, 2 warnings;
  - live browser loaded v65 assets at 1280 x 720 with no console errors.

## New Path navigation reset hotfix (2026-08-02, v66)

- Status: internally verified; pending user visual acceptance.
- Root cause: the sidebar label `+ New Path` called `go('workspace')`, which reopened the existing confirmed onboarding draft and therefore rendered `Path Confirmed` instead of a new goal form.
- Changes:
  - bound the sidebar `+ New Path` action to `newPath()`;
  - reset the previous draft, goal, answers, interpretation, workload, feasibility decision, selected documents, source mode, connection editor, notices and errors;
  - retained existing completed learning paths in Learning Paths;
  - bumped active frontend assets from v65 to v66.
- Verification:
  - `node --check pathly-app.js`: passed;
  - focused frontend regression: 44 passed, 1 third-party deprecation warning;
  - added a regression assertion that the sidebar action calls `newPath()` and that the prior onboarding state is cleared.
- Visual acceptance boundary: direct browser automation was unavailable because the Windows browser-control process returned `CreateProcessWithLogonW failed: 1385`; no browser click result is claimed.
## Knowledge Map coarse-estimate presentation (2026-08-03, v67)

- Status: internally verified; pending user visual acceptance.
- Product rule: exact workload minutes remain server-side for workload calculation, capacity checks, scheduling and future adaptation, but are no longer exposed on the student-facing Personal Knowledge Map.
- Changes:
  - removed per-concept minute labels from every map node;
  - removed `Estimated work` from the selected-node detail panel;
  - replaced raw planning reasons that exposed base and adjusted minute calculations with role-based explanations of why the concept is included;
  - retained concept role, source, prerequisite/sequence relationships and target status;
  - bumped active frontend assets to v67.
- Verification:
  - `node --check pathly-app.js`: passed;
  - focused frontend regression: 45 passed, 1 third-party deprecation warning;
  - live service serves v67;
  - served JavaScript contains no map-node minute renderer, no detail-panel `Estimated work`, and no raw `planning_reason` output in concept detail.
- Boundary: user-entered scheduling constraints and measured learning results are not changed by this presentation-only update.
## Selected materials and optional private concepts (2026-08-03, v68)

- Status: internally verified; pending user visual acceptance.
- Product boundary:
  - documents explicitly selected by the learner are stored as required/core sources for this path;
  - concepts extracted from those documents are optional candidate nodes, not mandatory materials;
  - Pathly does not automatically add unselected private documents to the path.
- Changes:
  - separated the interpretation page into `Selected materials — used in this path`, public KG candidates, and `Concepts Suggested From Your Materials`;
  - added clear copy that unchecking a concept excludes it from the Knowledge Map and workload but keeps the selected document available as private learning evidence;
  - frontend now submits both accepted and explicitly rejected private concept IDs;
  - backend persists `rejected_private_concepts` and treats them as a valid decision rather than pending work;
  - changing document selection invalidates the current interpretation so stale concepts cannot survive a source change;
  - selected document payloads now use `role=core` and `required=true`;
  - private-only paths with no confirmed concepts are blocked with recovery guidance, preventing an empty path;
  - bumped frontend assets to v68.
- Verification:
  - Python compile: `pathly_server.py`, `pathly_goal_interpretation.py` passed;
  - JavaScript syntax: `pathly-app.js` passed;
  - focused interpretation/document/frontend suite: 55 passed, 2 third-party deprecation warnings;
  - live service restarted from the project environment; `/api/health` returned HTTP 200 and `/` serves `pathly-app.js?v=68`.
- Known boundary:
  - there is currently no automatic private-document recommendation feature. If it is added later, it must render in a separate `Suggested materials` section, default unselected, and must never become a source without explicit learner opt-in.
## Public KG monotonic expansion regression (2026-08-03)

- Status: internally verified.
- Rule protected: for the same learning goal and KG source, adding selected private materials under `private_plus_kg` may add relevant public concepts but must not reduce the goal-derived Public KG baseline. `private_only` is intentionally excluded because it is an explicit learner choice to omit the public baseline.
- Added regression: `test_private_materials_only_expand_never_reduce_public_goal_baseline` compares the public concept IDs from `kg_only` against the IDs produced by the same goal with selected private material, and asserts `baseline ⊆ augmented`.
- Verification: `pytest -q tests/test_pathly_goal_interpretation.py` -> 9 passed, 1 third-party deprecation warning.
## Recognized Public KG concepts in interpretation (2026-08-03, v69)

- Status: internally verified; pending user visual acceptance.
- Problem addressed: an exact, high-confidence Public KG match (for example, `Machine Learning`) is auto-confirmed and therefore correctly absent from the review-only candidate list. The previous page did not show that recognized match, which could misleadingly look like no public KG concept had been found.
- Changes:
  - added a read-only `Recognized Public Concepts` section above reviewable Public KG candidates;
  - displays de-duplicated `canonical_concepts` that were automatically included through a high-confidence Public KG match;
  - renamed the review section to `Public KG Candidates Requiring Review` to make its purpose explicit;
  - kept selected documents as required sources, private concepts as optional checkboxes, and rejected private concepts as explicit exclusions; no interpretation, source-selection, or monotonic Public KG rule changed;
  - bumped the active frontend asset to v69.
- Verification:
  - `node --check pathly-app.js`: passed;
  - `pytest -q tests/test_pathly_goal_interpretation.py tests/test_pathly_frontend_v2.py tests/test_pathly_document_interpretation_integration.py`: 56 passed, 2 third-party deprecation warnings;
  - HTTP verification: homepage serves `pathly-app.js?v=69`, and the served asset contains `Recognized Public Concepts`.
- Known boundary: this section explains auto-confirmed public concepts; it intentionally does not make them optional, preserving the existing distinction between required selected documents and optional extracted private concepts.
## Personal Knowledge Map semantic roles and connection controls (2026-08-03, v70)

- Status: internally verified; pending user visual acceptance.
- Problem addressed:
  - review-map concepts were often all marked as targets or generic supporting concepts because confirmed interpretation entries were treated as targets and missing relationship metadata fell into one fallback role;
  - independently routed sequence hints could overlap and visually resemble solid lines;
  - the prior review flow did not make the default learning relationships directly editable in the map.
- Changes:
  - introduced one primary target, plus distinct `Prerequisite`, `Core learning target`, and `Supporting concept` roles for the pre-workload map;
  - added a goal-scoped semantic relationship set for Machine Learning, Neural Networks, and RAG-related concepts, while preserving safe sequence-hint fallbacks for other goal scopes;
  - rendered only de-duplicated orthogonal SVG connections; route lanes are offset when a corridor has multiple edges, and relationship labels no longer clutter or overlap the graph;
  - made review-map edges clickable: click an active connection to exclude it; click its pale dashed excluded connection to restore it;
  - generated a private draft-only bridge when excluding a middle relationship would otherwise leave its predecessor disconnected from the remaining path;
  - derives excluded nodes from whether they still reach the primary target, then passes only those exclusions into the confirmed review and workload filter;
  - nodes remain selectable for explanation; the primary target remains protected from exclusion;
  - persists the selected node role with the confirmed knowledge-map review; existing selected-document, optional-private-concept, and Public KG monotonic-expansion rules were not changed;
  - bumped active frontend assets to v70.
- Verification:
  - `node --check pathly-app.js`: passed;
  - Python compile: `pathly_onboarding.py`, `pathly_server.py`, `pathly_workload.py`: passed;
  - focused frontend, onboarding, workload, goal-interpretation and document-flow regressions: 81 passed, 2 third-party deprecation warnings;
  - running service HTTP check: homepage serves `pathly-app.js?v=70`; the served asset includes semantic roles, edge toggling, bridge logic and excluded-connection UI.
- Visual-check limitation:
  - attempted browser automation for final visual inspection, but the local Windows browser process could not start because of `CreateProcessWithLogonW failed: 1385`. This is an environment limitation, not treated as a passed visual test. Manual visual acceptance is still required.
- Known boundary:
  - semantic relationship templates are deliberately conservative before full Neo4j prerequisite metadata is available. They are an editable learner-facing subgraph, not a claim that every public-KG relationship has been fully resolved.
## Personal Knowledge Map node-based exclude and restore fix (2026-08-03, v71)

- Status: internally verified; pending user visual acceptance.
- User-visible correction:
  - map interaction is now on concept nodes, not relationship lines;
  - clicking a non-primary node excludes that concept from the draft path;
  - clicking an excluded node restores it and its default relationships;
  - the primary target remains viewable but cannot be excluded.
- Recovery and continuity:
  - restoration removes any legacy edge-level exclusion touching the restored node, so concepts excluded in the earlier v70 interaction can be added back;
  - node exclusion removes its incident relationships and adds a draft-only bridge from each included predecessor to each included successor where appropriate;
  - restoring the node removes the generated bridge and returns to the ordinary semantic relationship set;
  - graph paths are explanatory only and no longer accept pointer or keyboard input.
- Verification:
  - `node --check pathly-app.js`: passed;
  - focused frontend, onboarding, workload, goal-interpretation and document-flow regressions: 81 passed, 2 third-party deprecation warnings;
  - isolated graph behavior check passed: excluding `Supervised Learning` created `Regression -> Classification` bridge; restoring it removed that bridge and restored the node;
  - running service HTTP verification passed: homepage serves `pathly-app.js?v=71` and asset includes node exclusion, restoration and bridge functions.
## Personal Knowledge Map viewport retention fix (2026-08-03, v72)

- Status: internally verified; pending user visual acceptance.
- User-visible correction:
  - selecting a later concept no longer sends the Personal Knowledge Map back to its left/top origin;
  - excluding or restoring a concept also keeps the current horizontal and vertical map position, so the visible change remains in context.
- Implementation:
  - saves the current `.pkm-map` scroll offsets immediately before node-triggered re-rendering;
  - restores those offsets on the next rendered frame;
  - viewport state is transient UI state only and is not stored as learner or learning-path data.
- Verification:
  - `node --check pathly-app.js`: passed;
  - focused frontend, onboarding, workload, goal-interpretation and document-flow regressions: 82 passed, 2 third-party deprecation warnings;
  - running service HTTP verification passed: homepage serves `pathly-app.js?v=72` and the served asset contains both viewport save and restore helpers.
- Known limitation:
  - automated browser-level visual checking remains unavailable in this Windows environment; final visual confirmation is manual.
## Final PKM snapshot consistency fix (2026-08-03, v73)

- Status: internally verified; pending user visual acceptance.
- Correction:
  - the confirmed Personal Knowledge Map is now the authoritative scope for the final plan;
  - included concepts, the single primary target, semantic roles, and active edges are copied from the confirmed review snapshot;
  - workload estimation adds activity/time metadata without rebuilding or reclassifying the confirmed map;
  - the final Dashboard receives the same confirmed edge snapshot instead of deriving a second graph from partial prerequisite metadata;
  - excluded concepts are omitted from the final plan scope, while the editable preview remains the place where they can be restored.
- Verification:
  - `node --check pathly-app.js`: passed;
  - Python compile for `pathly_workload.py`: passed;
  - core frontend, planning API, Onboarding and workload regressions: 79 passed, 1 third-party warning;
  - added regression coverage for the full edge snapshot in the confirmation payload and final plan payload.
- Known limitation:
  - automated browser-level visual checking remains unavailable in this Windows environment; manual acceptance is still required.
## Exact preview-to-final map reuse (2026-08-04, v74)

- Status: internally verified; pending user visual acceptance.
- Correction:
  - final Dashboard now renders the complete reviewed-concepts snapshot, including the same excluded nodes, roles and confirmed edges shown in the preview;
  - final map no longer derives its node set from the workload-only `concept_path`;
  - workload data remains separate and continues to drive activities and scheduling only.
- Verification:
  - `node --check pathly-app.js`: passed;
  - Python compile for `pathly_workload.py`: passed;
  - core frontend, planning API, Onboarding and workload regressions: 79 passed, 1 third-party warning;
  - running service HTTP verification passed: homepage serves `pathly-app.js?v=74` with exact snapshot rendering wiring.
- Known limitation:
  - existing plans created before v74 do not contain the full reviewed-concepts snapshot; create a new path to validate exact equality.
## Full Lecture View v3 — Step 1: contract foundation (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Scope completed:
  - added isolated `full-lecture-v3` contract module;
  - defined stable learner-facing fields for overview, source materials, lecture sections, practice, knowledge check, citations and generation metadata;
  - added structural validation, positive-minute checks and schedule-budget guard;
  - added compatibility conversion from existing `annotated-session-v1` without changing the v1/v2 experience;
  - compatibility payload is explicitly marked `fallback` and `compatibility_shell` until the lecture generator is implemented.
- Files: `full_lecture_contract.py`, `tests/test_full_lecture_contract.py`
- API/database changes: none in this step; no existing route or table was changed.
- Verification: `pytest -q tests/test_full_lecture_contract.py tests/test_pathly_annotated_content.py`: **14 passed**; one existing Starlette/httpx deprecation warning only.
- Manual acceptance:
  1. Confirm the current annotated page still behaves unchanged.
  2. Confirm this step is only a contract foundation; no new v3 page is expected yet.
- Known limitation: no full lecture generation or UI has been wired yet.
- Next step after confirmation: Step 2 — evidence selection and deterministic full-lecture fallback generation.

## Full Lecture View v3 — Step 2: evidence preparation and deterministic fallback (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Scope completed:
  - added `full_lecture_generator.py` as an isolated v3 generator;
  - added bounded evidence preparation that removes email/DOI-style metadata noise and marks quality flags;
  - converted annotated source readings into learner-facing lecture sections with explanation, worked interpretation, misconceptions and takeaway;
  - preserved source references and section minute budgets;
  - added practice and knowledge-check payloads tied to the selected source sections;
  - fallback is explicitly marked `generation_mode=fallback` and does not claim live model output.
- Files: `full_lecture_generator.py`, `tests/test_full_lecture_generator.py`
- API/database changes: none; current v1/v2 routes remain unchanged.
- Verification: `pytest -q tests/test_full_lecture_contract.py tests/test_full_lecture_generator.py tests/test_pathly_annotated_content.py`: **16 passed**; one existing Starlette/httpx deprecation warning only.
- Manual acceptance:
  1. Confirm no existing Today Learning page changed.
  2. Confirm this step only establishes the v3 fallback generator; it is not connected to the browser yet.
- Known limitation: source selection still consumes the existing annotated session; the real v3 API/page and multi-source lecture orchestration come in later steps.
- Next step after confirmation: Step 3 — expose the v3 lecture payload through a parallel API route, without replacing the current page.

## Full Lecture View v3 — Step 3: parallel API exposure (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Scope completed:
  - added `GET /api/plans/{plan_id}/days/{day}/full-lecture`;
  - route reuses the existing annotated-session source context and converts it to the new `full-lecture-v3` contract;
  - route preserves learning-day unlock checks and existing error envelope conventions;
  - existing `/session` and `/annotated-session` routes remain unchanged;
  - no frontend navigation has been switched to v3 yet.
- Files: `pathly_server.py`, `tests/test_full_lecture_api.py`
- API/database changes: one new read-only API route; no database changes.
- Verification:
  - `pytest -q tests/test_full_lecture_contract.py tests/test_full_lecture_generator.py tests/test_full_lecture_api.py tests/test_pathly_annotated_content.py`: **17 passed**;
  - `py_compile pathly_server.py full_lecture_generator.py full_lecture_contract.py`: passed;
  - one existing Starlette/httpx deprecation warning only.
- Manual acceptance:
  1. Existing Today Learning and Annotated Source tabs should remain unchanged.
  2. The new route is parallel and is not yet linked from the UI.
- Known limitation: the running server must be restarted before the new route is reachable; v3 has not yet been rendered in the browser.
- Next step after confirmation: Step 4 — build a separate Full Lecture View v3 page/toggle for comparison.

## Full Lecture View v3 — Step 4: parallel comparison page (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Scope completed:
  - added a new `Full Lecture View v3` tab beside Study Blocks v1 and Annotated Source v2;
  - added client loading/error/retry states for the new endpoint;
  - rendered lecture overview, source-grounded sections, worked examples, misconceptions, takeaways, practice, knowledge check and source coverage;
  - kept v1 as the default and kept v2 available for direct comparison;
  - added `loadFullLecture` to the existing page state and window action surface.
- Files: `pathly-app.js`
- API/database changes: consumes the Step 3 read-only endpoint; no new tables.
- Verification:
  - `node --check pathly-app.js`: passed;
  - v3 contract/generator/API tests: **6 passed**.
- Manual acceptance:
  1. Restart the Pathly service so the new endpoint is loaded.
  2. Open Today Learning and click `Full Lecture View v3`.
  3. Compare it with `Study Blocks View v1` and `Annotated Source View v2`.
  4. Confirm fallback is visibly labeled when the model is unavailable.
- Known limitation: this is the first comparison UI; progress persistence and richer interactive lecture controls will be added in later steps.
- Next step after confirmation: Step 5 — improve v3 source material presentation and lecture interaction/persistence.

## Existing-path exact snapshot fallback and backend reload (2026-08-04, v75)

- Status: internally verified; pending user visual acceptance.
- Correction:
  - Dashboard now falls back to the confirmed onboarding draft snapshot when an older stored plan does not yet contain `knowledge_map`;
  - restarted the 4173 Pathly service so the server-side snapshot persistence logic is active;
  - corrected an existing UTF-8 label in the interpretation page.
- Verification:
  - `node --check pathly-app.js`: passed;
  - core frontend, planning API, Onboarding and workload regressions: 79 passed, 1 third-party warning;
  - running service serves `pathly-app.js?v=75` after restart.
- Known limitation:
  - if the onboarding draft itself was deleted, an old plan cannot reconstruct the preview snapshot; otherwise the dashboard now uses the saved draft snapshot.
## Read-only final map renderer fix (2026-08-04, v76)

- Status: internally verified; pending user visual acceptance.
- Root cause corrected:
  - the final dashboard passed preview edges into the graph renderer, but the renderer still recomputed reachability and excluded nodes using a different rule;
  - this could mark almost every non-primary node as excluded, especially for public-KG-only and private-material paths.
- Correction:
  - added an `exactSnapshot` rendering mode used only by a confirmed final map;
  - in this mode, active edges and excluded nodes are read directly from the confirmed preview snapshot with no secondary prerequisite, reachability, or role inference;
  - the same path applies whether the learner uses only Public KG, selected private materials, or a mixed source mode.
- Verification:
  - `node --check pathly-app.js`: passed;
  - core frontend, planning API, Onboarding and workload regressions: 80 passed, 1 third-party warning;
  - running service HTTP verification passed: homepage serves `pathly-app.js?v=76` with the exact-snapshot renderer.
## Full Lecture View v3 tab click hotfix (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Issue: the new v3 tab was rendered from a cached static asset, and the tab did not explicitly declare button behavior.
- Fix:
  - bumped `pathly-app.js` cache version from v76 to v77 in `index.html`;
  - added `type="button"` and `return false` to all daily-stage tabs;
  - preserved the latest v3 route, state and rendering implementation.
- Verification:
  - `node --check pathly-app.js`: passed;
  - served asset reference now points to `pathly-app.js?v=77`.
- Manual acceptance:
  1. Hard refresh the page (`Ctrl+F5`).
  2. Click `Full Lecture View v3`.
  3. The tab should switch immediately and show loading or the lecture/error state.

## Full Lecture View v3 click handling hotfix v78 (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Root cause addressed: inline stage-button handlers were unreliable after repeated full-page string re-renders and cache updates.
- Fix:
  - replaced inline `onclick` handlers with `data-daily-stage` attributes;
  - added a document-level event delegate that calls `window.setDailyStage(stage)`;
  - bumped `pathly-app.js` cache version to v78.
- Verification:
  - `node --check pathly-app.js`: passed;
  - source contains the delegated handler and all four stage buttons use `data-daily-stage`.
- Manual acceptance:
  1. Restart service if it is still serving the previous process.
  2. Hard refresh with `Ctrl+F5`.
  3. Click `Full Lecture View v3`; the stage should switch even if the API then reports an error or loading state.

## Full Lecture View v3 loading-state hotfix v79 (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Root cause: switching to v3 called `act(loadFullLecture)`, which replaced the entire application with the global `Pathly Is Working` screen while the API retried.
- Fix:
  - v3 now calls `loadFullLecture()` without global `act()`;
  - the v3 page renders immediately with its own loading/error state;
  - navigation and sidebars remain visible during API loading or failure;
  - bumped `pathly-app.js` cache version to v79.
- Verification:
  - `node --check pathly-app.js`: passed.
- Manual acceptance:
  1. Restart service and hard refresh (`Ctrl+F5`).
  2. Click `Full Lecture View v3`.
  3. The page should immediately switch to the v3 loading state, not the full-screen `Pathly Is Working` page.
  4. If the API is unavailable, v3 should show an inline retry message while navigation remains usable.

## Full Lecture View v3 stage-state hotfix v80 (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Root cause: `setDailyStage` handled only `quiz`, `annotated` and defaulted every other value to `content`; therefore clicking v3 immediately reset to v1.
- Fix:
  - explicitly added `lecture-v3` to the stage state mapping;
  - bumped `pathly-app.js` cache version to v80.
- Verification:
  - `node --check pathly-app.js`: passed;
  - source mapping now preserves `state.dailyStage === "lecture-v3"`.
- Manual acceptance:
  1. Restart service and hard refresh (`Ctrl+F5`).
  2. Click `Full Lecture View v3`.
  3. Confirm the v3 tab remains active and the v3 loading/content view appears instead of v1.

## Full Lecture View v3 — Step 5: section interaction and progress persistence (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Scope completed:
  - v3 now shows section-level learning progress (`completed / total` and progress bar);
  - each lecture section has a clear `Complete this section` action;
  - completed sections remain visually marked and can be reopened;
  - progress is persisted in the existing anonymous browser workspace state and restored after refresh;
  - source excerpts are expanded by default inside each section, with a clear instruction to read the source before using the explanation;
  - v3 keeps practice and knowledge-check areas below the lecture sections;
  - bumped `pathly-app.js` cache version to v81.
- Files: `pathly-app.js`
- API/database changes: none; this step uses browser persistence only and does not alter v1/v2 progress.
- Verification:
  - `node --check pathly-app.js`: passed;
  - v3 contract/generator/API tests: **6 passed**.
- Manual acceptance:
  1. Restart service and hard refresh (`Ctrl+F5`).
  2. Open Full Lecture View v3.
  3. Confirm each section shows a source excerpt and `Complete this section` button.
  4. Complete one section, refresh, and confirm its completed state and progress remain.
- Known limitation: section progress is currently browser-persisted; server-side cross-device persistence and true PDF page rendering/annotation are future steps.
- Next step after confirmation: Step 6 — connect section completion to server-side learning signals and build richer PDF/source navigation.

## Full Lecture View v3 — Step 6: server-side section progress (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Scope completed:
  - added SQLite table `full_lecture_section_progress`;
  - added read endpoint: `GET /api/plans/{plan_id}/days/{day}/full-lecture/progress`;
  - added write endpoint: `POST /api/plans/{plan_id}/days/{day}/full-lecture/sections/{section_id}/progress`;
  - validates that the requested section belongs to the learner's generated v3 lecture before saving;
  - v3 frontend now restores server progress on load and writes completion/reopen actions to the server;
  - browser persistence remains a safe local fallback if the service is temporarily unavailable;
  - bumped frontend asset version to v82.
- Files: `full_lecture_store.py`, `pathly_server.py`, `pathly-app.js`, `tests/test_full_lecture_store.py`.
- Verification:
  - `node --check pathly-app.js`: passed;
  - `py_compile pathly_server.py full_lecture_store.py`: passed;
  - v3 contract/generator/API/store tests: **7 passed**.
- Manual acceptance:
  1. Restart the service and hard refresh (`Ctrl+F5`).
  2. In Full Lecture v3, complete a section.
  3. Refresh and confirm the section remains complete.
  4. Open the same plan in a new tab and confirm the state is restored from the server.
- Next step after confirmation: Step 7 — PDF page-level rendering and source annotations, where a selected source becomes an actual document reading surface rather than only an excerpt.

## Full Lecture View v3 availability fallback hotfix (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- User-visible issue: v3 displayed `The requested Pathly resource was not found` for a learning day that could open v1.
- Root cause: v3 required an existing Annotated Source v2 session; missing v2 state incorrectly blocked v3, even when the daily v1 session existed.
- Fix:
  - Full Lecture v3 now uses v2 source data when available;
  - if v2 is unavailable, it generates a clearly labelled deterministic v3 lecture from the available daily v1 session instead of returning 404;
  - section progress endpoints are now loaded in the running service.
- Verification:
  - v3 contract/generator/API/store tests: **8 passed**;
  - `py_compile pathly_server.py full_lecture_generator.py`: passed;
  - restarted service OpenAPI verification: full lecture route = true; progress route = true.
- Manual acceptance:
  1. Hard refresh (`Ctrl+F5`).
  2. Click Full Lecture View v3 for the same learning day.
  3. It should now render a fallback lecture rather than show resource-not-found.

## Full Lecture View v3 refresh restoration hotfix v83 (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- User-visible issue: refreshing a v3 lecture restored only the empty `Preparing Full Lecture View v3` shell and required the learner to press Load again.
- Root cause: the app persisted section completion but not `selectedDay` or `dailyStage`; startup also did not auto-request v3 content after daily session restoration.
- Fix:
  - persist and restore `selectedDay` and `dailyStage`;
  - save stage selection immediately on tab switch;
  - during hydration, if the saved stage is `lecture-v3`, load the day and automatically request the full lecture;
  - bumped asset version to v83.
- Verification:
  - `node --check pathly-app.js`: passed;
  - source check confirms persisted day/stage and v3 hydration path.
- Manual acceptance:
  1. Open a v3 lecture and wait for its content to load.
  2. Refresh (`Ctrl+R` or `Ctrl+F5`).
  3. The same learning day and v3 lecture should reload automatically; no Load Full Lecture click should be needed.

## Full Lecture View v3 Step 7 — private PDF page reader and page-level source labels (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- User goal: replace excerpt-only source context with a real, page-level private PDF reading surface inside Full Lecture View v3.
- Changes:
  - Added `PrivateDocumentService.render_pdf_page(user_id, document_id, page)`, which verifies document ownership, validates page bounds, renders the owned PDF page through Poppler, and caches the PNG alongside the private source file.
  - Added `GET /api/documents/{document_id}/pages/{page}/render`; this route renders only a page from a document owned by the current anonymous user and responds with private-cache headers.
  - Full Lecture generator now preserves `document_id`, document title, and page range on each lecture section sourced from an annotated private reading.
  - Full Lecture v3 now displays the selected original PDF page inside its corresponding section, plus a separate bounded prepared excerpt and explicit page-range provenance.
  - Added a v3 tab loading fix: selecting Full Lecture View v3 immediately requests its content rather than leaving the learner at a preparation screen.
  - Bumped UI asset versions to `pathly-ui.css?v=69` and `pathly-app.js?v=85`.
- Security boundary:
  - A different anonymous user receives not-found semantics for another user's document; the public KG is never used as a storage location for these PDF renders.
- Verification:
  - `py_compile full_lecture_generator.py pathly_documents.py pathly_server.py`: passed.
  - `node --check pathly-app.js`: passed.
  - Focused regression suite: `pytest -q tests/test_full_lecture_generator.py tests/test_full_lecture_api.py tests/test_pathly_private_documents.py` — **12 passed**.
  - Wider relevant suite before the tab hotfix: **16 passed**.
  - Runtime OpenAPI after restart confirms full lecture, section progress, and PDF page-render routes are live.
  - Poppler render pipeline confirmed through a generated PNG in the private-document regression test. Direct visual-image inspection was blocked by the workstation sandbox helper, so no visual claim beyond the generated PNG and API/unit checks is made.
- Current limitation:
  - This is page-level source context with page labels; it does not yet draw coordinate-accurate highlight overlays on the PDF page. That requires storing text bounding boxes during PDF extraction, which is a separate follow-up step.
- Manual acceptance:
  1. Hard refresh the browser (`Ctrl+F5`) so `pathly-app.js?v=85` loads.
  2. Open a path that was created with ready private PDFs, then open **Full Lecture View v3**.
  3. For a section backed by one of those PDFs, expand **Read the selected PDF page**; the rendered page, document title, and selected page/range should appear in that section.
  4. Confirm the separate **prepared source excerpt** is readable and does not expose unrelated document pages.
  5. Open the same document page from a different anonymous session: it must not be available.
- Next step after acceptance: page-coordinate extraction and in-page highlight overlays, then deepen source-linked learner annotations.

### Step 7 compatibility follow-up (2026-08-04)

- Full Lecture v3 now also carries document/page metadata from a Daily Session's `required_resources` when it must use the v1 Daily Session fallback; PDF pages are therefore available for both annotated-source and older Daily Session paths where a block is linked to a required private resource.
- Asset version advanced to `pathly-app.js?v=86`; service restarted successfully.
- Regression rerun: `pytest -q tests/test_full_lecture_generator.py tests/test_full_lecture_api.py tests/test_pathly_private_documents.py` — **12 passed**.

## Non-disruptive generation status (2026-08-04, v87)

- Status: internally verified; pending user acceptance.
- Goal: every action that waits for a server response now gives immediate, clear feedback instead of looking like an unresponsive click.
- Changes:
  - Replaced the former full-page `Pathly Is Working` screen with a fixed in-page generation overlay.
  - The current page, its sidebar, and entered form values remain visible while a request runs; the overlay blocks duplicate clicks.
  - The overlay states that generation is in progress, includes a spinner, and is removed automatically on success or failure.
  - All existing `act(...)` API actions now use the shared state automatically; secure-session setup and Full Lecture generation are also covered explicitly.
  - Asset versions: `pathly-app.js?v=87`, `pathly-ui.css?v=70`.
- Verification:
  - `node --check pathly-app.js`: passed.
  - Full frontend/API regression: `pytest -q tests/test_pathly_frontend_v2.py tests/test_pathly_planning_api.py tests/test_pathly_onboarding_v2.py tests/test_pathly_workload.py`: pending rerun after the assertion update.
  - Live HTTP source check: pending rerun after the regression suite.
- Manual acceptance:
  1. Hard refresh the page.
  2. Trigger a server-backed action such as goal interpretation, workload generation, feasibility check, PDF upload, or Full Lecture generation.
  3. Confirm that the same page remains visible behind a centered “Generating...” card, repeated clicks are prevented, and the card disappears when the result or an error returns.
- Final verification completed:
  - `node --check pathly-app.js`: passed.
  - `pytest -q tests/test_pathly_frontend_v2.py tests/test_pathly_planning_api.py tests/test_pathly_onboarding_v2.py tests/test_pathly_workload.py`: **80 passed** (one upstream deprecation warning).
  - Live HTTP verification passed: the local server serves `pathly-app.js?v=87` containing both `showBusy` and `hideBusy`.
## Full Lecture quality Step 1 — source-to-concept alignment (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Goal: prevent an unrelated PDF page from being presented as teaching evidence for the scheduled knowledge node.
- Changes:
  - Annotated Content now scores every candidate source against the scheduled concept before creating a reading/lecture section.
  - The score uses specific concept terms, section/page text, retrieval relevance, and standard acronym support (for example, `RAG` matches `Retrieval-Augmented Generation`).
  - Broad labels with no specific anchor terms, or pages with no matching concept terms, are rejected rather than being forced into the lecture.
  - Source choice is now made per scheduled concept: matching private PDF first, then matching public material, otherwise an explicitly labelled generated fallback.
  - Each reading retains `source_alignment` metadata (`aligned`, `weak`, `rejected`, or `generated`) and its title follows the scheduled concept rather than an arbitrary PDF section heading.
- Expected result:
  - A section titled AI Applications will no longer select an XOR / linear separability page merely because it came from an uploaded PDF. If no page truly supports that broad topic, Pathly uses a transparent fallback instead.
- Verification:
  - `py_compile pathly_annotated_content.py`: passed.
  - `pytest -q tests/test_pathly_annotated_content.py tests/test_full_lecture_generator.py tests/test_full_lecture_contract.py tests/test_full_lecture_api.py`: **20 passed**.
  - Added regression cases for rejecting the AI Applications → XOR mismatch and retaining a matching Gradient Descent PDF page.
  - Service restarted and OpenAPI is available.
- Limitation:
  - This is deterministic lexical/metadata alignment, not an LLM semantic reranker yet. It deliberately favors refusing a dubious page over displaying a plausible-looking but misleading one.
- Manual acceptance:
  1. Hard refresh the browser (`Ctrl+F5`).
  2. Open Full Lecture v3 for the uploaded-PDF path.
  3. Confirm each shown PDF page has a section topic that visibly matches the page; in particular, the old AI Applications/XOR mismatch should not recur.
  4. If a matching page is unavailable, confirm Pathly shows transparent generated fallback content rather than a random private PDF page.
- Next accepted step: generate a real page-led lecture section around an aligned page (explain → read/observe → worked derivation/example → check → objective practice).

### Source alignment strengthening — page main-topic gate (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- User feedback: a Bagging diagram was still displayed under a Datasets section because the page contained the generic word `dataset`.
- Fix:
  - Added main-topic detection on page title and opening excerpt for concrete technical terms such as Bagging, Bootstrap, Ensemble, Gradient Descent, Neural Networks, XOR, Retrieval, Embedding, Transformer, and others.
  - A candidate now fails when its detected page main topic does not overlap with the scheduled concept's specific terms, even if generic context words overlap.
  - Example: Bagging/Bootstrap/Ensemble page → Datasets now produces an explicit generated fallback instead of showing the misleading PDF page.
  - Standard expansion/acronym matching remains supported (for example RAG ↔ Retrieval-Augmented Generation).
  - Advanced alignment version to `content-agent-v2-source-first-a7-page-topic-gate`, which causes old cached annotated sessions to regenerate; frontend asset advanced to `pathly-app.js?v=87`.
- Verification:
  - `py_compile pathly_annotated_content.py`: passed.
  - `pytest -q tests/test_pathly_annotated_content.py tests/test_full_lecture_generator.py tests/test_full_lecture_contract.py tests/test_full_lecture_api.py`: **21 passed**.
  - Added regression test: Bagging page with generic dataset wording is rejected for the Datasets concept.
  - Service restarted successfully and frontend JavaScript syntax check passed.
- Known boundary:
  - The current main-topic lexicon is deliberately conservative and deterministic. Semantic reranking across long documents is a later improvement, but this rule closes the exact false-positive shown in acceptance.
- Manual acceptance:
  1. Hard refresh (`Ctrl+F5`) to load `pathly-app.js?v=87`.
  2. Return to the same Full Lecture v3 learning day.
  3. The Datasets section must not render the Bagging page; it should show a transparent fallback or a genuinely dataset-specific page.

## Full Lecture quality Step 2 — page-led lecture generator (2026-08-04)

- Status: internally verified; **pending user acceptance**.
- Goal: turn an aligned source page into a learner-facing lecture sequence rather than a short explanation placed above an image.
- Changes:
  - Added `page_led_lesson` to every Full Lecture v3 section.
  - A normal section now includes a time budget that exactly matches its scheduled minutes, a prerequisite recap, why-this-page context, an observation prompt, guided source-reading steps, an annotated walkthrough of bounded source sentences, key terms, a worked reasoning example, an unscored knowledge check, and a transition to the next concept.
  - Full Lecture v3 UI now renders this sequence as a structured lesson around the selected page. The original private PDF page remains embedded at the read-and-observe step; the prepared excerpt is retained as a collapsed review aid.
  - Existing Daily Session fallback sections receive the same teaching structure, although their source-specific detail is naturally limited when no annotated page is available.
  - Added structural validation: the page-led time plan must sum exactly to the section's scheduled minutes. Very short sections use one compact focused-study phase instead of a misleading five-stage split.
  - Updated Full Lecture contract/generator version and asset versions to `pathly-ui.css?v=70` and `pathly-app.js?v=88`.
- Verification:
  - `node --check pathly-app.js`: passed.
  - `py_compile full_lecture_contract.py full_lecture_generator.py`: passed.
  - `pytest -q tests/test_full_lecture_contract.py tests/test_full_lecture_generator.py tests/test_full_lecture_api.py tests/test_pathly_annotated_content.py`: **22 passed**.
  - Tests verify walkthrough presence, knowledge-check content, normal time conservation, and one-minute edge behavior.
  - Service restarted successfully.
- Deliberate scope boundary:
  - The knowledge check is instructional in this step; it is not yet a scored interactive objective exercise. Page-coordinate highlight overlays and scored page-level interactions remain later steps.
- Manual acceptance:
  1. Hard refresh (`Ctrl+F5`) to load `pathly-app.js?v=88`.
  2. Open a Full Lecture v3 section backed by a matching PDF page.
  3. Confirm the page now sits inside a sequence: Why this page → Quick recap → Read and observe → Annotated walkthrough → Key terms → Worked example → Check your understanding → Carry this forward.
  4. Confirm the displayed phase minutes add up to the section's shown duration.
  5. Check that the walkthrough and example refer to the selected page/topic rather than generic Pathly or learning-method language.
- Next accepted step: PDF text/figure anchors and in-page highlight overlays.

## Full Lecture v3 Step 2 corrective pass - substantive teaching (2026-08-04)

- Status: internally verified; waiting for user acceptance.
- User acceptance note: the earlier page-led structure was rejected because its body remained teacher-facing and explanatory rather than teaching the knowledge itself.
- Privacy authorization: user explicitly allowed cleaned, bounded, concept-relevant PDF excerpts to be sent to the OpenAI API. Full PDFs and identity data are not included.
- Changes:
  - Added per-section live lecture generation grounded in the aligned PDF excerpt and upstream KG knowledge.
  - Added a quality gate for minimum teaching depth, concept relevance, at least two source walkthroughs, and a solved example with at least three steps.
  - Added rejection of Pathly/pedagogy/learning-method language and generic instructional meta phrases.
  - Failing sections are marked `source_coverage_insufficient`; they are no longer presented as a complete lecture.
  - Generator/cache version advanced to `full-lecture-live-teaching-v3`.
- Verification:
  - Python and JavaScript syntax checks passed.
  - Full Lecture + source alignment regression: 22 passed.
  - Real OpenAI synthetic validation (`Linear Separability`, 30 min): live/complete, 523 teaching words, 2 source walkthroughs, 3 worked steps, no banned meta language.
- Known limitation: generated lecture sections are cached in the running service process; durable server-side lecture caching remains a later hardening item.

## Full Lecture v3 corrective pass - remove fallback-as-source and Why this page (2026-08-04)

- Status: internally verified; waiting for user acceptance.
- Rejected behavior: generated fallback prose was being treated as source evidence, so the model expanded Pathly's own instructions instead of teaching domain knowledge.
- Changes:
  - `generated_fallback` is no longer exposed as a source, citation, document, excerpt, PDF page, Read and Observe block, or Annotated Walkthrough.
  - No-source sections use a knowledge-only generation prompt and receive only the concept definition as upstream context.
  - Added `concept_explanation` as the primary teaching body: overview, mechanism, assumptions/boundaries, and concrete example.
  - Added quality-gate rejection for `fallback source`, `learning concept in your path`, `no suitable source page`, and `start by asking`.
  - Removed the `Why this page` section from Full Lecture View v3.
  - Generator version advanced to `full-lecture-knowledge-first-v4`; browser asset advanced to v90.
- Verification:
  - Full Lecture contract/generator/API regression: 11 passed.
  - Real no-source OpenAI validation (`AI Applications`, 30 min): live/complete, 880 teaching words, 3 worked-example steps, concept mechanism present, no fallback/source-selection language.
  - JavaScript syntax passed; `Why this page` no longer exists in the application bundle.

## Full Lecture v3 hotfix - hide failed fallback and instant completion (2026-08-04)

- Status: internally verified; waiting for user acceptance.
- Diagnosis:
  - Mixed good/bad sections were not only historical cache. Sections that failed live generation or the quality gate still rendered the old deterministic worked example/check/transition.
  - `Complete this section` was slow because the progress endpoint regenerated the entire Full Lecture before validating the section ID.
- Changes:
  - Sections with `content_quality.status != complete` render no fallback teaching body; they show an explicit quality failure and retry action only.
  - Existing successful sections remain visible and cached while retries regenerate failed sections.
  - Completion uses optimistic UI: state changes immediately, then persists in the background.
  - Added a per-section saving guard and `Completed · Saving...` state.
  - Progress API validates deterministic section IDs from the stored annotated session and never calls the lecture generator.
  - Frontend asset advanced to v91.
- Verification:
  - Full Lecture generator/contract/API plus frontend regression: 63 passed, 1 warning.
  - Python and JavaScript syntax passed.
  - Permanent tests assert failed fallback is hidden, `Why this page` remains absent, optimistic state precedes the API call, and progress writes do not regenerate lectures.

## Full Lecture v3 retry closure - no fallback lesson body (2026-08-04)

- Status: internally verified; waiting for user acceptance.
- Product decision: when a Full Lecture section cannot pass live generation and quality validation, Pathly does not display a KG/template short lesson or any fallback teaching body.
- Changes:
  - Live generation now makes up to two section-level attempts; the second request receives the first validation failure as a repair instruction.
  - Added an authenticated per-section regenerate API; retrying one section does not rebuild or replace the rest of the lecture.
  - Failed sections now offer Retry now, Retry automatically later, Generate a more specific topic, View original PDF when available, and Continue to next section.
  - Automatic retry is persisted in the anonymous browser workspace and resumes after refresh; it performs one delayed attempt rather than looping or consuming model calls indefinitely.
  - A failed section cannot be marked complete and no hidden fallback body is rendered.
  - Frontend asset advanced to v92.
- API:
  - POST /api/plans/{plan_id}/days/{day}/full-lecture/sections/{section_id}/regenerate
- Verification:
  - Python and JavaScript syntax checks passed.
  - Focused Full Lecture generator/API/frontend regression: 61 passed, 1 warning.
  - Complete Pathly regression: 184 passed, 2 warnings.
  - Restarted the real service on 127.0.0.1:4173; /api/health returned live and session auth required.
  - Running service served pathly-app.js?v=92 and all finalized retry controls.
- Known limitation:
  - A retry still depends on a working model and sufficient knowledge/source context. If it continues to fail, Pathly deliberately leaves the section unavailable and offers the approved recovery actions instead of inventing a lesson.

## Full Lecture retry-control visual unification (2026-08-04)

- Status: internally verified; waiting for user acceptance.
- Unified Retry now, Retry automatically later, View original PDF, Continue to next section, and Generate this topic controls.
- All recovery buttons now share a 42px minimum height, 11px radius, consistent padding, typography, focus, hover, disabled, and responsive states.
- Retry now remains the primary action; non-destructive alternatives use the same secondary style.
- The specific-topic input and action are rendered as one aligned input group.
- Improved spacing between the unavailable title and explanatory copy.
- Active stylesheet advanced to pathly-ui.css?v=71.
- Verification: JavaScript syntax passed; frontend regression 51 passed, 1 warning; running service serves CSS v71.

## Full Lecture section time-plan UI removal (2026-08-05)

- Removed the learner-facing How to use these X minutes strip from every Full Lecture v3 section.
- Backend activity timing and section estimated minutes remain unchanged.
- Frontend asset advanced to v93.
- Verification: JavaScript syntax passed; frontend regression 51 passed, 1 warning; running service serves v93 without the removed text.

## 2026-08-05 — Full Lecture v3 retry flow closure

**Status:** Internally verified; awaiting user acceptance

### Problem closed
- Removed the learner-facing `Try a more specific knowledge topic` input and `Generate this topic` action. Curriculum topic selection remains owned by the confirmed plan and Content Agent.
- `Retry now` and automatic retry regenerate only the original scheduled concept and preserve the section identity.
- If source mapping changed while the page was open, the API now refreshes the unchanged annotated-session mapping and retries the equivalent section position.
- If that refresh cannot resolve the section safely, the API returns a recoverable `lecture_section_context_changed` response; the browser reloads the lecture rather than showing the misleading red 404 resource error.
- Missing plan/day resources still return a genuine 404.

### API and data changes
- Removed `topic_override` from the Full Lecture section regeneration payload and generator call.
- No database migration.

### Verification
- Full Python regression suite: `184 passed, 2 warnings`.
- Added frontend regression assertions that the removed topic prompt, button, and `topic_override` field are absent.
- Restarted the local FastAPI service on port 4173.
- Live HTTP verification: homepage 200, `pathly-app.js?v=94` served, removed controls absent, `Retry now` and `Retry automatically later` present.

### User acceptance steps
1. Press `Ctrl + F5` once.
2. Open `Full Lecture View v3` and locate an unavailable section.
3. Confirm there is no free-text topic field.
4. Use `Retry now`; it must retry the same scheduled concept.
5. Use `Retry automatically later`; reading and navigation must remain available.
6. Confirm no red `requested Pathly resource was not found` message appears merely because lecture source mapping was refreshed.

### Known limitation
- A retry can still remain unavailable when the model or suitable source evidence is unavailable. In that case Pathly does not fabricate a template lesson; the approved recovery choices remain automatic retry, original PDF when available, and continuing to the next section.

## 2026-08-05 — Full Lecture related-page sequence upgrade

**Status:** Internally verified; awaiting user acceptance

### Product change
- Upgraded source grounding from a single `page_start/page_end` anchor to an ordered `page_sequence`.
- Each scheduled concept still chooses the strongest aligned anchor page, then adds only nearby pages from the same PDF when they are topic-aligned or belong to the same source section.
- The sequence is ordered by page number, de-duplicated, and bounded to six pages. Unrelated or distant keyword matches are not included.
- Historical content with only `page_start/page_end` remains readable; the compatibility layer expands an existing range into a page sequence.

### Content Agent change
- Annotated Source Agent version: `content-agent-v2-source-first-a8-related-page-sequence`.
- Full Lecture Generator version: `full-lecture-related-pages-v5`.
- The generator combines clean evidence across the selected sequence rather than teaching from only the anchor chunk.
- Every selected page receives a learner-facing guide containing its role (`context_before`, `anchor`, or `context_after`), purpose, bounded key claims, and transition to the next page.
- Existing source alignment gates remain active, so an unrelated page is excluded instead of being presented as supporting evidence.

### UI change
- Replaced the single-page image with a related-page PDF reader.
- Added page chips, Previous page, Next page, anchor-page labeling, per-page explanation, key claims, and page-to-page transition text.
- The reader displays one high-resolution page at a time to avoid loading every PDF page simultaneously, while all selected related pages remain directly reachable.
- Static assets advanced to `pathly-app.js?v=95` and `pathly-ui.css?v=72`.

### Compatibility and storage
- No SQLite migration was required because annotated sessions and Full Lecture payloads are stored as JSON.
- Old `page_start/page_end` fields remain in the response for compatibility; `page_sequence` is now the authoritative multi-page field for new content.
- The Annotated Agent and Full Lecture Generator version bumps invalidate outdated cached generation for unfinished content.

### Verification
- Multi-page focused suite: `79 passed, 1 warning`.
- Full Pathly regression: `185 passed, 2 warnings`.
- Python and JavaScript syntax checks passed.
- Local service restarted on port 4173.
- Live HTTP verification: homepage 200; app v95 and CSS v72 served; page sequence, Previous page, and Next page controls present.

### User acceptance
1. Press `Ctrl + F5`.
2. Open Today Learning → Full Lecture View v3.
3. Open a section grounded in a private PDF.
4. Confirm `Read selected source pages` shows page chips and identifies the anchor page.
5. Use Previous page / Next page and confirm the PDF image, page purpose, key claims, and transition update together.
6. Confirm unrelated pages are not added merely because they contain a generic term.

### Known boundary
- The sequence can only use pages present in the retrieved evidence candidates. It currently checks up to the private retrieval result set and does not yet scan every page of every uploaded PDF at lecture-request time. This keeps latency bounded and prevents broad keyword matches from overwhelming the lesson.

### 2026-08-05 follow-up — Missing PDF reader diagnosis

- User acceptance reported that `Read selected source pages` was not visible.
- Read-only production-data audit confirmed the currently selected plan `cb7ee511-dc68-47b3-af38-4316abf0a15f` uses path `563d4754-69c5-4da8-97f7-ad51da7f3283`, which has zero rows in `path_document_links`.
- Its current A8 annotated session correctly contains one `public_rag` reading with no `document_id` and an empty `page_sequence`; therefore no private-PDF reader can be rendered.
- A separate earlier path for the same goal (`4b2246e0-6878-48f1-b6c9-3e7349307d83`) is linked to four private PDFs.
- Added explicit Full Lecture status messaging: either `PDF source sequence available` with the number of grounded sections, or `No uploaded PDF is linked to this learning path` with recovery guidance. This replaces silent disappearance of the reader.
- Advanced the app asset to `pathly-app.js?v=96`.
- Verification: JavaScript syntax passed; focused frontend/lecture/annotated suite `74 passed, 1 warning`; service restarted on port 4173.

## 2026-08-05 - Source-Grounded Lecture View v4 / S0 isolated baseline

**Status:** Awaiting user acceptance

### Objective
Create a fully isolated v4 pilot surface without changing the existing Study Blocks v1, Annotated Source v2, Full Lecture v3, planning, KG, Chroma, or formal learning progress.

### Delivered
- Added the `Source-Grounded Lecture View v4` tab in Today Learning, behind `PATHLY_LECTURE_V4_ENABLED`.
- Added separate v4 rendering state, current section restoration, scroll restoration, and independent completion state.
- Added explicit return actions to Full Lecture v3 and Study Blocks v1, plus a reload action.
- Added a detached SQLite store for v4 lecture records and v4 progress. It does not write v1, v2, v3, daily completion, Quiz, next-day unlock, or Adaptation state.
- Added separate v4 APIs: read, generate, section completion, and isolated retry.
- v4 currently uses a detached v3 snapshot only as the S0 baseline; source-linking, verified sources, and v4-quality generation begin in later stages.

### API and data
- `GET /api/plans/{plan_id}/days/{day}/lecture-v4`
- `POST /api/plans/{plan_id}/days/{day}/lecture-v4/generate`
- `POST /api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/complete`
- `POST /api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/retry`
- New SQLite tables: `source_grounded_lecture_v4`, `source_grounded_lecture_v4_progress`.
- Added production-safe configuration guidance: `.env.example` defaults `PATHLY_LECTURE_V4_ENABLED=false`; the local pilot may opt in.

### Verification performed
- Python syntax: passed for `pathly_server.py` and `source_grounded_v4_store.py`.
- JavaScript syntax: passed for `pathly-app.js`.
- New v4 focused suite: `5 passed, 1 warning`.
- Existing v3 lecture suites: `14 passed`.
- Full regression: `190 passed, 2 warnings` (third-party deprecation warnings only).
- Local service restarted and `/api/capabilities` reported `source_grounded_lecture_v4.available=true`, stage `s0_isolated_baseline`.
- A separate feature-flag test reported `available=false` when `PATHLY_LECTURE_V4_ENABLED=false`. The unauthenticated direct route test returned the expected session-protection `401` before route access, so it did not alter any user data.

### Manual acceptance steps
1. Hard refresh the local page.
2. Open Today Learning and select `Source-Grounded Lecture View v4`.
3. Confirm the S0 isolated-baseline label and the return buttons appear.
4. Complete one v4 section, return to v3, and confirm v3 progress is unchanged.
5. Return to v4 and refresh. Confirm the active v4 section and v4 completion state remain.
6. Confirm v4 does not unlock another day and does not change the formal Quiz/Adaptation flow.

### Known boundary
S0 intentionally does not claim improved source quality. It is a safe, removable experiment shell. S1 will add the read-only source-linking index; S2 will establish the verified Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent golden path.

### S0 hotfix - v4 tab direct action (2026-08-05)

**Status:** Awaiting user acceptance

- User reported that the `Source-Grounded Lecture View v4` tab did not respond to clicks.
- Removed the fragile document-level delegated click handler for daily view tabs.
- Each tab now calls `setDailyStage(...)` directly, so dynamic page rendering cannot disconnect the v4 action.
- Advanced the application asset to `pathly-app.js?v=98` and restarted the local service.
- Verification: JavaScript syntax passed; focused v4 and frontend suite `56 passed, 1 warning`; live homepage serves v98 and capabilities report v4 available.
- Manual acceptance: hard refresh once, then choose `Source-Grounded Lecture View v4`; the tab must immediately become active and show the v4 preparation screen or stored isolated lecture.

### S0 hotfix - loading layer no longer blocks v4 navigation (2026-08-05)

**Status:** Awaiting user acceptance

- User still could not activate the v4 tab after the direct-action fix.
- Root cause addressed: the full-screen busy layer was capturing pointer events during asynchronous preparation.
- Added `pathly-interaction-fix.css`: the status layer is now pointer-transparent; only its status card remains interactive.
- v1 and v2 were not otherwise changed; future work will focus on v3/v4.
- Verification: focused v4/frontend suite `56 passed, 1 warning`; JavaScript syntax passed; live homepage serves the interaction fix stylesheet and app v98.
- Manual acceptance: hard refresh, click v4 while preparation is visible, and confirm the tab changes immediately instead of waiting for the request to finish.

### S0 hotfix - direct pointer activation for v4 (2026-08-05)

**Status:** Awaiting user acceptance

- User confirmed the v4 tab remained inert; the issue was treated as an interaction-layer problem, not a v4 content/API problem.
- Added direct `pointerdown` activation to the v4 stage control and an independent capture listener (`pathly-v4-click-fix.js`) loaded after the main application.
- v1/v2 were not otherwise changed; future implementation scope is v3/v4 only.
- Verification: focused v4/frontend suite `56 passed, 1 warning`; JavaScript syntax passed; live homepage serves the v4 click-fix script.
- Manual acceptance: hard refresh, click the v4 tab, and confirm the active tab changes immediately.

## 2026-08-05 — v4 native navigation hotfix

- Status: internal verification passed; awaiting user acceptance.
- Root cause: the v4 tab still depended on a `pointerdown` handler while its normal click was explicitly cancelled. The temporary global click-fix script also intercepted the same interaction path.
- Change: replaced the v4 tab with a native link to `/?daily_view=lecture-v4`; startup now restores `lecture-v4` from the URL; removed the old global interception script; added matching link active-state styling; bumped static assets to `pathly-app.js?v=100` and `pathly-ui.css?v=74`.
- Scope: v3/v4 only. No work was added to deprecated v1/v2.
- Verification: `node --check pathly-app.js` passed; `pytest tests/test_pathly_server.py tests/test_source_grounded_lecture_v4.py -q` passed (11 tests); live HTTP verified App v100, absence of old click-fix script, native v4 link, and URL restoration logic.
- Manual acceptance: refresh the homepage, click Source-Grounded Lecture View v4, and confirm the URL contains `daily_view=lecture-v4` and the v4 page remains after refresh.

## 2026-08-05 — v4 route context restoration hotfix

- Status: internal verification passed; awaiting user acceptance.
- User evidence: native URL changed to `daily_view=lecture-v4`, but reload returned to Learning Paths with a previous-lesson restoration warning.
- Root cause: full-page navigation discarded the currently selected plan. Hydration then selected the first plan in the list and attempted to restore the old selected day against the wrong path.
- Change: v4 URLs now carry `plan_id` and `day`; startup restores both before loading Today Learning; the selected plan is now persisted for future refreshes and v3/v4 navigation; static app bumped to v102.
- Verification: JavaScript syntax passed; server/v4 tests passed (11); live HTTP previously verified static asset delivery and URL restoration markers.
- Acceptance: refresh, select the intended learning path once, open an unlocked day, then click v4. The URL must include `daily_view`, `plan_id`, and `day`; v4 must remain selected after refresh.

## 2026-08-05 — S0 acceptance blocker: independent v4 route loader

- Status: internal verification passed; S0 remains awaiting user acceptance.
- Acceptance failure: selecting v4 changed the URL but hydration returned to Learning Paths because the shared Today Learning loader attempted to restore/generate v1 session content and chat before loading v4.
- Root cause: v4 navigation was visually separate but its startup path was not operationally isolated from the legacy daily-content initialization branch.
- Change: introduced `loadV4RouteContext()` to restore only the selected plan, active/unlocked day, progress context, and v4 data. A URL request for `lecture-v4` now bypasses v1 session/content/chat initialization. Errors stay on the v4 error state rather than redirecting to Dashboard. Static app version is v103.
- Regression maintenance: updated stale asset-version assertions only; no v1/v2 product work was added.
- Verification: JavaScript syntax passed; v4/server focused tests 11 passed; frontend tests 51 passed; complete regression 190 passed; live HTTP confirmed v103 and the independent v4 loader.
- Manual acceptance still required: enter v4, complete one v4 section, return to v3 and confirm v3 progress is unchanged, return to v4 and refresh, confirm v4 section and scroll state restore.

## 2026-08-05 — S0 acceptance blocker: false No Active Learning Path during v4 startup

- Status: internal verification passed; S0 still awaits user acceptance.
- User evidence: URL correctly contained `daily_view=lecture-v4`, `plan_id`, and `day`, but the page displayed `No Active Learning Path`.
- Root causes: the app rendered Today Learning before asynchronous plan restoration completed; additionally, the URL plan version may be absent from the deduplicated latest-plan list.
- Change: v4 startup is now atomic after anonymous-session initialization. It directly reads the URL `plan_id` when needed, restores the requested day, loads v4, then reveals the page. During restoration it shows a dedicated v4 restoring state instead of the false empty-path state. Static app version is v104.
- Verification: JavaScript syntax passed; focused frontend/server/v4 suite 62 passed; complete regression 190 passed; live HTTP confirmed v104, direct plan loading, atomic v4 branch, and restoring screen.
- Manual acceptance remains required before S0 can be marked accepted.

## 2026-08-05 - S0 acceptance blocker: anonymous-session startup no longer resets v4 to workspace

- Status: fixed in code, awaiting the user's retry.
- Root cause: `startSecureSession()` changed the anonymous user id during the first load, then forced `state.view` back to `workspace` whenever the old view was `today` or `dashboard`. That broke the `lecture-v4` deep link before the v4 loader could finish.
- Change: preserved the `today` view when the requested route is `lecture-v4`, so the v4 restoring branch can continue after the anonymous session is created.
- Verification: JavaScript syntax still passes. The frontend cachebuster was also bumped to `pathly-app.js?v=105` so the fix is actually loaded in the browser.
- Scope: S0 only. v1/v2/v3 behavior was not changed.

## S0 repair — direct v4 deep-link restoration

- Status: internally verified; awaiting user acceptance.
- Root cause: the lecture-v4 route awaited documents, draft and profile initialization before resolving the selected plan/day. A blocked unrelated request left the route indefinitely on “Restoring”.
- Change: v4 now restores only the linked plan and requested day, then loads the isolated v4 snapshot. Capability discovery runs in the background; documents, draft, profile and active-path progress are not dependencies of S0 entry.
- Isolation: this does not change v1/v2/v3 data, progress, or planning state.
- Verification: 
ode --check pathly-app.js passed. Client cache revision: v106.
- S0 follow-up: v4 route restoration now has a 12-second failure boundary and transitions into the v4 page before isolated snapshot generation begins; cache revision v107; JavaScript syntax check passed.

## S1 — Rebuildable Source Linking Index

- Status: internally accepted; awaiting user acceptance of the v4 entry and S1 result.
- Added a SQLite sidecar table `concept_source_links`, scoped by anonymous user, plan and day.
- The index stores Concept, Resource, Document, ordered page sequence, chunk IDs, scope, relevance, coverage, match method, review status, reason and source version.
- Links are projected from existing source metadata only. S1 does not write to Neo4j, public/private Chroma, document chunks, Planning, or v3 payloads.
- Unreliable sources are explicitly marked `unlinked`; no PDF is fabricated.
- v4 generation now stores an independent `source-link-s1-v1` snapshot and exposes `GET /api/plans/{plan_id}/days/{day}/lecture-v4/source-links`.
- S0 entry hardening: unrelated startup dependencies were removed, restoration has a 12-second request boundary plus a 15-second UI watchdog, and v4 generation is shown as a separate state.
- Runtime correction: two competing Pathly service instances were replaced by one logical uvicorn service, eliminating random delivery of stale frontend code.
- Verification: JavaScript and Python syntax passed; S1/v4/front-end acceptance group 58 passed; complete regression 192 passed with 2 dependency deprecation warnings; live `/api/health`, v108 asset, watchdog and source-links route verified.
- Browser automation could not start because the Windows desktop browser helper returned OS logon error 1385. Manual browser acceptance remains required.
## 2026-08-08 - S0 v4 isolated acceptance entry hotfix

Status: internally accepted; awaiting user visual acceptance.

- Root cause: `daily_view=lecture-v4` still booted the main SPA and could remain indefinitely in its path/day restoration state.
- Added standalone `lecture-v4.html` and `lecture-v4.js`; the exact v4 acceptance URL is now dispatched by FastAPI before the main SPA loads.
- The standalone view creates/resumes the anonymous session, loads the isolated v4 snapshot, generates only when absent, renders `lecture_sections`, and writes only v4 progress.
- Added `/lecture-v4.js` static route. Normal `/` continues to serve `index.html`; v3 and historical state were not modified.
- Live verification: exact acceptance URL HTTP 200, standalone marker present, standalone script present, old `Restoring Source-Grounded` text absent, health HTTP 200.
- Tests: focused v4 entry/S0/S1 suite `10 passed`; full regression `195 passed, 2 dependency warnings`.
- Service: restarted on `127.0.0.1:4173` with `PATHLY_LECTURE_V4_ENABLED=true` and session authentication enabled.
- Browser-control automation could not attach because Windows returned `CreateProcessWithLogonW 1385`; user visual acceptance remains required.

## 2026-08-08 - v4 product-page rendering correction

- User acceptance found that the isolated route exposed an engineering/debug baseline with unstyled controls and placeholder text.
- Added a dedicated responsive Pathly v4 visual shell so the isolated route remains independent without looking like a raw document.
- Replaced debug fields (`S1 source-link status`, `isolated baseline`) with product-facing Source Coverage.
- The v4 renderer now displays available lecture content from `lecture_sections`: core explanation, mechanism, boundaries, guided observation, worked example, misconceptions, knowledge check, takeaway, selected page sequence, and isolated v4 completion state.
- Cachebuster updated to `lecture-v4.js?v=2`.
- Focused regression: `10 passed, 1 dependency warning`.
- Live verification: HTTP 200; dedicated v4 style served; v2 script served; actual lecture renderer present; debug status text absent.
- Boundary: S0/S1 still use an isolated v3 read-only snapshot plus the S1 source-link index. Truly new source-grounded lecture generation is S4 and is not being claimed complete.

## 2026-08-08 - S0 v4 in-page tab restoration

- Status: in progress.
- Scope: remove the standalone v4 route and restore v4 inside Today Learning; S1 has not started.


### S0 completion

- Status: awaiting user acceptance.
- Removed the standalone `lecture-v4.html` / `lecture-v4.js` entry and its server routing.
- v4 now uses the same in-page `<button>` tab interaction as v3 through `setDailyStage('lecture-v4')`.
- URL state is synchronized with `history.replaceState`; refresh restores URL `plan_id`, `day`, and v4 stage through normal Today Learning hydration.
- v4 GET/generate now uses a local in-page loading state; it no longer opens the global blocking overlay or requires a second Load click.
- v4 errors remain in the Today Learning shell with Retry and Return to v3 actions.
- v4 progress storage and completion endpoints remain independent from v3, Quiz, day unlocking, and Adaptation.
- Static asset cache revision: `pathly-app.js?v=109`.
- Focused verification: JavaScript syntax passed; Python syntax passed; 59 focused tests passed.
- Full regression: 195 passed; 2 dependency deprecation warnings.
- Live verification: health 200; v4 acceptance URL 200 and serves the main app; old standalone marker absent; `/lecture-v4.js` returns 404.
- Automated visual inspection could not start because the Windows browser helper returned OS logon error 1385. Manual user acceptance is required.
- S1 status for this approved sequence: not started. It will begin only after the user accepts S0.

### S0 user-acceptance blocker: v4 tab click parity

- User acceptance failed because v4 still did not react to clicks.
- All daily version tabs now use one shared DOM event binding; v4 no longer has a special inline click path or experimental dashed styling.
- v4 action handlers are explicitly exposed with the existing page handlers.
- Cache revision bumped to v110; S1 remains not started.

- Final implementation: all Daily Learning tabs, including v3 and v4, now use the same post-render DOM event listener. No v4-specific navigation handler remains.
- Removed v4-only dashed tab styling and obsolete anchor styling.
- Exposed v4 page actions alongside existing global UI handlers.
- Verification: 59 focused tests passed; complete regression 195 passed; live service serves `pathly-app.js?v=110`.
- Status remains awaiting user acceptance; S1 has not started.

## 2026-08-09 — S0 white-screen root-cause fix (awaiting user acceptance)

- Status: S0 implementation repaired; awaiting manual acceptance. S1 has not started.
- Root cause: the v4 functions were accidentally inserted inside `loadFullLecture()`. The browser then referenced `loadLectureV4`, `toggleV4Section`, and `retryLectureV4Section` as global handlers during startup, causing a runtime `ReferenceError` and a completely blank page.
- Fix: rebuilt the `loadFullLecture()` boundary and moved all v4 functions back to top-level scope. v4 remains an in-page Today Learning tab and uses the same shared tab event binding as v3.
- Cache: `pathly-app.js?v=111`.
- Regression protection: added a test that asserts the v3 loader closes before the v4 function block and that v4 handlers are declared exactly once.
- Syntax gate: `node --check pathly-app.js` passed.
- Focused tests: 9 passed (`test_lecture_v4_entry.py`, `test_source_grounded_lecture_v4.py`).
- Full regression: 196 passed, 2 dependency deprecation warnings.
- Live service verification: `/api/health` 200, `/` 200, `/pathly-app.js?v=111` 200; served asset contains the top-level v4 loader and no malformed nesting.
- Browser automation note: direct automated visual verification could not start because the Windows browser helper returned `CreateProcessWithLogonW 1385`; this is an environment limitation, not a Pathly HTTP failure. Manual acceptance remains required.
## 2026-08-09 — S0 user acceptance / S1 started

- S0 status: user accepted.
- S1 status: in progress.
- Scope: read-only Concept → Resource/Document → ordered PDF page source-link index, v4 source-status presentation, session isolation, and deletion cleanup only.
- Explicit exclusions: no S2–S4 lecture generation, no v1/v2/v3 changes, no Quiz/day-unlock/Adaptation changes.
## 2026-08-09 - S1 read-only Source Linking Index complete

- Status: internal acceptance passed; awaiting user acceptance. S2 has not started.
- S0 acceptance: confirmed by the user before S1 began.
- Scope completed: a rebuildable SQLite sidecar index linking each v4 concept to an existing Resource/Document and an ordered, continuous PDF page sequence.
- Isolation: no writes were made to Neo4j, public/private Chroma, original PDFs, Planning data, v1/v2/v3 content, Quiz, day unlocking, or Adaptation.

### Implementation

- Upgraded the sidecar contract to `source-link-s1-v2` with anonymous-user, plan, day, concept, resource, document, source scope, ordered pages, chunk IDs, relevance, coverage, match method, explanation, status, and version metadata.
- Added conservative thresholds: relevance >= 0.75 and coverage >= 0.60.
- Source candidates now reuse prepared daily evidence and required/optional resource metadata that already came through the existing KG/RAG/private-document pipeline.
- Disconnected retrieval pages are reduced to the strongest continuous run instead of being presented as one artificial sequence.
- Unreliable or unrelated evidence is stored as `unlinked`; its page sequence and chunk IDs are cleared so v4 cannot display an unrelated PDF page.
- Link IDs are scoped per anonymous user, plan, and day.
- Deleting a private PDF removes only that owner's matching S1 links and invalidates only that owner's v4 snapshots/progress that reference the document.
- Old v4 snapshots without `source-link-s1-v2` and `source_link_status=indexed` are automatically regenerated on entry.

### API and UI

- `GET /api/plans/{plan_id}/days/{day}/lecture-v4/source-links` now returns links grouped for user-facing section display.
- v4 sections show one of:
  - Verified/linked source available;
  - public or private source scope;
  - document title;
  - continuous page range;
  - why the source was selected;
  - source coverage summary;
  - or `No reliable source yet`.
- Numeric matching scores, database fields, and engineering/debug text are not shown in the product UI.
- S1 remains an index/status stage. It does not claim that the new source-grounded lecture generator is complete.
- Static revisions: `pathly-app.js?v=112`, `pathly-ui.css?v=75`.

### Verification

- Python syntax: passed for `source_linking_index.py`, `source_grounded_v4_store.py`, and `pathly_server.py`.
- JavaScript syntax: `node --check pathly-app.js` passed.
- Focused S1/v4 tests: 16 passed.
- Complete regression: 201 passed; 2 dependency deprecation warnings; 0 failures.
- Live service restarted successfully on `127.0.0.1:4173`.
- Live health/capabilities: HTTP 200; v4 reports `s1_read_only_source_index`; SQLite, JSON KG, ChromaDB, Neo4j, and private-document capabilities report available.
- Live assets: homepage, `pathly-app.js?v=112`, and active S1 stylesheet are served successfully.
- Existing stored learning-day validation: `source-link-s1-v2`, 3 usable links, 1 unlinked concept, and all returned page sequences continuous.

### Known boundary

- S1 establishes reliable, explainable source links only. It does not yet generate the new page-led v4 lecture content. That work begins in S2 only after user acceptance.
- A current learning day may legitimately show `No reliable source yet` when its existing evidence does not meet the threshold. This is expected and is safer than showing an unrelated page.

### Manual acceptance

1. Hard refresh `http://127.0.0.1:4173/?v=112`.
2. Open Today Learning and choose `Source-Grounded Lecture View v4`.
3. Confirm v4 stays inside the normal Today Learning shell with the same sidebar and Ask Pathly panel.
4. For each section, confirm it shows either a linked public/private document with a continuous page range and reason, or `No reliable source yet`.
5. Confirm no unrelated PDF page is displayed and no numeric engineering score appears.
6. Return to Full Lecture v3 and confirm its progress is unchanged.
7. Refresh while in v4 and confirm the v4 tab and independent completion state are restored.

## 2026-08-09 - S1 provenance page backfill complete

- Status: internal acceptance passed; awaiting user acceptance. S2 has not started.
- Source-link contract upgraded to `source-link-s1-v3`.
- Tail item closed: Daily evidence is no longer marked `unlinked` merely because it lacks page metadata.
- Recovery order:
  1. reuse page metadata already present in Daily evidence;
  2. query the configured Neo4j concept context for linked Resource records;
  3. if Neo4j is unavailable, query the calibrated JSON KG without modifying it;
  4. retrieve existing public Chroma chunks within each candidate Resource;
  5. locate the original offline source PDF from Resource metadata/build manifests;
  6. align relevant Chroma chunk text to actual extracted PDF-page text;
  7. retain only a conservative continuous page run;
  8. mark `unlinked` only if no real page sequence passes the checks.
- The recovery is read-only. It does not write to Neo4j, Chroma, source PDFs, v1/v2/v3 content, Planning, Quiz, unlocking, or Adaptation.
- Page numbers are derived from actual PDF page extraction and text alignment; chunk order is never treated as a page number.
- Public recovered documents use a stable `public:<resource_id>` identity in the sidecar index.
- v4 generation and section retry both run provenance recovery in a worker thread, so PDF inspection does not block the event loop.

### Verification

- Python syntax: passed for `source_provenance_backfill.py`, `source_linking_index.py`, and `pathly_server.py`.
- Focused source-link/provenance tests: 7 passed.
- Full regression: 203 passed; 2 dependency deprecation warnings; 0 failures.
- Real-data check: the previously page-less Classification resource `cs224n-2026-lecture03-neuralnets.pdf` recovered a continuous sequence on pages 10-13 from existing public Chroma chunks and the original offline PDF.
- Failure check: relevant chunks paired with unrelated PDF pages remain `unlinked`.
- Current environment note: live Neo4j was not reachable during the real-data check; recovery continued through the calibrated JSON/daily Resource identity and public Chroma as designed. It was not reported as a live Neo4j result.

### Manual acceptance

1. Refresh Pathly and open Today Learning -> Source-Grounded Lecture View v4.
2. Regenerate/reload the current v4 snapshot so it uses `source-link-s1-v3`.
3. Confirm a section that previously showed no page solely because Daily evidence lacked page metadata now shows the recovered document and continuous page range.
4. Confirm genuinely unsupported concepts still show `No reliable source yet`.
5. Return to v3 and confirm its content and progress are unchanged.


### Live activation addendum

- Pathly was restarted with the project virtual environment and is listening on port 4173.
- Live checks after restart: `/api/health` HTTP 200 and `/` HTTP 200.
- The first restart attempt reused an obsolete `D:\py11\python.exe` command that no longer contained FastAPI; it was replaced immediately with the configured project virtual environment. No product data was changed.


## 2026-08-09 - v4 S2 verified golden path started

- Status: in progress.
- Scope: verify real source coverage for Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent.
- Safety boundary: no writes to Neo4j, the existing public/private Chroma collections, Planning, v1/v2/v3, Quiz, unlocking, or Adaptation.
- Audit finding: the strongest XOR/linear-separability source (06_mlp.pdf) exists in the offline KG build artifacts but is absent from the current public Chroma collection. S2 will register it only in the removable v4 verified-source sidecar and will not mislabel it as public-Chroma indexed.

## 2026-08-09 - v4 S2 verified golden path complete

- Status: internal acceptance passed; awaiting user acceptance. S3 has not started.
- Completed at: 2026-08-09 03:11:40 +08:00.
- Scope completed: verified, read-only source bindings for Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent in the isolated v4 sidecar.
- Safety boundary preserved: no writes to Neo4j, public/private Chroma, original PDFs, Planning, v1/v2/v3 content or progress, Quiz, next-day unlocking, or Adaptation.

### Implementation

- Added erified_golden_sources.py, which validates every registered source against the actual PDF manifest, SHA identity, page bounds, and required page text before returning erified.
- Upgraded the sidecar contract to source-link-s2-v1.
- Verified sources override weaker Daily evidence only for exact golden-path concepts; unrelated topics remain unlinked.
- Added persisted S2 metadata: source readiness, golden-path position, and golden-path version.
- Added an additive SQLite migration; the sidecar remains deletable and rebuildable.
- v4 snapshots now use source-grounded-v4-s2-verified-v1 and include a read-only golden-source audit. Existing v3 snapshots and progress remain untouched.
- Added GET /api/lecture-v4/golden-path and extended the day source-links response with readiness and golden-path version.
- v4 now displays the five verified source bindings and distinguishes Public retrieval index ready from Verified offline KG resource; public retrieval index pending.
- Static revision: pathly-app.js?v=113.

### Verified source chain

- Linear Separability:  6_mlp.pdf, pages 2-3, verified offline KG resource.
- XOR:  6_mlp.pdf, pages 2-7, verified offline KG resource.
- Neural Networks: cs224n-2026-lecture03-neuralnets.pdf, pages 13-14, public Chroma ready.
- Activation Functions: cs224n-2026-lecture03-neuralnets.pdf, pages 15-17, public Chroma ready.
- Gradient Descent: cs224n-2026-lecture03-neuralnets.pdf, pages 18-20, public Chroma ready.

### Verification

- Python syntax: passed for the S2 registry, source index, v4 store, server, and tests.
- JavaScript syntax: 
ode --check pathly-app.js passed.
- Focused S2/source-link/provenance/v4 tests: 17 passed; 1 dependency deprecation warning.
- Complete regression: 206 passed; 2 dependency deprecation warnings; 0 failures.
- Real PDF audit: 5/5 golden concepts verified from actual extracted page text.
- Anonymous-session API check: GET /api/lecture-v4/golden-path returned HTTP 200 with 5/5 verified.
- Live service restarted on 127.0.0.1:4173; capabilities report s2_verified_golden_path; homepage serves v113.
- Automated visual browser control could not start because the Windows browser helper returned CreateProcessWithLogonW 1385. This environment limitation does not affect the running Pathly service; manual visual acceptance is required.

### Known boundary

- S2 verifies source identity and continuous page coverage only. It does not yet generate the new source-grounded lecture. New v4 teaching content remains S4; private-PDF source association remains S3.
-  6_mlp.pdf is verified from immutable offline KG build artifacts but is not yet in the current public Chroma collection. The UI states this explicitly and does not claim live public retrieval readiness.
- A non-golden-path concept remains unlinked unless the S1 provenance chain independently finds reliable pages.

### Manual acceptance

1. Hard refresh http://127.0.0.1:4173/?v=113.
2. Open Today Learning and choose Source-Grounded Lecture View v4.
3. Confirm the S2 verified source-chain panel lists all five concepts and the page ranges above.
4. Confirm Linear Separability/XOR say the offline KG resource is verified but public retrieval indexing is pending.
5. Confirm Neural Networks/Activation Functions/Gradient Descent say the public retrieval index is ready.
6. Confirm unrelated current-day concepts can still show No reliable source yet rather than an unrelated PDF.
7. Return to v3 and confirm its content/progress are unchanged.
## 2026-08-09 - v4 S3 private source association complete

- Status: internal acceptance passed; awaiting user acceptance. S4 has not started.
- Completed at: 2026-08-09 12:46 +08:00.
- Scope: owner-scoped private Concept -> canonical Concept -> private Document -> ordered Pages/Chunks links for Source-Grounded Lecture View v4.
- Safety boundary preserved: no writes to Neo4j, public/private Chroma, original PDFs, Planning, v1/v2/v3 content or progress, Quiz, next-day unlocking, or Adaptation.

### Implementation

- Added `private_source_linking.py` as a read-only resolver for confirmed private-document mappings.
- Private PDFs enter v4 only when all of these pass:
  - the mapping was explicitly confirmed during goal interpretation;
  - the document belongs to the current anonymous user and is still ready;
  - mapped chunk IDs resolve to real stored chunks;
  - real page metadata forms a continuous page sequence;
  - relevance is at least 0.75 and coverage is at least 0.60.
- Unconfirmed Daily private evidence is excluded from S3 server-side source selection.
- Upgraded the sidecar contract to `source-link-s3-v1` and the isolated snapshot generator to `source-grounded-v4-s3-private-links-v1`.
- Added additive sidecar fields `link_role` and `canonical_concept_id`.
- Source selection is quality-based:
  - verified public sources remain primary;
  - a stronger confirmed private source may become primary when the public candidate is not verified;
  - other reliable private sources are shown as supplemental;
  - private identity alone never overrides a stronger public source.
- v4 now renders all reliable sources for a section and labels primary/supplemental plus public/private scope.
- Existing document deletion flow removes this owner's sidecar links and invalidates only this owner's affected v4 snapshots.
- Static revision: `pathly-app.js?v=114`.

### API and database

- Existing v4 APIs remain unchanged.
- `GET /api/plans/{plan_id}/days/{day}/lecture-v4/source-links` now returns S3 role and canonical mapping metadata in owner-scoped records.
- `concept_source_links` migration is additive and the table remains removable/rebuildable.
- No public KG, RAG collection, plan, or historical content schema was modified.

### Verification

- Python syntax: passed for private resolver, source index, goal interpretation store, v4 store, and server.
- JavaScript syntax: `node --check pathly-app.js` passed.
- Focused S3/source-index/v4 tests: 18 passed; 1 dependency deprecation warning; 0 failures.
- Complete regression: 211 passed; 2 dependency deprecation warnings; 0 failures.
- Tests prove:
  - owner A can resolve an accepted private mapping while owner B cannot;
  - unrelated concepts do not receive the private PDF;
  - unconfirmed private evidence is rejected;
  - verified public source remains primary and private source is supplemental;
  - private source becomes primary only when no reliable public source is available;
  - sidecar rows remain owner scoped;
  - deleting a private document removes owner links and invalidates only owner v4 snapshots.
- Live service restarted with the project virtual environment on `127.0.0.1:4173`.
- Live capability reports `s3_private_source_links`; homepage HTTP 200 serves `pathly-app.js?v=114`.

### Real and fallback boundary

- S3 uses real confirmed mapping rows, owner-scoped SQLite document chunks, and their real page metadata.
- If a private mapping, owned document, chunk, page sequence, relevance, or coverage check fails, that private source is omitted. No template source or fabricated page is substituted.
- S3 does not generate the new lecture body. Source-grounded teaching content remains S4.

### Manual acceptance

1. Hard refresh `http://127.0.0.1:4173/?v=114`.
2. Open Today Learning and choose `Source-Grounded Lecture View v4`.
3. Use a path created with a confirmed, relevant private PDF.
4. Confirm the strongest source is labelled `PRIMARY SOURCE` and a second relevant private PDF is labelled `SUPPLEMENTAL SOURCE` when both are available.
5. Confirm private cards say `Your private material`, show the real filename and continuous page range, and explain the confirmed mapping.
6. Open another concept not covered by that PDF and confirm the PDF is not shown there.
7. Return to v3 and confirm its content/progress is unchanged.
8. Refresh v4 and confirm its independent state remains.

### Known boundary

- A current path with no confirmed relevant private mapping will correctly show only its public source or `No reliable source yet`.
- S3 does not yet combine the public/private pages into a newly generated lecture. That is the later v4 Lecture Generator stage.
## 2026-08-09 - v4 S4 source-grounded lecture generator complete

- Status: internal acceptance passed; awaiting user acceptance. S5 has not started.
- Completed at: 2026-08-09 15:01 +08:00.
- Scope: convert reliable S1-S3 Concept -> Source -> ordered PDF page links into finished, student-facing v4 lecture sections.
- Safety boundary preserved: v4 remains isolated from v3 content/progress, formal Quiz, next-day unlocking, Adaptation, Neo4j, public/private Chroma, Planning, and original PDF files.

### Implementation

- Added source_grounded_v4_generator.py with contract source-grounded-lecture-v4 and generator source-grounded-v4-s4-lecture-v1.
- Each ready section now contains:
  - concept introduction and actual mechanism;
  - prerequisite recap;
  - ordered selected source pages;
  - page-by-page explanation;
  - knowledge-specific terminology;
  - fully worked example;
  - at least three single-choice objective questions with immediate feedback;
  - summary and next-concept connection.
- Content validation rejects:
  - Pathly/Content Agent/pedagogy/learning-method meta language;
  - lectures too thin for scheduled minutes;
  - walkthrough pages outside the approved source sequence;
  - incomplete worked examples;
  - fewer than three objective questions;
  - questions without exactly one correct answer.
- Missing source pages, failed model calls, or failed quality validation produce an explicit retryable unavailable section. No template lecture, fake citation, or fallback source is displayed.
- Public verified/backfilled pages and owner-scoped private document chunks are resolved only from the S1-S3 approved links.
- The v4 page now renders the complete S4 contract inside Today Learning while keeping the existing sidebar and Ask Pathly layout.
- Private PDF pages render in the relevant source section; public selected pages display their extracted evidence and page identity.
- v4 exercise answers and results persist in the independent browser workspace; section completion remains independent of v3.
- Multiple eligible v4 sections generate concurrently with up to three workers, reducing initial wait from the sum of all section times to approximately the slowest batch.
- Static revision: pathly-app.js?v=115.

### API and storage

- Existing isolated v4 endpoints remain unchanged:
  - GET /api/plans/{plan_id}/days/{day}/lecture-v4
  - POST /api/plans/{plan_id}/days/{day}/lecture-v4/generate
  - POST /api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/complete
  - POST /api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/retry
- Existing S4-incompatible v4 snapshots are treated as stale and regenerated; v3 caches are not migrated or overwritten.
- v4 source links and progress remain in the removable SQLite sidecar tables.

### Verification

- Python syntax: passed for the S4 generator, source providers, store, and server.
- JavaScript syntax: node --check pathly-app.js passed.
- Focused S4/v4 entry/isolation tests: 15 passed; 1 dependency deprecation warning; 0 failures.
- Complete regression: 215 passed; 2 dependency deprecation warnings; 0 failures.
- Real model smoke test: OpenAI returned all seven required lecture fields and three objective questions in 63.8 seconds for a source-grounded XOR section.
- Failure tests prove that missing sources, model failure, meta language, and invalid objective answers do not produce a fake lecture.
- Live Pathly service restarted on 127.0.0.1:4173.
- Live health: ok; capabilities: s4_source_grounded_lecture; anonymous session enforcement: enabled; homepage serves v115.
- Automated browser control could not start because the Windows browser helper returned CreateProcessWithLogonW 1385. The running service and automated web/API tests are healthy; final visual acceptance is manual.

### Known boundary

- S4 generates and displays source-grounded lecture content, but v4 signals do not yet affect the formal Quiz, next-day unlock, or Adaptation. That is S5.
- Public source pages currently display verified page identity plus extracted page evidence; private PDFs also render the actual page image.
- A section with no reliable source or failed quality validation is intentionally unavailable until retry succeeds.
- The first live model generation is asynchronous from the user's perspective but can take around one minute. Up to three sections now generate in parallel; cached reloads are immediate.

### Manual acceptance

1. Hard refresh http://127.0.0.1:4173/?v=115.
2. Open Today Learning and select Source-Grounded Lecture View v4.
3. Wait for the first generation. The v4 tab stays inside Today Learning; the sidebar and Ask Pathly remain visible.
4. Confirm a ready section includes Concept Introduction, Prerequisite Recap, Selected Source Pages, Page-by-Page Explanation, Key Terms, Worked Example, Objective Exercise, and Summary.
5. Answer an objective question incorrectly and check the immediate explanation; then answer all questions correctly.
6. Confirm Complete v4 section stays disabled until all objective answers are correct, then saves immediately.
7. Refresh and confirm v4, the selected section, objective answers, results, and independent completion state are restored.
8. Return to Full Lecture v3 and confirm v3 progress is unchanged.
9. For an unavailable section, confirm only retry/return/continue actions appear and no template or fabricated source lesson is shown.

## 2026-08-09 - v4 generation duplicate source-link hotfix

- Status: internally verified; awaiting user visual acceptance
- Root cause: S1 projected the same Concept-Resource source through more than one evidence path. ConceptSourceLinkIndex.replace_day() converted both records to the same stable scoped link_id, then attempted two SQLite inserts, causing UNIQUE constraint failed: concept_source_links.link_id. The v4 generate endpoint therefore returned HTTP 500 before S4 content generation began.
- Fix:
  - Deduplicate projected links by the final owner/plan/day-scoped link_id before insertion.
  - When duplicate candidates differ, deterministically retain the stronger record, prioritising verified status, relevance, coverage, then page-sequence length.
  - Added a regression test covering duplicate private Concept-Source candidates.
- Validation:
  - Focused S1-S4 tests: 16 passed.
  - Complete regression: 216 passed, 2 dependency deprecation warnings, 0 failures.
  - Pathly restarted on port 4173; /api/health returned service ready and v4 stage s4_source_grounded_lecture.
- Privacy boundary:
  - The agent did not trigger live generation for the user's real plan because that may send the user's private PDF evidence and profile context to the configured model. The user can now trigger it explicitly from the v4 UI.
- Acceptance:
  1. Refresh http://127.0.0.1:4173/?v=115.
  2. Open Today Learning and Source-Grounded Lecture View v4.
  3. Select Retry v4 once.
  4. The request must no longer fail immediately with the generic v4 error. It should show generated sections or explicit per-section unavailable states.

## v4 S4 hotfix — Retry route/generator collision and redundant v3 rebuild (2026-08-09 17:04:36 +08:00)

- Status: pending user confirmation.
- User-visible failure: Retry v4 repeatedly returned 4 could not be loaded after S1/S3 source links had already been written.
- Root causes:
  - pathly_server.generate_source_grounded_lecture_v4 (the FastAPI endpoint) shadowed the imported function with the same name. The endpoint therefore passed itself to the worker instead of the S4 generator.
  - Both whole-lecture generation and section retry unnecessarily regenerated Full Lecture v3. A staged local diagnostic measured about 159 seconds in v3 restoration versus about 32 seconds in the isolated v4 generator, causing the browser request to time out before v4 could be saved.
- Changes:
  - Imported the S4 generator as uild_source_grounded_lecture_v4 and updated both call sites.
  - When an isolated v4 snapshot exists, whole-v4 regeneration now uses it as the structural base instead of rebuilding v3.
  - Section retry now reuses the saved isolated v4 structure and never regenerates v3.
  - Added regression coverage for generator aliasing and v3-free section retry.
- Verification:
  - python -m py_compile pathly_server.py source_grounded_v4_generator.py: passed using the project venv.
  - Focused v4/source-index suite: 20 passed, 1 upstream deprecation warning.
  - Full regression: 218 passed, 2 upstream deprecation warnings, 0 failures.
  - Pathly restarted as one listener on 127.0.0.1:4173 (PID 41120); capabilities report v4 stage s4_source_grounded_lecture.
- Privacy note: no live retry was initiated outside the user's browser session, so private PDF evidence was not sent through a synthetic test session.
- Manual acceptance: hard-refresh, open the same Day 1, select Source-Grounded Lecture View v4, and press Retry v4 once. The request should now invoke the real S4 generator and must not rebuild v3.

## 2026-08-09 - v4 false timeout and inert Retry hotfix

- Status: internally verified; awaiting user visual acceptance.
- User-visible failure: v4 displayed `v4 restoration timed out` after about 15 seconds even though the server was still generating successfully; pressing Retry then appeared to do nothing.
- Root causes:
  - The frontend used a fixed 15-second restoration watchdog, while real four-section generation took about 128-160 seconds.
  - After the false timeout, `lectureV4Loading` remained true, so the Retry handler returned early and did not start another request.
- Changes:
  - Removed the false 15-second v4 restoration timeout.
  - Render the real generating state immediately before the generate request and keep it visible until the request returns.
  - Clear the v4 error after a successful response and preserve explicit per-section unavailable states when content validation rejects a section.
  - Added a safe `content_validation_failed` reason for future retries without exposing private model output.
  - Fixed two remaining mojibake strings in the product UI.
  - Bumped the frontend asset to `pathly-app.js?v=116`.
- Verification:
  - v4 focused suite: 19 passed, 1 upstream deprecation warning, 0 failures.
  - Complete regression: 220 passed, 2 upstream deprecation warnings, 0 failures.
  - Pathly restarted with exactly one listener on `127.0.0.1:4173` (PID 37296).
  - Homepage, `/api/health`, and `/api/capabilities` return HTTP 200.
  - Homepage serves `pathly-app.js?v=116`; capabilities report v4 enabled.
- Known boundary:
  - A fresh whole-lecture generation can still take roughly 2-3 minutes because it generates and validates four source-grounded sections. It must now remain in a truthful generating state rather than reporting a false timeout.
  - The current saved snapshot has four unavailable sections because previous model outputs failed strict content validation. Retrying an individual section is the fastest acceptance path and now records a specific safe validation reason if it is rejected again.
- Manual acceptance URL:
  - `http://127.0.0.1:4173/?v=116&daily_view=lecture-v4&plan_id=874d8d3e-bfb1-463c-963f-8c140bb6d0e2&day=1`

## 2026-08-09 - v4 PDF layout and mathematical transcript hotfix

- Status: internally verified; awaiting user visual acceptance.
- User-visible issues:
  - Rendered PDF pages used their natural dimensions and were clipped by the Ask Pathly sidebar.
  - Extracted PDF text exposed damaged formula, matrix, and font-mapping output as primary lesson content.
- Root causes:
  - v4 layout rules existed in `pathly-styles.css`, but the production page did not load or serve that stylesheet.
  - Private PDF page text was rendered as an always-visible blockquote even when the original rendered page was available.
- Changes:
  - Merged v4 rules into the existing FastAPI-served `pathly-ui.css` and bumped app/CSS assets to v117.
  - Added strict min-width/max-width constraints to the lecture grid and source-page cards.
  - Added a bounded PDF frame that scales the full page to the lecture column while preserving aspect ratio.
  - Kept the original PDF page as the source of truth for formulas, matrices, diagrams, and mathematical notation.
  - Moved extracted text into a collapsed `Accessible text transcript` panel with an explicit notation warning.
- Verification:
  - JavaScript syntax passed.
  - Focused v4/frontend tests: 71 passed initially; final merged-style frontend suite: 57 passed.
  - Complete regression: 221 passed, 2 upstream deprecation warnings, 0 failures.
  - Pathly restarted with one listener on 127.0.0.1:4173 (PID 45632).
  - Homepage and `pathly-ui.css?v=117` return HTTP 200; the served CSS contains the PDF fit rule.
- Acceptance URL:
  - `http://127.0.0.1:4173/?v=117&daily_view=lecture-v4&plan_id=874d8d3e-bfb1-463c-963f-8c140bb6d0e2&day=1`
## 2026-08-09 - v4 colocated PDF page guidance frontend update

- Status: internally verified; awaiting user visual acceptance.
- User feedback addressed:
  - Only raw PDF extraction should be folded under `Accessible text transcript`; the teaching explanation must remain visible.
  - Each page-specific explanation should appear with the corresponding original PDF page instead of in a detached summary list.
- Changes:
  - Each v4 source page now renders its own visible `Pathly Page Guide` immediately below the page.
  - The guide includes `What to notice`, the page explanation, and its connection to the previous/next idea.
  - Private PDF raw extracted text remains collapsed because formula and matrix extraction can be lossy.
  - Public source text stays visible when no original PDF page renderer is available.
  - Removed the duplicated standalone `Page-by-page explanation` section.
  - Existing lecture data is reused; no regeneration is required.
  - Bumped frontend assets to v118.
- Verification:
  - JavaScript syntax check: passed.
  - Focused v4/frontend tests: 58 passed, 1 upstream warning, 0 failures.
  - Complete regression: 222 passed, 2 upstream dependency warnings, 0 failures.
  - Pathly restarted with exactly one listener on 127.0.0.1:4173 (PID 38296).
  - Homepage and `pathly-ui.css?v=118` return HTTP 200; both v118 assets and colocated guide styles are served.
- Acceptance URL:
  - `http://127.0.0.1:4173/?v=118&daily_view=lecture-v4&plan_id=874d8d3e-bfb1-463c-963f-8c140bb6d0e2&day=1`

## 2026-08-09 - v4 bounded section retry closure

- Status: internally verified; awaiting user visual acceptance.
- User-visible problem addressed:
  - Some unavailable v4 sections continued to fail after Retry, while the UI gave no immediate response and the server regenerated unrelated sections.
- Root causes:
  - The retry endpoint rebuilt every v4 section instead of isolating the requested section.
  - Content-contract failures and malformed model JSON were reported too generically.
  - Every failure was treated as retryable, including missing or unreadable source material.
- Changes:
  - Retry now sends only the selected section through the v4 generator and replaces only that section in the saved v4 snapshot.
  - Added one safe repair pass for malformed or incomplete model output using the original selected sources and a non-content validation label.
  - Previous model output is never included in the repair request, preventing accidental resubmission of private PDF-derived generated content.
  - Added explicit response-format, content-validation, source-link, source-text, and generation failure presentation.
  - Missing/unreadable sources are no longer offered a futile regeneration action.
  - Added a maximum of three section repair attempts.
  - Retry now shows immediate section-local `Repairing this section...` feedback without a full-page loading overlay.
  - Bumped frontend assets to v119.
- Verification:
  - JavaScript syntax and Python compilation: passed.
  - Focused v4/frontend suite: 76 passed, 1 upstream warning, 0 failures.
  - Complete regression: 226 passed, 2 upstream dependency warnings, 0 failures.
- Privacy verification:
  - Tests use an injected fake model; no private PDF was sent to a live model during verification.
  - The repair-pass regression explicitly asserts that no `previous_output` field is present.
- Manual acceptance:
  - Open the v119 acceptance URL, choose an unavailable section and press its repair button.
  - The clicked section must immediately show `Repairing this section...`; other sections must remain unchanged.
  - A source-link/source-text failure must explain that regeneration cannot fix it instead of showing Retry.
- Runtime verification: Pathly restarted with exactly one listener on `127.0.0.1:4173` (PID 48180); homepage, health endpoint, and v119 CSS returned HTTP 200.

## 2026-08-09 - S4 source-grounded lecture publication closure (v120)

**Status:** Internally verified; awaiting user visual acceptance.

### Product decision

- v4 is now published atomically: the learner sees the lecture only when every required section passes source, content, structure, worked-example, and objective-exercise checks.
- If any section fails, no successful section and no failed section is partially published.
- Learners no longer see repair attempts, quality-check failure reasons, `Needs attention`, or manual `Repair this section` controls.
- The withheld state uses neutral product language and allows source review, opening My Library, or returning to Full Lecture v3.
- Background repair is automatic and bounded to three attempts per section in one page session. A later visit can resume recovery without exposing incomplete content.
- No low-quality template lecture is used as a fallback.

### Implementation changes

- `source_grounded_v4_generator.py`: added lecture-wide publication metadata and `published/withheld` status.
- `pathly_server.py`: centralised publication-state recomputation; completion is rejected until the entire lecture is published; section retry preserves lecture-wide metadata.
- `pathly-app.js`: added the all-or-nothing publication gate, neutral withheld UI, optional source review, and bounded automatic background repair.
- `pathly-ui.css`: added publication-gate and source-review styling.
- `index.html`: serves v120 assets.

### API and data behaviour

- Existing isolated v4 APIs remain unchanged.
- `generation_metadata` now records `publication_status`, `quality_gate_passed`, and `withheld_sections`.
- v4 remains isolated from v3 progress, the formal Quiz, next-day unlock, and Adaptation.

### Verification

- JavaScript syntax check: passed.
- Python compile check: passed.
- Focused S4 suite: `26 passed, 1 warning`.
- Full regression: `227 passed, 2 warnings`.
- Runtime: one listener on port 4173, PID 42808.
- Online checks: homepage 200, `/api/health` 200, v120 JavaScript 200.
- Online asset inspection confirms the publication gate is present and the learner-facing manual repair label is absent.
- Warnings are upstream deprecation notices from Starlette/httpx and importlib metadata; there were no test failures.

### Browser validation limitation

- Automated in-app browser control could not start because Windows returned `CreateProcessWithLogonW failed: 1385`.
- This is recorded as an automation-environment limitation, not reported as a Pathly browser pass.
- User visual acceptance is therefore still required.

### User acceptance URL

`http://127.0.0.1:4173/?v=120&daily_view=lecture-v4&plan_id=874d8d3e-bfb1-463c-963f-8c140bb6d0e2&day=1`

Acceptance expectation:

1. An incomplete lecture shows only `Preparing your complete lecture` or `This lecture needs better source material`.
2. It never shows partial lecture sections, `Needs attention`, repair attempt counts, or a `Repair this section` button.
3. If all automatic repairs pass, the complete lecture replaces the gate as one publication.
4. `Review source materials` reveals source summaries only; it does not reveal an unapproved lesson.
5. Returning to v3 leaves v3 progress unchanged.

### Known boundary

- Automatic repair is initiated while the v4 page is open. If the learner leaves, recovery resumes on a later v4 visit.
- Formal v4 learning-state integration remains S5 work and is intentionally not part of S4.
## 2026-08-09 - Rollback S4 atomic publication gate (v121)

**Status:** Internally verified; awaiting user visual acceptance.

### Product decision

- Rolled back only the v120 whole-lecture publication gate because it could keep learners on `Preparing your complete lecture` for too long.
- Restored the previous section-local v4 experience: approved sections appear immediately, while an unsuccessful section remains isolated and can be repaired independently.
- Retained the completed S1-S3 work: source linking, public/private source separation, consecutive PDF page sequences, source-grounded generation, and PDF presentation improvements.
- Building a stronger curated PDF collection remains the preferred way to improve coverage and section quality.

### Implementation changes

- `pathly-app.js`: removed the whole-lecture waiting gate and automatic lecture-wide repair loop; restored section-local rendering and manual repair controls.
- `source_grounded_v4_generator.py`: restored section-level generated/unavailable status without atomic publication metadata.
- `pathly_server.py`: removed the lecture-wide completion guard and restored independent section retry semantics.
- `pathly-ui.css`: removed v120 publication-gate styling.
- `index.html`: serves v121 assets.

### Verification

- JavaScript syntax check: passed.
- Python compile check: passed.
- Focused rollback suite: `77 passed, 1 warning`.
- Full regression: `227 passed, 2 warnings`.
- Runtime: one listener on port 4173, PID 48636.
- Online checks: homepage 200, `/api/health` 200, v121 JavaScript 200.
- Online asset inspection confirms section-local copy and `Repair this section` are present, while `Preparing your complete lecture` is absent.
- Warnings are upstream deprecation notices; there were no test failures.

### User acceptance URL

`http://127.0.0.1:4173/?v=121&daily_view=lecture-v4&plan_id=874d8d3e-bfb1-463c-963f-8c140bb6d0e2&day=1`

Acceptance expectation:

1. v4 does not stop at a whole-lecture `Preparing your complete lecture` screen.
2. Sections that passed quality checks are displayed immediately.
3. A section that did not pass is marked independently and offers `Repair this section`.
4. Repairing one section does not hide other available sections.
5. Returning to v3 leaves v3 progress unchanged.

### Known boundary

- A low-quality or poorly aligned source can still cause one v4 section to remain unavailable; the rest of the lecture remains usable.
- Formal v4 learning-state integration remains S5 work and is unchanged by this rollback.
## 2026-08-10 - G0 golden demonstration path closure

**Status:** Awaiting user acceptance.

### Delivery

- Fixed demonstration chain: `Linear Separability → XOR → Neural Networks → Activation Functions → Gradient Descent`.
- Created and activated fixed five-day path: `g0-neural-foundations-98c696ca12b9-v1`.
- Indexed all 34 extracted chunks from public `06_mlp.pdf` into the public retrieval collection.
- Pre-generated and cached five source-grounded v4 lectures. Day 1–2 use verified `06_mlp.pdf` pages; Days 3–5 use a verified neural-network lecture source where it is a closer semantic match.
- Each lecture passed concept/source alignment, ordered-source, worked-example, objective-question, readable-symbol, and no-meta-language checks.

### Verification

- Focused G0 and source-grounding tests: `12 passed`.
- Full regression suite: `230 passed, 2 warnings`.
- Pathly service restarted successfully; health endpoint returned HTTP 200.
- Quality report: `artifacts/g0_quality_report.json`.

### Acceptance boundary

- The remaining work is browser-level visual acceptance of the five cached lecture pages and their source sequences.
- G0 remains an isolated v4 pilot: it does not change formal Quiz, next-day unlocking, Adaptation, or v1/v2/v3 learning progress.
## 2026-08-10 - G0 current-session acceptance launcher

**Status:** Ready for user acceptance.

### Fix
- Replaced the obsolete hard-coded G0 plan link with a `golden_case=g0` launcher.
- The launcher first resolves the current anonymous browser session, then creates the fixed public G0 path for that same session and opens Day 1 in Lecture v4.
- Approved public G0 lectures are copied into the current session's isolated v4 cache; no five-lecture live-model rerun is required for each acceptance run.
- After launch, the URL is normalized to the current session's `plan_id`, `daily_view=lecture-v4`, and `day=1`, so refreshes do not relaunch G0.

### Verification
- Syntax checks: `g0_golden_case.py`, `source_grounded_v4_store.py`, and `pathly-app.js` passed.
- Focused G0 tests: `4 passed`.
- Service health check passed after restart.
- Fresh anonymous-session API flow passed: session creation -> G0 provisioning -> Day 1 v4 fetch returned `g0-neural-foundations-v1`, one lecture section, and `session_template_reused=true`.

### Acceptance entry
- Start from `/?golden_case=g0`; do not reuse historic `g0-neural-foundations-...` plan IDs from a different anonymous session.

## 2026-08-11 - Local shared-demo learner mode

**Status:** In progress.

### Goal

Make a local Pathly presentation stable across browser windows: public knowledge and the presenter's private materials can be used together for the same current learning path, without publishing private material to the public KG or public RAG.

### Changes in progress

- Added an explicit `PATHLY_LOCAL_DEMO_SHARED_MODE` switch, defaulting to `false` in application code.
- The local `start_pathly.ps1` launcher enables the switch so normal local presentations use one stable learner identity.
- Production keeps its existing anonymous-session ownership boundary when the switch is absent or false.

### Verification pending

- Restart with the local launcher.
- Verify two independent browser clients obtain `local-demo-learner` and can read the same newly created path/v4 record.
- Verify the normal production-default test path remains per-session.

## 2026-08-11 — Local shared-demo learner mode

**Status:** internally accepted

### Purpose
Make the local presentation stable across Chrome, the in-app browser, refreshes, and new tabs without changing the public/private data boundary.

### Implementation
- Added `PATHLY_LOCAL_DEMO_SHARED_MODE` (default `false`) and `PATHLY_LOCAL_DEMO_USER_ID` (default `local-demo-learner`).
- `start_pathly.ps1` enables shared-demo mode only for the local launcher.
- In shared-demo mode, individual browsers retain separate HttpOnly cookies but all business requests resolve to `local-demo-learner`.
- Public KG/public RAG and uploaded private documents can therefore contribute to the same local learner's planning and content. Private documents remain in private storage/indexes and are never written into public KG/RAG.
- Production behaviour is unchanged when the flag is false: each anonymous session remains isolated.
- Added a non-sensitive health indicator: `local_demo_shared_mode`.

### Verification
- Python syntax check: passed.
- `pytest tests/test_pathly_security.py tests/test_source_grounded_lecture_v4.py -q`: **16 passed**.
- Live integration test with two independent HTTP sessions: passed. Both returned `user_id=local-demo-learner`, `local_demo_shared=true`, while retaining separate cookies.

### Known transition note
Plans created under previous browser-specific anonymous IDs are not automatically migrated into the new shared local learner. Create or recreate the presentation path once after this restart; it will then remain accessible from all local browsers and tabs.

### Final service check
- Restarted local Pathly on 127.0.0.1:4173 with PATHLY_LOCAL_DEMO_SHARED_MODE=true.
- /api/health returned service_ready=true and local_demo_shared_mode=true.
- Live two-session verification passed after restart.


## 2026-08-11 - Verified good-case normal-flow integration

**Status:** Internally accepted; awaiting browser acceptance.

### Product decision

- The reliable-source case is now part of the normal onboarding -> planning -> daily-content flow.
- No dedicated golden-case launcher or prebuilt-plan selection is exposed in the frontend.
- Existing onboarding questions and stored profile schema were not changed.
- Two presentation scenarios remain presenter guidance only; they are not shown on plan or content pages.

### Implementation

- Removed the frontend G0 launcher branch so normal hydration always follows the learner's own profile, goal and plan.
- Added a verified-source registry matcher for neural-network goals and concept coverage. It only supplies audited sources; it never creates a plan or user session.
- Added a v4 scenario fingerprint covering the goal, concept path, profile version inputs, learning style, example preference, pace, interest tags, foundation scores and confidence. Identical inputs reuse cache; meaningful profile changes produce a distinct cache identity.
- Canonicalized v4 GET, generate, source-link, complete and retry operations to the server-side anonymous-session owner. Stale frontend user IDs can no longer redirect v4 reads/writes to the wrong cache.
- A valid scheduled plan can initialize its daily session before v4 generation instead of being reported as a missing resource.
- Added small accessible question-mark hints beside existing onboarding questions. The hints explain that an answer may affect teaching proportion, scaffolding, examples, pacing or review. No explicit timing explanation was added to plan/content pages.
- Corrected two legacy English encoding artifacts and moved the interaction stylesheet inside the document head.
- Bumped frontend assets to v124.

### Verification

- Python and JavaScript syntax checks: passed.
- Focused v4, verified-source, profile-cache and frontend tests: **27 passed**.
- Complete regression: **237 passed, 2 dependency deprecation warnings**.
- The warnings are from Starlette TestClient/httpx and OpenTelemetry metadata APIs; they do not indicate product failures.

### Acceptance focus

1. Complete onboarding normally with the neural-network learning goal; do not use a special golden URL.
2. Hover or focus the question-mark hints and confirm they are brief and non-blocking.
3. Create the path and open Today Learning -> Source-Grounded Lecture v4.
4. Refresh and retry a section; the same plan/day must remain accessible without a false 404.
5. Repeat with a different learning style, example preference or confidence answer. The normal flow remains the same, while the generated content/cache input is distinct.

### Final boundary and live verification

- Removed the public G0 provisioning/status API. The audited source registry remains available to the normal planning/content path; no prebuilt demonstration plan is exposed as a product action.
- Added an explicit regression assertion that the product API does not expose a prebuilt good-case plan.
- Final complete regression after this removal: **238 passed, 2 dependency deprecation warnings**.
- Restarted Pathly with the project virtual environment and local shared-learner configuration.
- Live checks: homepage HTTP 200, service_ready=true, v124 assets active, exactly one listener on port 4173, and no public /api/golden-cases/g0 route.
- Browser-control automation could not be started because the Windows sandbox account lacks logon rights (CreateProcessWithLogonW 1385). This is recorded as an environment limitation; no visual browser result is claimed.
## 2026-08-11 — Final plan P0: Neo4j production gate

Status: **internal acceptance passed; awaiting user confirmation before K1**

### Goal

- Make real Neo4j the mandatory KG backend for formal Pathly startup and acceptance.
- Prevent a configured password or a JSON fallback from being reported as a successful Neo4j production run.

### Changes

- Added `pathly_neo4j.py` with separate configuration, Bolt reachability, authentication/query, and actual-backend checks.
- Added `neo4j_preflight.py`; it fails formal startup unless `KG_BACKEND=neo4j` and a real read-only `MATCH (c:Concept)` query succeeds.
- Updated `start_pathly.ps1` to set `KG_BACKEND=neo4j`, run the preflight, optionally launch Neo4j Desktop when Bolt is down, and refuse to start Pathly on a JSON fallback.
- Updated `/api/health` and `/api/capabilities` Neo4j data to distinguish `configured`, `bolt_reachable`, `query_verified`, `configured_backend`, and `actual_backend`.
- Updated `.env.example` with the formal Neo4j configuration and optional Neo4j Desktop executable.

### Tests and actual results

- Python compile: passed for `pathly_neo4j.py`, `neo4j_preflight.py`, and `pathly_server.py`.
- P0/API tests: `10 passed`.
- Full Pathly regression: `242 passed`, with two dependency deprecation warnings and no failures.
- Real preflight: passed with `configured_backend=neo4j`, Bolt reachable, query verified, database `neo4j`, and `366` Concept nodes.
- Live service restart through `start_pathly.ps1`: passed.
- Live `/api/health`: HTTP 200; `neo4j.available=true`, `query_verified=true`, `actual_backend=neo4j`, `concept_count=366`.

### Fallback boundary

- JSON remains available for explicitly labelled outage tests.
- JSON cannot pass `neo4j_preflight.py` and is not counted as a formal production acceptance result.

### Known limitation

- Starting Neo4j Desktop can be automated when the desktop executable is known, but a Desktop project configured not to auto-start its DBMS can still require the user to start that DBMS. Pathly now reports this as a failed preflight instead of silently using JSON.

### Next stage

- K1: audit the five canonical concepts, relationships, resources, chunks, ordered PDF pages, quality, and licensing for the golden knowledge chain.
## 2026-08-11 — K1 Golden knowledge chain audit — awaiting user confirmation

- Status: **internal acceptance passed; awaiting user confirmation**
- Scope: read-only audit only. Neo4j, Chroma, PDFs, Planning, and content records were not modified.
- Production gate: real Neo4j query passed (`actual_backend=neo4j`, `query_verified=true`, 366 Concept nodes).
- Added repeatable audit: `kg_golden_audit.py`.
- Added machine-readable result: `artifacts/k1_golden_chain_audit.json`.
- Added human report: `documents/K1_GOLDEN_CHAIN_AUDIT.md`.
- Added tests: `tests/test_kg_golden_audit.py`.
- Findings:
  - All five concepts have usable reviewed PDF page coverage.
  - XOR is not a canonical Neo4j Concept.
  - Linear Separability has no explicit bridge to XOR.
  - Neural Networks and Activation Functions contain a prerequisite cycle.
  - Gradient Descent currently lists Backpropagation as a prerequisite and needs direction review.
  - Public Chroma has resource chunks for both golden PDFs, but the chunks lack page and canonical-concept metadata.
  - Source URL/license metadata is insufficient for a publication conclusion.
- Commands and actual results:
  - `python -m pytest tests/test_kg_golden_audit.py -q` → `3 passed`.
  - `python kg_golden_audit.py` → 5 concepts audited; 0 fully verified end-to-end; 5 need relationship/provenance review; 0 lack usable PDF content.
  - `python -m py_compile kg_golden_audit.py` → passed.
  - `python -m pytest -q` → `245 passed, 2 warnings` in 63.88 seconds.
- Next after confirmation: P1 public Concept–Source relationship implementation, using these findings as the migration input.

## 2026-08-11 - P1 Public Concept-Source Registry

Status: **internal acceptance passed; awaiting user confirmation**

### Goal

- Make verified public source links reusable across normal onboarding-created plans.
- Separate stable public source registration from per-user/per-plan daily course snapshots.
- Keep the implementation read-through and sidecar-based: no Neo4j, Chroma, Planning, v1/v2/v3, or historical v4 content records were modified.

### Implementation

- Added `public_source_registry.py` with a sidecar SQLite table `public_concept_sources`.
- Added `PublicConceptSourceRegistry` and `PublicThenReviewedResolver`.
- Public source identity is now based on `canonical_concept_id + resource_id + source_version`, not user, plan, or day.
- Added `p1_public_source_rebuild.py`, which rebuilds the public registry from Neo4j health plus reviewed golden-source coverage.
- Added `GET /api/concepts/{concept_id}/verified-sources`.
- Added `POST /api/internal/source-links/rebuild`.
- Updated v4 source resolution to read from the public registry first, then reviewed golden sources.

### API and data changes

- New source version: `public-concept-source-p1-v1`.
- New sidecar table: `public_concept_sources`.
- New machine-readable artifact: `artifacts/p1_public_source_registry.json`.

### Tests and actual results

- Python compile: passed for `public_source_registry.py`, `p1_public_source_rebuild.py`, and `pathly_server.py`.
- Focused tests: `pytest tests/test_public_source_registry_p1.py tests/test_source_grounded_lecture_v4.py -q` -> `17 passed, 1 warning`.
- Live `/api/health`: HTTP 200; `service_ready=true`; `configured_backend=neo4j`; `actual_backend=neo4j`; `bolt_reachable=true`; `query_verified=true`; `concept_count=366`.
- Live rebuild: `POST /api/internal/source-links/rebuild` -> `kg_source=neo4j`, `neo4j_query_verified=true`, `concept_count=5`, `verified_count=5`.
- Live verified-source lookup: `GET /api/concepts/canonical%3Axor/verified-sources?concept_name=XOR` -> verified public source for `XOR`, document `06_mlp.pdf`, continuous pages `2-7`, match reason recorded, no `user_id` field exposed.

### Known issues

- `XOR` is still not a canonical Neo4j Concept node. P1 bridges it through the reviewed public source registry, but K2/K3 should add or merge it properly in Neo4j.
- The reviewed `XOR` source still reports `neo4j_node_status=missing` and `neo4j_resource_status=missing_or_id_mismatch`.
- Source URL and license status remain `needs_source_review` for the reviewed golden materials.
- P1 improves source reuse and removes plan/day coupling from public links; it does not by itself guarantee v4 generation quality or repair all v4 retry failures.

### Next stage

- P2: repair v4 initialization, cache identity, retry behavior, and runtime error handling so missing cache/source/session states no longer collapse into vague 404 failures.

## 2026-08-11 - P2 v4 initialization, cache identity, Retry, and runtime state

Status: **internal acceptance passed; awaiting user confirmation**

### Goal

- Fix the Source-Grounded Lecture View v4 runtime path so missing cache, stale cache, daily-session initialization, and Retry no longer collapse into vague 404 errors or an infinite Restoring state.
- Keep v4 inside the normal Today Learning tab flow.
- Preserve v4 isolation from v1/v2/v3 progress, formal Quiz, next-day unlock, and Adaptation.

### Implementation

- Updated `GET /api/plans/{plan_id}/days/{day}/lecture-v4`.
  - Missing v4 cache now returns a valid `v4_not_generated` payload with `can_generate=true` and `reason_code=cache_missing`.
  - Stale v4 cache returns a valid `v4_stale` payload with `can_generate=true` and `reason_code=cache_stale`.
  - Cache absence is no longer treated as a missing Pathly resource.
- Added current-cache validation for v4.
  - v4 cache identity now includes public source version, source-link version, golden path version, generator version, and scenario fingerprint.
- Added daily runtime initialization before v4 generation.
  - v4 generate now verifies/initializes the selected plan/day daily session before building source-grounded content.
- Updated `Retry v4` frontend behavior.
  - Retry now calls `loadLectureV4(true)` and forces regeneration instead of repeating a stale GET.
  - The v4 error state now gives an immediate visible generating/regenerating state.
  - The v4 loading card explains whether Pathly is checking cache, generating for the first time, or regenerating from verified sources.
- Kept v4 failures isolated.
  - A failed or rejected v4 generation does not alter v3, Quiz state, Activity Timeline unlock, or Adaptation.

### API and data changes

- No new public database table was added in P2.
- Changed v4 GET semantics from ambiguous 404 to explicit runtime state:
  - `v4_status=not_generated`
  - `v4_status=stale`
  - `can_generate=true`
  - `reason_code=cache_missing/cache_stale`
- Generation still uses existing v4 content storage and source-link sidecar state.

### Tests and actual results

- JavaScript syntax check:
  - `node --check pathly-app.js` -> passed.
- Focused Python tests:
  - `python -m pytest tests/test_source_grounded_lecture_v4.py tests/test_public_source_registry_p1.py -q` -> `20 passed` in 24.48 seconds.
- Live `/api/health` after service restart:
  - HTTP 200.
  - `service_ready=true`.
  - `KG_BACKEND=neo4j`.
  - `neo4j.configured_backend=neo4j`.
  - `neo4j.actual_backend=neo4j`.
  - `neo4j.bolt_reachable=true`.
  - `neo4j.query_verified=true`.
  - `neo4j.concept_count=366`.
- Live v4 cache/runtime check:
  - `GET /api/plans/9df74580-82e7-4dff-a1fd-89e202762f92/days/1/lecture-v4?user_id=local-demo-learner` -> HTTP 200.
  - Current response mode: `stored`.
  - Verified that the endpoint now returns valid v4 state rather than a generic 404.
- Earlier live missing-cache check during P2:
  - Missing cache returned `mode=v4_not_generated`, `v4_status=not_generated`, `can_generate=true`, `reason_code=cache_missing`.
- Earlier live generate check during P2:
  - `POST /lecture-v4/generate` completed server-side with HTTP 201 after about 173.7 seconds.
  - The synchronous client call timed out at 120 seconds, but the server completed and persisted the v4 record.
  - The persisted section was marked unavailable by v4 quality checks. This is recorded as a content-quality limitation, not a P2 runtime/cache failure.

### Known limitations

- v4 generation can still be slow because source resolution, generation, and quality checks currently run synchronously. P2 makes the state recoverable and explicit, but does not yet add a true async background job queue.
- Strict quality checks can still reject a generated section. P2 intentionally avoids showing fake or low-quality lecture content; rejected content remains a P5/content-quality issue.
- Some generated source text still contains encoding/OCR artifacts in stored historical v4 records. P2 does not rewrite historical content.
- Interest tags and some onboarding field-consumption fixes remain P4.
- Better lecture quality, formula/layout rendering, and PDF-adjacent teaching presentation remain P5.

### User acceptance steps

1. Hard refresh Pathly with a cache-busting URL.
2. Open Today Learning for a plan/day.
3. Click `Source-Grounded Lecture View v4`.
4. Expected: the page stays inside Today Learning, the sidebar remains visible, and v4 either loads existing content or shows a local generating/regenerating state.
5. Click `Retry v4` on a failed v4 card.
6. Expected: Retry immediately switches into a generating state and no longer loops through a stale GET-only 404.
7. Return to Full Lecture v3.
8. Expected: v3 progress and v4 progress remain separate.

### Next stage

- P3: ensure the verified golden objective can be created through the normal onboarding/planning path and reuse verified public sources without depending on a fixed plan ID or pre-created user.

---

## 2026-08-11 20:58 +08:00 — P3 normal onboarding golden-path creation

### Status

- Stage: P3 — normal Onboarding generates the verified golden path.
- Result: internally validated; ready for user acceptance.

### Objective

Make the verified golden case work through the normal product flow rather than a fixed prebuilt plan:

```text
I want to understand why XOR is not linearly separable and learn how neural networks,
activation functions, and gradient descent solve this problem.
```

Expected stable core chain:

```text
Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent
```

### Implementation

- Added verified golden-goal interpretation helpers in `verified_golden_sources.py`.
  - `verified_canonical_concept_name(...)`
  - `verified_goal_concepts_for_goal(...)`
  - `VerifiedGoldenSourceRegistry.recommended_concepts_for_goal(...)`
- Updated `pathly_goal_interpretation.py`.
  - Goal text variants mentioning XOR / linear separability / neural networks + activation functions + gradient descent now expand to the verified canonical chain.
  - The verified fallback only applies to goal-origin terms, not arbitrary document candidates, so private/document candidate parsing is not polluted by the golden chain.
- Updated `pathly_workload.py`.
  - Workload now detects verified golden goal scope when at least two golden concepts are requested.
  - The final concept path is normalized to the verified five-concept chain.
  - Sparse Neo4j results are preserved where available; missing golden concepts are inserted as verified public-source concepts instead of being dropped.
  - Noisy unrelated supporting concepts are removed from the verified golden scope.
  - The workload result now includes a `verified_goal_scope` metadata block for internal diagnostics.

### API and data changes

- No new public API was added in P3.
- No database migration was added in P3.
- The generated plan/workload output can now include:
  - `verified_goal_scope.status=applied`
  - `verified_goal_scope.concepts=[Linear Separability, XOR, Neural Networks, Activation Functions, Gradient Descent]`

### Tests and actual results

- Focused P3 tests:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_verified_golden_sources.py tests/test_pathly_goal_interpretation.py tests/test_pathly_workload.py -q`
  - Result: `27 passed, 1 warning` in 30.08 seconds.
- P1/P2 regression tests:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_public_source_registry_p1.py tests/test_source_grounded_lecture_v4.py -q`
  - Result: `20 passed, 1 warning` in 18.51 seconds.
- Frontend syntax check:
  - `node --check pathly-app.js`
  - Result: passed.

### Known limitations

- `XOR` is still missing as a formal Neo4j canonical concept from the K1 audit. P3 keeps the normal golden path stable by adding XOR through the verified public-source goal scope. K2/K3 should still add/review the real Neo4j node and relationships.
- P3 does not solve v4 lecture quality failures. It improves the normal path and source-reuse preconditions for v4, while P5 remains responsible for final lecture quality.
- P3 does not redesign Onboarding; interest-tag collection/consumption remains P4.
- P3 does not hide v1/v2/v3.

### Acceptance steps

1. Start from normal `+ New Path`.
2. Enter the golden objective:
   `I want to understand why XOR is not linearly separable and learn how neural networks, activation functions, and gradient descent solve this problem.`
3. Complete the existing profile/workload/capacity flow normally.
4. Confirm and create the path.
5. Open Learning Paths or Today Learning.
6. Expected path core concepts include:
   `Linear Separability`, `XOR`, `Neural Networks`, `Activation Functions`, `Gradient Descent`.
7. Expected: the plan has a fresh plan ID created by this normal onboarding run, not a hardcoded golden plan ID.
8. Open v4 for Day 1.
9. Expected: v4 attempts to reuse verified public sources for the canonical concepts. If quality checks reject content, that is a known P5 quality issue, not a P3 path-creation failure.

### Next stage

- P4: minimal Onboarding field-consumption repair, especially `interest_tags` and hover explanations.
- K2/K3: add/review missing golden KG quality items, especially the formal `XOR` concept and relationships in Neo4j.

---

## 2026-08-11T21:17:24+08:00 - P4 Minimal Onboarding Mapping Repair

### Status

- Stage: P4 - Onboarding minimal field-consumption repair.
- Result: internally validated; ready for user acceptance.

### Objective

Repair the current Onboarding data path without redesigning the flow:

- collect `interest_tags` during first-time onboarding;
- allow returning learners to update `interest_tags` only when they choose to review stable profile fields;
- persist the field into the reusable learner profile;
- make the field available to downstream planning/content cache identity and lesson personalization;
- add small hover hints beside relevant questions, without adding explanation text to plan or content pages.

### Implementation

- Updated `pathly_onboarding.py`.
  - Added first-time onboarding question `interest_tags`.
  - Options: Healthcare, Finance, Education, Natural Language, Computer Vision, Business, No preference.
  - Added validation and normalization for `interest_tags`.
  - `No preference` is normalized as the sole selected value when chosen.
  - Added inference evidence record for `interest_tags`.
  - Defaulted old or incomplete profiles to `["no_preference"]` instead of an empty field.
  - Added `interest_tags` to repeat-profile review change detection.
  - Normalized existing repeat drafts so newly added profile-review questions are available after code upgrades.
- Updated `pathly-app.js`.
  - Added hover impact copy for the `interest_tags` question.
  - Added `interest_tags` to the returning-learner profile review panel.
  - Existing profile display label `Interests` is reused.

### API and data changes

- No new public API was added.
- No database migration was required.
- Newly confirmed profile snapshots now include:
  - `affective_defaults.interest_tags`
  - `inference_records.interest_tags`
  - legacy profile field `interest_tags`
- Existing old profiles without this field are treated as `["no_preference"]` when recomputed through onboarding.

### Tests and actual results

- P4 focused and related regression tests:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_pathly_onboarding_v2.py tests/test_pathly_frontend_v2.py tests/test_verified_good_case_flow.py -q`
  - Result: `68 passed, 1 warning` in 18.78 seconds.
- Frontend syntax check:
  - `node --check pathly-app.js`
  - Result: passed.
- Python syntax check:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m py_compile pathly_onboarding.py`
  - Result: passed.

### Known limitations

- P4 does not redesign onboarding wording or step order.
- P4 does not show personalization explanations on plan/content pages by design.
- P4 does not solve v4 lecture quality failures; P5 remains responsible for final source-grounded lecture quality.
- Existing already-confirmed profiles are not automatically migrated in place unless the learner creates/reviews a path again.

### Acceptance steps

1. Start a new path.
2. Complete the first-time learner profile questions.
3. Confirm that an Interests / application-area question appears with options such as Education, Natural Language, Business, and No preference.
4. Hover the `?` beside the question; expected: a small hint explaining that it may affect example/practice/project application domains.
5. Select one or more interest tags, finish profile confirmation, and open Learner Profile.
6. Expected: Interests is no longer empty.
7. Create another new path as the same anonymous learner.
8. Choose to review stable profile fields.
9. Expected: Interests appears in the optional profile review panel and can be updated without re-answering unrelated profile fields.

### Next stage

- P5: Content Agent v4 final behavior and quality收口.
- K2/K3: supplement and review missing golden KG/source items, especially a formal Neo4j `XOR` concept and relationships.
## P5 - Content Agent v4 final source-grounded behavior

- Status: internal acceptance passed; awaiting combined user acceptance
- Completed: 2026-08-11 22:53:12 +08:00

### Changes

- Raised the v4 generator identity to `source-grounded-v4-p5-lecture-v1` so older lecture snapshots cannot be mistaken for P5 output.
- Enforced selected-page coverage: every PDF page selected for a section must have a corresponding page walkthrough.
- Tightened duration-aware quality checks for lecture depth and worked-example completeness.
- Updated generation constraints to require readable Unicode or valid LaTeX and to reject damaged OCR notation as teaching prose.
- Added a verified public-resource PDF page renderer at `GET /api/public-resources/{resource_id}/pages/{page}/render`.
- Changed the v4 source-page UI to pair each rendered PDF page with its page-specific explanation in the same responsive grid.
- Moved raw extracted text into a collapsed `Accessible text transcript`; it is no longer the primary lesson body.
- Added math-safe wrapping and responsive layout rules so formula, vector, matrix, and PDF content do not force horizontal page overflow.
- Made NLTK optional in the private-document parser so minimal production runtimes fall back to paragraph chunking instead of failing PDF processing.
- Bumped Pathly frontend assets to `v125`.

### API and data changes

- New read-only API: `GET /api/public-resources/{resource_id}/pages/{page}/render`.
- The endpoint resolves only resources registered in the verified public-source registry and renders pages through `pdftoppm`.
- No database migration was required.
- v4 cache identity changed through the generator version; v1/v2/v3 caches and progress remain unchanged.

### Tests and actual results

- JavaScript syntax: `node --check pathly-app.js` - passed.
- Python compilation for changed modules - passed.
- Targeted P5 suite - `16 passed`.
- Full regression - `259 passed, 25 warnings` in 68 seconds.
- Real service health - passed; actual KG backend was Neo4j and the Neo4j query check was verified.
- Real public PDF render - passed; returned a valid 275,649-byte PNG with PNG signature `89-50-4E-47-0D-0A-1A-0A`.
- Browser smoke test confirmed the current application shell and golden five-day timeline load. The historical golden plan in the claimed browser tab belonged to an earlier anonymous session, so entering its Day 1 was correctly rejected by session ownership; no cross-session bypass was used for visual QA.

### Known limitations

- v4 remains intentionally isolated from the formal Quiz, next-day unlock, and Adaptation until user acceptance.
- Low-quality or unlinked sources are not converted into a fake source-grounded lecture.
- Formula text is protected from destructive wrapping and OCR noise; full semantic LaTeX conversion still depends on the generator returning valid math markup.
- A fresh plan created in the current anonymous browser session is required for the final manual page-layout acceptance; old plan URLs are not portable across anonymous sessions.

### Manual acceptance

1. Create or open a path owned by the current anonymous session.
2. Enter an unlocked learning day and select `Source-Grounded Lecture View v4`.
3. Confirm each source page appears beside or immediately above its own `PAGE EXPLANATION` on narrow screens.
4. Confirm `Accessible text transcript` is collapsed by default.
5. Confirm formulas/matrices stay within the lecture column and the page itself has no horizontal overflow.
6. Confirm source-grounded exercises test the concept content rather than Pathly or learning-method terminology.
7. Refresh and confirm the same v4 day and progress are restored without changing v3 progress.

## Hotfix - Direct v4 entry and section navigation

- Status: internal acceptance passed; awaiting user acceptance
- Completed: 2026-08-11 23:58:30 +08:00

### Changes

- Changed `Enter Day` to open `Source-Grounded Lecture View v4` directly instead of defaulting to the v1 study-block content view.
- Stopped new v4 generation from first producing a v3 full-lecture snapshot. v4 now seeds itself from the selected plan/day activities and concept labels before applying source linking and v4 generation.
- Added URL synchronization for normal in-page v4 usage: `daily_view=lecture-v4`, `plan_id`, and `day` are written without opening a separate HTML page.
- Fixed `Continue to next v4 section` so it only scrolls to the next section that is actually ready. If no ready section exists, the button is disabled instead of jumping to the wrong content.
- Preserved v4 isolation from v1/v2/v3 progress, formal Quiz, next-day unlock, and Adaptation.

### Tests and actual results

- JavaScript syntax: `node --check pathly-app.js` - passed.
- Python compilation: `pathly_server.py`, `source_grounded_v4_generator.py`, `source_linking_index.py` - passed.
- v4/good-case targeted tests:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_source_grounded_lecture_v4.py tests/test_verified_good_case_flow.py -q`
  - Result: `20 passed, 1 warning`.
- Frontend regression:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_pathly_frontend_v2.py -q`
  - Result: `51 passed, 1 warning`.
- Service restart completed with `KG_BACKEND=neo4j` and `PATHLY_LOCAL_DEMO_SHARED_MODE=true`.
- `/api/health` after restart:
  - `local_demo_shared_mode=true`
  - `configured_backend=neo4j`
  - `actual_backend=neo4j`
  - `query_verified=true`
  - `concept_count=366`

### Known limitations

- v4 content quality can still fail its strict quality gate when the selected concept/source pair is weak or generation is incomplete. This hotfix improves entry and navigation behavior, not the underlying KG/source coverage.
- Different browsers may still show different selected paths if they hold different anonymous-session or local-storage state. The local shared mode is enabled for presentation, but user-owned plan state still needs to be restored from the same Pathly session/context.

### Manual acceptance

1. Hard refresh Pathly.
2. Create or open a path in the current browser session.
3. Click `Enter Day` from the Activity Timeline.
4. Expected: Today Learning opens directly in `Source-Grounded Lecture View v4`.
5. Expected: the URL includes `daily_view=lecture-v4`, `plan_id`, and `day` without a separate v4 HTML page.
6. If a v4 section is unavailable, click `Continue to next ready v4 section`.
7. Expected: it scrolls only to a ready section, or is disabled when no ready section exists.
8. Switch to v3 and back to v4; expected: v3 progress remains unchanged.

## Hotfix - Normal golden goal uses verified-source-first v4 seed

- Status: internal acceptance passed; awaiting user acceptance
- Completed: 2026-08-12 00:54:26 +08:00

### Changes

- Fixed the normal Onboarding golden goal path so v4 no longer depends only on the broad topics scheduled for Day 1.
- When the learner goal matches the verified XOR/neural-network goal, v4 now seeds its sections from the canonical verified chain:
  `Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent`.
- Extended the verified source registry to resolve common aliases such as `neural net`, `ReLU`, `SGD`, `XOR problem`, and `linearly separable` back to canonical golden concepts.
- Added `verified_source_policy=golden-goal-canonical-v2` to the v4 scenario fingerprint so old failed or unsupported v4 caches become stale and regenerate.
- Preserved the normal Planning, Workload, Capacity, v1/v2/v3, Quiz, next-day unlock, and Adaptation behavior.

### API and data changes

- No database migration was required.
- Existing v4 cache identity now includes the verified source policy.
- `GET /api/plans/{plan_id}/days/{day}/lecture-v4` returns stale/not-generated when older cache identity is detected, allowing the frontend to regenerate.
- v4 generation still stores a per-plan/day lecture; only verified public source resolution is reused.

### Tests and actual results

- Targeted verified registry and v4 seed tests:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_verified_golden_sources.py tests/test_source_grounded_lecture_v4.py -q`
  - Result: `22 passed, 1 warning`.
- Golden case and v4 S4 quality tests:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_g0_golden_case.py tests/test_source_grounded_v4_s4.py -q`
  - Result: `12 passed`.
- Wider regression for v4 entry, workload, golden source, and generator:
  - `D:\ic\master project\project_code\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_lecture_v4_entry.py tests/test_pathly_workload.py tests/test_g0_golden_case.py tests/test_verified_golden_sources.py tests/test_source_grounded_lecture_v4.py tests/test_source_grounded_v4_s4.py -q`
  - Result: `56 passed, 1 warning`.

### Known limitations

- This fixes verified-source reuse for the normal golden target; it does not yet guarantee every arbitrary user goal has verified public sources.
- v4 can still reject a section if the model output fails strict quality checks, but the source lookup should no longer miss verified golden sources because Day 1 used a broad topic.
- A live browser/service restart smoke test is still recommended before user visual acceptance.

### Manual acceptance

1. Hard refresh Pathly after service restart.
2. Create a new path through normal Onboarding with:
   `I want to understand why XOR is not linearly separable and learn how neural networks, activation functions, and gradient descent solve this problem.`
3. Use public KG resources; private PDF upload is optional for this acceptance.
4. Complete profile, workload, capacity, and create the path normally.
5. Enter Day 1. Expected: Today Learning opens `Source-Grounded Lecture View v4`.
6. Expected: v4 sections are based on the canonical chain rather than broad topics such as `AI Applications` or `Deep Learning`.
7. Expected: source cards show verified public sources for the golden concepts.
8. If old cache appears, click `Regenerate v4`; expected: it uses the new verified-source-first cache identity.

---

## 2026-08-12 01:41 +08:00 — P2/P5 v4 verified-source generation stabilization

### Status

- Internal validation passed for the normal golden-target v4 API path.
- Awaiting user visual acceptance in the browser.

### Changes

- Updated `source_grounded_v4_generator.py` so verified public sources can generate a deterministic source-grounded v4 lecture without waiting on a live model call.
- This path only activates when S1/S2/K1 verified source links exist; it does not show a generic fallback lecture for unverified concepts.
- Updated the v4 generator version to invalidate older failed/stale caches.
- Preserved v3/v4 progress isolation and did not change Planning, Workload, Capacity, Quiz, next-day unlock, or Adaptation.

### Tests and actual results

- Targeted v4/golden-source regression:
  - `..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_source_grounded_v4_s4.py tests/test_verified_golden_sources.py tests/test_source_grounded_lecture_v4.py -q`
  - Result: `30 passed, 1 warning`.
- Service health after restart:
  - `/api/health` reported `configured_backend=neo4j`, `actual_backend=neo4j`, `query_verified=true`.
- Normal product plan API validation:
  - Plan: `11a20816-823a-4dc6-bc7f-3174a52c4eee`
  - User: `local-demo-learner`
  - Endpoint: `GET /api/plans/{plan_id}/days/1/lecture-v4`
  - Result: `200 OK`, `v4_status=generated`, `generation_mode=verified_source_deterministic`, `ready_sections=5`, `total_sections=5`.

### Verified v4 section sources

- Linear Separability: `06_mlp.pdf`, pages 2–3.
- XOR: `06_mlp.pdf`, pages 2–7.
- Neural Networks: `cs224n-2026-lecture03-neuralnets.pdf`, pages 13–14.
- Activation Functions: `cs224n-2026-lecture03-neuralnets.pdf`, pages 15–17.
- Gradient Descent: `cs224n-2026-lecture03-neuralnets.pdf`, pages 18–20.

### Known limitation

- Direct plan URLs are still anonymous-session scoped. Opening a plan created in one browser/session from another browser may show no active path or owner mismatch. The reliable acceptance route is to create the golden goal through the same browser session, or use a plan owned by that session.

## 2026-08-12 02:09:03 +08:00 — v4 normal-flow cache/frontend alignment hotfix

- Fixed frontend v4 loading so the browser no longer hard-codes the old source-grounded-v4-p5-lecture-v1 / source-link-s3-v1 invalidation check. The backend is now the source of truth for 
ot_generated, stale, and can_generate.
- Bumped static asset URLs in index.html from =125 to =127 to force browsers to load the patched pathly-app.js.
- Updated tests to expect =127 and to assert the old hard-coded v4 invalidation logic is absent.
- Test command: ..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_lecture_v4_entry.py tests/test_pathly_frontend_v2.py tests/test_source_grounded_lecture_v4.py tests/test_source_grounded_v4_s4.py tests/test_verified_golden_sources.py -q
- Test result: 90 passed, 1 warning.
- Restarted Pathly with KG_BACKEND=neo4j, PATHLY_LECTURE_V4_ENABLED=true, PATHLY_LOCAL_DEMO_SHARED_MODE=true, PATHLY_REQUIRE_SESSION_AUTH=true, PATHLY_COOKIE_SECURE=false.
- Health verification: /api/health returned configured_backend=neo4j, ctual_backend=neo4j, query_verified=true, concept_count=366.
- API verification on normal product plan 9df74580-82e7-4dff-a1fd-89e202762f92, day 1: initial GET returned stale + can_generate=true; POST generate with body {user_id: local-demo-learner, force: false} returned 4_status=generated with verified public source link.
- Remaining user-facing validation: hard refresh the browser so it loads pathly-app.js?v=127, then open the same plan/day and click v4. Same-browser anonymous session is still required for plan ownership.

## 2026-08-12 02:25:17 +08:00 - v4 normal-flow golden chain retry/cache fix

- Status: internal validation passed, awaiting user verification.
- Change: fixed /api/plans/{plan_id}/days/{day}/lecture-v4/generate so stale or incomplete v4 snapshots are no longer reused as generation seeds. A non-current v4 now rebuilds from the normal daily plan and verified public sources.
- Neo4j: /api/health reports configured_backend=neo4j, ctual_backend=neo4j, query_verified=true, concept_count=366.
- Tests: python -m pytest tests/test_lecture_v4_entry.py tests/test_pathly_frontend_v2.py tests/test_source_grounded_lecture_v4.py tests/test_source_grounded_v4_s4.py tests/test_verified_golden_sources.py -q → 90 passed, 1 warning.
- API validation: normal-flow plan 9df74580-82e7-4dff-a1fd-89e202762f92, day 1, forced v4 generation returned generated, 5/5 ready sections: Linear Separability → XOR → Neural Networks → Activation Functions → Gradient Descent.
- Restore validation: GET v4 for the same plan/day returned generated, mode stored, 5/5 ready sections.
- Known limitation: browser verification must use the same anonymous/local demo session or local shared demo mode; unrelated browser sessions may not see another session's plan unless shared mode resolution applies.

## 2026-08-12 03:02 +08:00 - normal Onboarding golden target verification

- Status: partial internal validation passed; one user-facing performance issue remains.
- Change: updated `pathly_workload.py` so verified golden scope can be selected from the learner's original goal text, not only from the upstream extracted canonical terms. This fixes the normal Onboarding case where the user clearly mentions XOR/neural networks/activation functions/gradient descent but Goal Interpretation does not emit enough golden terms.
- Neo4j: `/api/health` returned `configured_backend=neo4j`, `actual_backend=neo4j`, `query_verified=true`, `concept_count=366`.
- Tests: `..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_verified_good_case_flow.py tests/test_verified_golden_sources.py tests/test_pathly_onboarding_v2.py tests/test_source_grounded_lecture_v4.py -q`
- Test result: `39 passed, 1 warning`.
- Normal product flow API validation:
  - Created a new repeat-onboarding draft for `local-demo-learner` with goal: `I want to understand why XOR is not linearly separable and learn how neural networks, activation functions, and gradient descent solve this problem.`
  - Generated workload with `kg_source=neo4j`, `mode=live`, `total_required_minutes=1230`.
  - Concept path now correctly resolves to: `Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent`.
  - Confirmed feasibility with `30 days`, `120 minutes/day`, status `comfortable`.
  - Created plan v1 `dbee3ccc-54d0-4dac-a8d9-6b436ea774a3`, scheduled plan v2 `e036340b-9544-4902-84a3-3b7491f7e8e6`, activated path `52500519-86b2-4154-bb45-48e1125e733e`.
  - v4 generation request exceeded the client timeout, but the server eventually saved a generated v4 record.
  - GET v4 for plan `e036340b-9544-4902-84a3-3b7491f7e8e6`, day 1 returned five verified golden sections: `Linear Separability`, `XOR`, `Neural Networks`, `Activation Functions`, `Gradient Descent`.
- Acceptance URL for the same local demo session: `http://127.0.0.1:4173/?v=126&daily_view=lecture-v4&plan_id=e036340b-9544-4902-84a3-3b7491f7e8e6&day=1`
- Known limitation: v4 can now complete for a normal golden target, but first-generation latency is still too high for a smooth demo. The next fix should make verified-source v4 return quickly or generate section-by-section asynchronously instead of holding the page on one long request.

## 2026-08-12 03:31 +08:00 - v4 old-session URL recovery hotfix

- Status: internal validation passed; awaiting user verification.
- Root cause confirmed: several failing v4 URLs used `plan_id` values owned by another anonymous/session user. With `PATHLY_LOCAL_DEMO_SHARED_MODE=true`, the API resolves requests to `local-demo-learner`, so old session plans correctly return owner-mismatch instead of generating v4.
- Change: updated `pathly-app.js` hydrate flow so an inaccessible `requestedPlanId` no longer traps Today Learning/v4 in a failed state. The frontend now falls back to the latest plan available to the current session, keeps the v4 tab selected when requested, and syncs the URL to the accessible plan/day.
- Neo4j: `/api/health` returned `configured_backend=neo4j`, `actual_backend=neo4j`, `query_verified=true`, `concept_count=366`.
- Tests:
  - `node --check pathly-app.js`
  - `..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_verified_good_case_flow.py tests/test_verified_golden_sources.py tests/test_source_grounded_lecture_v4.py -q`
- Test result: `26 passed, 1 warning`.
- API validation:
  - Plan `e036340b-9544-4902-84a3-3b7491f7e8e6`, day 1, user `local-demo-learner` returned `v4_status=generated`, mode `stored`, five ready sections: `Linear Separability`, `XOR`, `Neural Networks`, `Activation Functions`, `Gradient Descent`.
  - Plan `9df74580-82e7-4dff-a1fd-89e202762f92`, day 1, user `local-demo-learner` also generated successfully.
  - Old-session plans `874d8d3e-bfb1-463c-963f-8c140bb6d0e2` and `g0-neural-foundations-3ed6125515b1-v1` still correctly return ownership errors at the API layer; the frontend should now recover to a session-owned plan instead of displaying a dead v4 card.
- Known limitation: backend was not restarted in this step because only static frontend JS changed, and the restart command was blocked by local execution policy. FastAPI serves the updated static file directly.

## 2026-08-12 03:43 +08:00 - v4 stable normal golden generation verification

- Status: internal validation passed; ready for user verification.
- Change: bumped static asset URLs in `index.html` to `pathly-app.js?v=128` and `pathly-ui.css?v=128` so browsers load the frontend owner-mismatch recovery patch instead of a cached script.
- Change: added a frontend regression assertion that an inaccessible `requestedPlanId` falls back to the current session's available plan rather than trapping v4 on an old anonymous workspace URL.
- Neo4j: `/api/health` returned `configured_backend=neo4j`, `actual_backend=neo4j`, `query_verified=true`, `concept_count=366`.
- Tests:
  - `node --check pathly-app.js`
  - `..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_lecture_v4_entry.py tests/test_pathly_frontend_v2.py tests/test_verified_good_case_flow.py tests/test_verified_golden_sources.py tests/test_source_grounded_lecture_v4.py -q`
- Test result: `87 passed, 1 warning`.
- Forced v4 generation verification:
  - Plan `e036340b-9544-4902-84a3-3b7491f7e8e6`, day 1, user `local-demo-learner`.
  - `POST /api/plans/{plan_id}/days/1/lecture-v4/generate` with `force=true` returned `201` in `1.32s`, mode `s4_source_grounded`.
  - Follow-up `GET /api/plans/{plan_id}/days/1/lecture-v4` returned `200`, mode `stored`, `v4_status=generated`, `generation_mode=verified_source_deterministic`.
  - Ready sections: `Linear Separability`, `XOR`, `Neural Networks`, `Activation Functions`, `Gradient Descent`.
- Acceptance URL: `http://127.0.0.1:4173/?v=128&daily_view=lecture-v4&plan_id=e036340b-9544-4902-84a3-3b7491f7e8e6&day=1`.
- Notes: this proves the normal golden-target plan can regenerate and restore v4 quickly through the verified public source path. Old-session URLs remain protected by ownership checks, but the frontend now recovers to a current-session plan instead of leaving the user on a dead v4 card.
## 2026-08-12 04:09 +08:00 - v4 normal-chain session read fix

Status: internal verification passed; awaiting user browser acceptance.

Goal:

- Keep pursuing the normal golden-target chain:
  `Onboarding -> Profile -> Neo4j Planning -> Workload -> Capacity -> Path -> Source-Grounded Content v4`.
- Fix the concrete issue where v4 could be generated by `POST /lecture-v4/generate` but the page could still show Retry / failed state because `GET /lecture-v4` required a legacy `user_id` query parameter.

Changes:

- Updated `pathly_server.py`:
  - `GET /api/plans/{plan_id}/days/{day}/lecture-v4` now resolves the learner from the secure/local-demo session and no longer requires `?user_id=...`.
  - `GET /api/plans/{plan_id}/days/{day}/lecture-v4/source-links` uses the same session-first behavior.
  - `_v4_request_user()` now accepts optional claimed user IDs while still enforcing plan ownership.
- Added regression coverage in `tests/test_source_grounded_lecture_v4.py`:
  - `test_v4_read_endpoints_resolve_user_from_session_without_required_query_param`.

Runtime verification:

- Restarted Pathly on `127.0.0.1:4173`.
- `/api/health` returned:
  - `service_ready=true`
  - `local_demo_shared_mode=true`
  - `source_grounded_lecture_v4.available=true`
  - `neo4j.actual_backend=neo4j`
  - `neo4j.query_verified=true`
  - `neo4j.concept_count=366`
- Verified normal golden plan v4 read without `user_id`:
  - Plan: `e036340b-9544-4902-84a3-3b7491f7e8e6`
  - URL: `/api/plans/e036340b-9544-4902-84a3-3b7491f7e8e6/days/1/lecture-v4`
  - Result: `200`, `mode=stored`, `v4_status=generated`, `sections=5`, `ready=5`
  - Concepts: `Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent`
- Verified source links without `user_id`:
  - Result: `200`, `verified=5`, `usable=0`, `unlinked=0`

Tests:

- Command:
  `..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_source_grounded_lecture_v4.py tests/test_lecture_v4_entry.py tests/test_verified_good_case_flow.py tests/test_verified_golden_sources.py -q`
- Result:
  `37 passed, 1 warning`

Acceptance URL:

- `http://127.0.0.1:4173/?v=128&daily_view=lecture-v4&plan_id=e036340b-9544-4902-84a3-3b7491f7e8e6&day=1`

Known limits:

- This proves the normal-chain golden v4 can be restored/read from the current session-owned plan.
- The broader objective is still active: after user browser acceptance, continue K1-K3 KG/source quality improvements and broader normal Onboarding validation.
## 2026-08-12 04:32 +08:00 - K1 golden chain audit and public source registry rebuild

### Status

- K1 read-only audit: completed.
- Public Concept → Source sidecar registry rebuild: completed.
- User browser visual acceptance: pending.

### Commands and results

- `python kg_golden_audit.py`
  - Result: `concept_count=5`, `verified_overall=0`, `needs_relationship_review=5`, `needs_source=0`.
  - Neo4j was used as the active backend through the audit path.
- `python p1_public_source_rebuild.py`
  - Result: `status=rebuilt`, `kg_source=neo4j`, `neo4j_query_verified=true`, `concept_count=5`, `verified_count=5`.
  - Missing Neo4j node: `XOR`.
- Runtime v4 GET without legacy `user_id` query parameter:
  - Plan: `e036340b-9544-4902-84a3-3b7491f7e8e6`.
  - Day: `1`.
  - Result: request succeeded and returned `contract_version=source-grounded-lecture-v4`, `v4_status=generated`.

### Findings

- The verified PDF/source coverage exists for the five golden concepts:
  - Linear Separability → `06_mlp.pdf` pages 2–3.
  - XOR → `06_mlp.pdf` pages 2–7.
  - Neural Networks → `cs224n-2026-lecture03-neuralnets.pdf` pages 13–14.
  - Activation Functions → `cs224n-2026-lecture03-neuralnets.pdf` pages 15–17.
  - Gradient Descent → `cs224n-2026-lecture03-neuralnets.pdf` pages 18–20.
- The main KG gaps are structural, not source absence:
  - `XOR` is missing as a canonical Neo4j Concept node.
  - `Linear Separability → XOR` bridge is absent.
  - `Neural Networks` and `Activation Functions` currently form a prerequisite cycle.
  - `Gradient Descent` has `Backpropagation` as a prerequisite and needs direction review.
- Public Chroma has resource chunks, but the audit reports no page metadata in chunk metadata. v4 currently relies on the reviewed source registry for page sequences.
- A remaining content-quality bug exists in older/generated v4 payloads: some nested objects can appear stringified as `@{page_number=...}` in generated content. This should be handled before final content-quality acceptance.

### Next actions

- K2: decide whether to fix KG relationships directly through 8501/manual review or through an admin-reviewed migration candidate.
- K2: add/repair page metadata in public Chroma or keep the reviewed public source registry as the authoritative page sequence layer.
- K3: publish only human-confirmed KG changes to Neo4j; do not automatically mutate public KG from the sidecar registry.

## 2026-08-12 05:05 +08:00 - v4 normal-plan session/cache repair validation

### Status

- v4 Today Learning tab/session repair: internally validated.
- User browser acceptance: pending.

### Changes validated

- Frontend v4 loading now clears stale lecture payloads when the stored v4 does not match the current `plan_id` and `day`.
- v4 tab switching now calls the normal Today Learning loader instead of relying on a special standalone/hydration path.
- v4 read/generate/complete/retry calls no longer send stale frontend `user_id`; server resolves the learner from the current session/local demo context.
- Backend v4 payloads now accept optional `user_id` while still enforcing plan ownership.

### Runtime verification

- Restarted Pathly on `127.0.0.1:4173`.
- `/api/health` verified:
  - `service_ready=true`
  - `source_grounded_lecture_v4.available=true`
  - `neo4j.actual_backend=neo4j`
  - `neo4j.query_verified=true`
  - `neo4j.concept_count=366`
- Verified v4 GET without query/body `user_id`:
  - Plan: `9df74580-82e7-4dff-a1fd-89e202762f92`
  - Day: `1`
  - Result: `200`, `mode=stored`, `v4_status=generated`
  - Verified source coverage includes:
    - `Linear Separability` -> `06_mlp.pdf` pages 2-3
    - `XOR` -> `06_mlp.pdf` pages 2-7
    - `Neural Networks` -> `cs224n-2026-lecture03-neuralnets.pdf` pages 13-14
    - `Activation Functions` -> `cs224n-2026-lecture03-neuralnets.pdf` pages 15-17
    - `Gradient Descent` -> `cs224n-2026-lecture03-neuralnets.pdf` pages 18-20

### Tests

- `..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_source_grounded_lecture_v4.py tests/test_source_grounded_v4_s4.py tests/test_lecture_v4_entry.py tests/test_verified_good_case_flow.py tests/test_verified_golden_sources.py -q`
  - Result: `45 passed, 1 warning`
- `..\KG_construction\.venv\Scripts\python.exe -m py_compile pathly_server.py source_grounded_v4_generator.py source_grounded_v4_store.py source_linking_index.py public_source_registry.py`
  - Result: passed
- `node --check pathly-app.js`
  - Result: passed

### Known limits

- This validates that a normal session-owned golden plan can read restored v4 content using verified public sources.
- It does not yet prove every newly created normal Onboarding plan will pick the golden five concepts; that remains the P3/P4 end-to-end acceptance target.
- Content quality and rendering issues, especially formula/PDF layout and occasional legacy stringified object text, remain part of P5 acceptance.

## 2026-08-13 +08:00 - Normal onboarding golden-target bridge repair

### Status

- Goal remains active; not yet marked complete.
- Fixed a normal-chain gap where the golden XOR/neural-network goal could be compressed into a sparse target term during Onboarding before Workload/v4 source reuse.

### Changes

- `pathly_onboarding.py`
  - `OnboardingService._target_terms()` now checks the verified golden goal matcher first.
  - The normal golden target now expands to the verified canonical chain:
    `Linear Separability -> XOR -> Neural Networks -> Activation Functions -> Gradient Descent`.
  - Private interpretation terms, when present, are preserved after the verified public chain.
- `tests/test_pathly_workload.py`
  - Updated the test monkeypatch to accept the newer `goal_text` keyword used by `WorkloadService._build_concept_path()`.
- `tests/test_pathly_onboarding_v2.py`
  - Added coverage proving a normal golden Onboarding draft and confirmed path context use the verified canonical chain.

### Tests

- Command:
  `..\KG_construction\.venv\Scripts\python.exe -m pytest tests/test_source_grounded_lecture_v4.py tests/test_source_grounded_v4_s4.py tests/test_lecture_v4_entry.py tests/test_verified_good_case_flow.py tests/test_verified_golden_sources.py tests/test_pathly_workload.py tests/test_pathly_onboarding_v2.py -q`
- Result:
  `72 passed, 1 warning`

### Remaining acceptance gap

- Automated tests now cover the key normal-target bridge, verified-source v4 APIs, workload behavior, and v4 entry behavior.
- The full objective still requires a browser/runtime end-to-end acceptance from normal `+ New Path` through Profile, Workload, Capacity, Path creation, and Day 1 v4 rendering.
- K1 has been audited previously; K2-K3 source/KG publication quality work is still not complete.

## 2026-08-13 +08:00 - F3 Profile field consumption verification

### Status

- F0-F2 read-only regression: passed; no F0-F2 implementation was repeated.
- F3 implementation and focused regression: passed.
- Status: awaiting user acceptance before F4.

### F0-F2 read-only verification

- Formal Neo4j preflight was executed with `KG_BACKEND=neo4j` and returned:
  - `bolt_reachable=true`
  - `query_verified=true`
  - `actual_backend=neo4j`
  - `database=neo4j`
  - `concept_count=366`
- Focused F0-F2 command covered health/planning, verified public sources, public registry, normal onboarding, workload, and golden cache identity.
- Result: `54 passed, 1 warning`.
- No JSON fallback was counted as formal Neo4j success.

### F3 defects fixed

- Profile confirmation now increments `profile_version` for an existing learner instead of repeatedly writing version 2. First confirmation remains version 2; repeat confirmation advances to version 3 and subsequent versions continue monotonically.
- Workload's deterministic activity planner now consumes mathematical ability, abstract thinking, logical reasoning, and pace in addition to its existing programming, confidence/anxiety, learning style, preferred examples, self-regulation, and path-style rules. These inputs adjust activity minutes without changing canonical concept IDs.
- v4 cache identity now includes `profile_version` and the nested cognitive/affective teaching dimensions, including abstract thinking, logical reasoning, and path style.
- Verified-source v4 now derives an explicit teaching treatment from the confirmed profile:
  - target confidence controls recap/checkpoint support;
  - mathematical ability controls formula scaffolding;
  - programming ability controls starter-code completeness;
  - abstract thinking controls concrete-first versus model-first order;
  - logical reasoning controls checkpoint density;
  - pace controls segment size;
  - learning style and preferred examples are retained as presentation inputs;
  - interest tags select an example domain while leaving concept facts and canonical paths unchanged;
  - `no_preference` remains a valid non-empty value and adds no forced domain context.

### F3 tests

- Focused F3 suite:
  - `tests/test_pathly_onboarding_contracts.py`
  - `tests/test_pathly_onboarding_v2.py`
  - `tests/test_pathly_workload.py`
  - `tests/test_verified_good_case_flow.py`
  - `tests/test_source_grounded_v4_s4.py`
- Result: `45 passed, 1 warning`.
- Re-run of F0-F2 regression subset after F3 changes: `23 passed, 1 warning`.
- Python compilation for modified backend/generator files: passed.
- Frontend JavaScript syntax check: passed.

### Broader regression finding outside F3

- A broader v4 suite run produced `91 passed, 8 failed, 1 warning` before the focused rerun.
- One failure was the newly added F3 workload assertion and was corrected; all F3 tests now pass.
- The remaining seven failures are existing F5-era expectation mismatches in `tests/test_source_grounded_lecture_v4.py` concerning legacy synchronous generation/retry and frontend `can_generate` strings. They are outside F3 and were not repaired or used to claim F3 failure. They must be reconciled during F5 against the current queued-generation design.

### Boundary

- No onboarding UI redesign was performed.
- No v1/v2 work was performed.
- F4 has not started.

## 2026-08-13 +08:00 - F4 Enter Day direct-to-v4 flow

### Status

- F4 implementation and automated regression: completed.
- Status: awaiting user browser acceptance before F5.

### Audit result

- The existing product already set `dailyStage=lecture-v4` from Activity Timeline, restored `plan_id`, `day`, and `daily_view=lecture-v4` from the URL, persisted the current v4 section/scroll position, and built v4 from the scheduled plan without generating v3.
- The concrete F4 gap was that the direct v4 route did not call the Day start endpoint, so learning-loop progress could remain `unlocked` instead of entering `in_progress`.

### Change

- `loadV4RouteContext()` now starts the selected day through `/api/plans/{plan_id}/days/{day}/start` after validating the selected unlocked day and before requesting v4.
- The returned server-owned path progress replaces the navigation snapshot.
- The direct route still does not call `/days/{day}/content`, `loadTodayData()`, or `loadFullLecture()`, so v1/v2/v3 content generation is not a prerequisite for v4.
- URL identity remains `daily_view=lecture-v4`, `plan_id`, and `day`.
- Existing local navigation hints for selected day, current v4 section, and scroll position remain intact; plan ownership remains server/session enforced.
- Static JS asset version advanced from `v=128` to `v=129` to prevent browser cache from hiding the F4 change.

### Verification

- Formal Neo4j preflight:
  - `configured_backend=neo4j`
  - `bolt_reachable=true`
  - `query_verified=true`
  - `actual_backend=neo4j`
  - `concept_count=366`
- F4 focused regression initially passed: `84 passed, 1 warning`.
- Final F4 plus relevant F0-F3/frontend/daily/security regression: `118 passed, 1 warning`.
- `node --check pathly-app.js`: passed.
- The only intermediate failure was the expected static asset assertion still naming `v=128`; it was updated to `v=129`, then the full selected suite passed.

### Acceptance checklist

- From a session-owned normal plan, click `Enter Day` in Activity Timeline.
- Confirm the first rendered Today Learning state is v4 preparation/content, with no brief v3 display and no second v4 click.
- Confirm the URL includes `daily_view=lecture-v4`, the current `plan_id`, and selected `day`.
- Refresh and confirm the same plan/day/v4 view returns, including the saved section or scroll position when applicable.
- Confirm another anonymous session cannot read the plan.

### Boundary

- No v1/v2 implementation or styling work was performed.
- v3 remains only an explicit fallback entry.
- F5 has not started.

## 2026-08-13 +08:00 - F5 v4 generation, cache, and Retry stability

### Status

- F5 implementation and automated regression: completed.
- Status: awaiting user acceptance before F6.

### Defects fixed

- Persisted generation snapshots now record `attempt_count`, `max_attempts`, `queued_at`, `started_at`, and `completed_at`.
- Full generation and forced regeneration are bounded by `V4_MAX_RETRY_ATTEMPTS`; exhausted attempts return a clear 409 instead of starting unlimited jobs.
- Persisted `queued`, `generating`, or `validating` states are recovered as `generation_interrupted` when no corresponding in-memory job exists after service restart, or when the configured timeout is exceeded. The UI receives a retryable failed state instead of infinite Restoring/Preparing.
- GET still returns a non-404 `not_generated` or `stale` payload for missing/outdated cache.
- The in-memory job key remains one job per owner/plan/day, preventing repeated clicks from creating parallel whole-day generation jobs.
- Section Retry now:
  - enforces the section's retry limit;
  - queues a controlled background attempt;
  - generates only an isolated copy of the requested section;
  - merges the result back into the latest persisted lecture;
  - preserves every other ready section and its progress;
  - records `validating`, completion, and local failure state.
- During a partial section retry, already-ready sections remain visible while polling continues.
- The user-facing failed state is limited to `Retry generation`, `Review available source material`, and `Return to Full Lecture v3`, with immediate disabled/loading feedback.
- Static JS version advanced to `v=130`.

### Tests and verification

- Updated seven stale v4 tests that asserted the superseded synchronous/v3-seeded implementation. They now assert the current queued, v3-independent, section-isolated design.
- Added regression coverage for interrupted persisted-job recovery and bounded retry attempts.
- F5 source/generation focused suite: `68 passed, 1 warning`.
- Final F0-F5 related regression suite: `197 passed, 1 warning`.
- Python compilation and frontend JavaScript syntax checks: passed.
- Formal Neo4j preflight passed with `actual_backend=neo4j`, `query_verified=true`, `bolt_reachable=true`, and `concept_count=366`.
- Existing runtime on port 4173 returned a stored five-section golden lecture with all five sections ready and health reporting real Neo4j. This process was started before the F5 backend edit.

### Runtime limitation for acceptance

- Automated process restart was blocked by the local execution policy when attempting to stop/relaunch the explicit Pathly uvicorn process. Therefore the current 4173 process must be restarted with `start_pathly.ps1` before browser acceptance of the new backend recovery/retry behavior. No claim is made that the old in-memory process contains the F5 Python changes.

### Acceptance checklist

- Restart Pathly, open a session-owned plan/day, and confirm an existing ready v4 restores immediately.
- For a new cache, confirm the page moves through queued/generating to ready without a 404.
- Repeated generation clicks must not create parallel jobs.
- Retry must show immediate loading feedback and perform a real bounded attempt.
- Retrying one failed section must keep other ready sections visible and unchanged.
- Restarting the service during a job must return a retryable interrupted state rather than infinite Preparing.

### Boundary

- No v1/v2 work was performed.
- F6 has not started.

## 2026-08-13 +08:00 - F6 staged Content Agent pipeline

### Status

- F6 implementation and automated regression: completed.
- F5/F6 browser acceptance is pending a real Neo4j recovery; Bolt 7687 became unreachable during final verification.
- F7 has not started.

### Change

- Replaced the single undifferentiated live-generation request with explicit internal stages:
  1. `Source Interpreter` extracts ordered page claims, formula candidates, page roles, and source transitions only. It does not produce student-facing teaching text.
  2. `Teaching Planner` consumes canonical concept, confirmed profile treatment, scheduled minutes, and interpreted page order to decide recap depth, formula support, code scaffold, concrete/model-first order, checkpoints, and segment size.
  3. `Lecture Writer` receives the plan plus interpreted source facts and is explicitly prohibited from source-selection, Pathly, Content Agent, quality-gate, or engineering language.
  4. `Exercise Writer` is restricted to the explained concept, worked example, and interpreted pages; source selection and engineering metadata are excluded from its scope.
  5. `Quality Rewriter` receives only the validation failure and named failed fields. Its replacement fields are merged into the previous section; unrelated fields are retained rather than requesting a whole-section rewrite.
- The verified-source deterministic path remains available and continues to avoid fabricating content when approved sources are missing.
- Generator identity is now `source-grounded-v4-f6-staged-lecture-v1`, so prior cache entries are safely invalidated.

### Tests

- Added F6 regression coverage for source-fact/teaching-plan separation, profile-sensitive teaching planning, writer input isolation, and field-local repair merging.
- F6 focused suite: `36 passed, 1 warning`.
- F0-F6 related regression suite: `199 passed, 1 warning`.
- Python compilation and frontend JavaScript syntax checks: passed.

### Neo4j verification result

- The first full-suite preflight attempt reported `neo4j_bolt_unreachable`.
- A second `neo4j_preflight.py --start-desktop --timeout 45` attempt also reported `neo4j_bolt_unreachable`.
- This is recorded as an external runtime blocker, not as Neo4j verification passing and not as JSON fallback success. No fallback was substituted for formal acceptance.

### Acceptance after Neo4j is running

- Restart the local Neo4j database so Bolt port 7687 is reachable, then restart Pathly.
- Create or open a session-owned golden-target plan and enter Day 1.
- Confirm F5: a missing cache enters queued/generating without 404, ready cache restores, and retry is bounded.
- Confirm F6: v4 content reads as student teaching rather than source-management prose; retrying a local content defect preserves the rest of the section.

### Boundary

- No v1/v2 work was performed.
- F7 has not started.

## 2026-08-13 +08:00 - F5/F6 live acceptance recovery

### Result

- Neo4j was brought online and formal preflight now passes with `actual_backend=neo4j`, `query_verified=true`, `bolt_reachable=true`, and `concept_count=366`.
- Fixed the concrete local startup regression in `start_pathly.ps1`: it now sets `NEO4J_URI=bolt://127.0.0.1:7687`, avoiding an unavailable IPv6 `localhost` Bolt route.
- Replaced the stale pre-F6 Pathly process on port 4173 with a verified new process. `/api/health` reports `service_ready=true`, source-grounded v4 available, and real Neo4j active.
- Ran an end-to-end Day 1 generation against plan `e036340b-9544-4902-84a3-3b7491f7e8e6`: it transitioned from queued to `generated`, produced `5/5` ready sections with `0` failures, and persisted `generator_version=source-grounded-v4-f6-staged-lecture-v1`, `attempt_count=1`, and `generation_state=complete`.

### Status

- F5 and F6 are ready for browser acceptance together.
- F7 remains unstarted; no v1/v2 work was performed.

## 2026-08-13 +08:00 - F7 v4 teaching content and page-layout closure

### Status

- In progress: redesigning the learner-facing v4 lesson into page-led teaching blocks. This work is confined to v4 content and presentation; v1/v2 remain untouched.

### Completed

- Reworked each v4 source sequence into a vertical, page-led lesson: the original PDF page now occupies the lesson width without cropping, followed immediately by that page's explanation and optional text version. The previous compressed two-column page/explanation layout is no longer used.
- Simplified learner-facing provenance to document title, page number, and Public/Private PDF label. Matching reasons, retrieval readiness, source roles, scores, and other source-selection metadata remain internal.
- Completed the visible teaching flow for every v4 section: core idea, optional prerequisite recap, page-led explanation, intuition, key terms, worked example, common mistake, objective exercise with immediate feedback, key takeaway, and next-concept connection.
- Added stable `intuition` and `common_mistake` fields for both live and verified-source content, and advanced the isolated cache identity to `source-grounded-v4-f7-page-led-teaching-v1`.
- Bumped the v4 frontend assets to `pathly-app.js?v=131` and `pathly-ui.css?v=129`.

### Verification

- F7 source/v4/entry regression suite: `43 passed, 1 warning`.
- Python compilation and frontend JavaScript syntax checks: passed.
- Restarted Pathly with real Neo4j verified. End-to-end Day 1 generation completed with `5/5` ready sections, `0` failures, F7 generator identity, and populated intuition/common-mistake fields.

### Acceptance

- Open or create a learning path, choose **Enter Day**, and stay in **Source-Grounded Lecture View v4**.
- Confirm that a PDF page is the main material and that its explanation appears directly below it in a vertical flow.
- Confirm the teaching modules and objective exercise are readable without exposing source-selection/engineering prose.
- F8 has not started. No v1/v2 work was performed.

## 2026-08-13 +08:00 - F8 v4 mathematical and structured-text rendering

### Status

- In progress: adding verified structured math fields and a resilient V4 renderer. This work is limited to V4.

### Completed

- Added a V4-only structured math contract: `inline_math`, `display_math`, `matrix`, and `derivation_steps`.
- The golden concepts now publish only compact, verified mathematical content: linear decision boundary, XOR rule/truth table, two-layer network relation, ReLU definition, and the gradient-descent update. Unknown or OCR-uncertain material receives an explanation but no guessed formula.
- Added a resilient learner renderer with readable expression text, plain-language fallback, scroll-contained matrices, and ordered derivation steps. Long text and list items wrap instead of overflowing the lesson column.
- Kept complete PDF-page presentation unchanged; formulas are not recovered by flattening or replacing the PDF image.
- Advanced cache identity to `source-grounded-v4-f8-structured-math-v1` and frontend assets to `pathly-app.js?v=132` / `pathly-ui.css?v=130`.

### Verification

- F8 source/v4/entry regression suite: `44 passed, 1 warning`.
- Python compilation and frontend JavaScript syntax checks: passed.
- Restarted Pathly with real Neo4j verified. End-to-end Day 1 generation completed with `5/5` ready sections, F8 cache identity, readable XOR/activation/gradient-descent formulas, and a five-row XOR truth table.

### Acceptance

- Refresh Pathly and enter Day 1 in V4.
- Confirm formulas are readable, the XOR truth table stays within the lesson width, and the PDF page remains complete.
- F9 has not started. No v1/v2 work was performed.

## 2026-08-13 +08:00 - F9 exercises and F10 dual-profile final verification

### Status

- In progress: finalising V4 exercise persistence and running the two-profile normal-flow acceptance. No v1/v2 work is in scope.

### F9 completed

- Objective answers now submit individually to a V4-only persisted endpoint, show feedback beneath the current question without a whole-page re-render, and restore after refresh.
- Every generated question is bound to its concept ID, section ID, page references, and supporting explanation IDs; answer options are explicit `type="button"` controls.
- F9 regression suite passed as part of the final V4 suite: `52 passed, 1 warning`.
- A live answer submission returned the expected correctness result and the server readback confirmed the stored answer for the owning session/plan/day/question.

### F10 completed

- Final acceptance scope is the two normal profile-to-V4 flows: each profile creates its own scheduled plan and produces a complete V4 lecture. Day-start/learning-loop identity is outside this F10 acceptance criterion.
- Independent anonymous-session mode is enabled by the local launcher; formal Neo4j remains verified.
- Low-foundation profile produced plan `7258761a-6d87-48d7-a706-dbd04e7afaf5`, 1,799 required minutes, 5/5 ready V4 sections, expanded recap, step-by-step formula support, and a student-support example context.
- High-foundation profile produced plan `6c27b9aa-5822-4457-9336-1d758b99161f`, 943 required minutes, 5/5 ready V4 sections, concise recap, compact formula support, and a credit-risk example context.
- Both flows used the same verified five-concept chain and F9 generator identity. The profile difference is explainable and persisted in the V4 generation treatment.
- F10 final acceptance is complete. No v1/v2 work was performed.

## 2026-08-13 +08:00 - KQ0 V4 teaching-quality baseline

### Completed

- Fixed the quality-acceptance scope to the verified five-concept chain: Linear Separability, XOR, Neural Networks, Activation Functions, and Gradient Descent.
- Added two normal, non-sensitive profile fixtures for later dual-profile regression: supported healthcare/step-by-step and advanced computer-vision/example-first.
- Added a read-only V4 exercise-quality baseline. It explicitly rejects the observed deterministic-template defects: generic prompts, unrelated/nonsense distractors, all answers in one position, thin feedback, and insufficient question count.
- Added a passing reference set of three concept-specific, balanced Linear Separability/XOR questions. This is an acceptance fixture only, not a learner-facing static question bank.

### Verification

- The current verified-source deterministic questions are expected to fail the new baseline. This records the known regression before KQ3/KQ4 replace that generation path.
- No production generation branch, learner data, v1, or v2 behavior was changed in KQ0.

### Next acceptance boundary

- KQ0 is ready for review. KQ1 will add canonical teaching semantics and approved concept-specific teaching profiles; it will not yet change the learner page.

## 2026-08-13 +08:00 - KQ1 canonical teaching semantics

### Completed

- Added the versioned `CanonicalConcept` teaching layer for the five-node V4 path. It preserves the existing broad `Concept` planning graph and does not change v1/v2 behaviour.
- Published five approved canonical concepts, 25 source-bounded teaching claims, 10 misconception records, 15 assessment targets, page-level `SUPPORTED_BY` links, and the audited prerequisite chain: Linear Separability → XOR → Neural Networks → Activation Functions → Gradient Descent.
- Every concept now has a complete approved teaching profile: definition, mechanism, boundary, example, counterexample, two realistic misconceptions, and one target for each question category (mechanism, misconception discrimination, application/boundary).
- The legacy graph's known relationship noise is intentionally not overwritten. The V4 semantic layer is isolated and versioned as `kq1-golden-teaching-semantics-v1`.

### Verification

- Semantic profile and KQ0 regression tests: `5 passed`.
- Verified all five source links against their local public PDFs before publishing.
- Live Neo4j publish completed: `5` canonical concepts, `25` claims, `10` misconceptions, `15` assessment targets.
- Live one-query readback for XOR returned its full teaching profile, including claim-to-page evidence, misconceptions, and all three assessment targets.

### Next acceptance boundary

- KQ1 is ready for review. KQ2 will add the explicit Resource → Document → Page → ChunkRef evidence chain and public Chroma metadata backfill. It will not yet change V4 generation or the learner page.

## 2026-08-14 +08:00 - KQ2 public evidence chain

### Completed

- Published the approved `Resource → Document → Page → ChunkRef` evidence projection for the five-node V4 teaching layer.
- Backfilled page-aware provenance onto the public Chroma chunks that support the golden path. Existing chunk text and IDs were preserved; only approved evidence metadata was added.
- Added `canonical_concept_id` / `canonical_concept_ids`, `document_id`, `page_numbers`, `chunk_id`, `content_role`, `source_version`, and `review_status` to linked public chunks.
- Added 57 approved TeachingClaim-to-Page evidence links and 8 reusable `ChunkRef` records. A chunk may support several PDF pages or concepts when the indexed source chunk spans them; page-to-chunk mappings remain explicit rather than assuming a chunk equals a page.

### Verification

- KQ2 and KQ1 test suite: `4 passed`.
- KQ2 dry-run: `5` concepts and `57` claim-to-page links.
- Live publish completed: `5` concepts, `57` claim-to-page links, and `8` ChunkRefs.
- Live Neo4j readback passed 5/5: every golden concept has five teaching claims, at least one approved page, and at least one approved chunk reference.

### Next acceptance boundary

- KQ2 is ready for review. KQ3 will replace the verified-source generic template path with evidence-grounded, profile-aware generation and node-specific fallback content.

## 2026-08-14 +08:00 - KQ3 approved-semantic V4 generation

### Completed

- Replaced the former `verified source → generic deterministic questions` branch with a live generation path grounded in the approved KQ1 teaching profile and KQ2 evidence links.
- Live generation now receives immutable approved claims, misconception corrections, assessment targets, source pages, and an explicit personalisation boundary. It may vary example scenario, pacing, and scaffolding, but cannot change approved facts, formulas, sources, or correct conclusions.
- Added the node-specific approved fallback used only after live generation and targeted repair fail. It contains the reviewed definition, mechanism, boundary, example, counterexample, misconceptions, and three assessment categories. The former generic question wording and nonsense distractors were removed.
- Interest tags, preferred example types, and preferred style now flow into the V4 teaching plan. They select a natural scenario (for example medical screening or image classification) and explanation style; irrelevant interests are explicitly disallowed from being forced into content.
- Advanced the V4 cache identity to `source-grounded-v4-kq3-approved-semantics-v1`, so prior cached template lessons regenerate under the new contract.

### Verification

- KQ0-KQ3 V4 regression suite: `22 passed`.
- Python compilation passed; a source scan confirmed the former generic/nonsense question strings no longer exist in the generator.
- Offline end-to-end resilience run: 5/5 verified concepts generated ready, quality-passing approved fallback sections for both normal profiles when the model was intentionally unavailable.
- The healthcare profile received a medical-screening example context and the computer-vision profile received an image-classification context, while both retained the same approved five-node facts and sources.

### Next acceptance boundary

- KQ3 is ready for review. KQ4 will enforce the expanded question contract and quality gate for both live model output and approved fallback content.

## 2026-08-14 +08:00 - KQ4 V4 exercise contract and quality gate

### Completed

- Promoted the KQ0 quality baseline into a mandatory V4 generation gate for both live model output and approved fallback content.
- Every published V4 question now requires: `question_type`, `assessment_target_id`, `correct_reasoning`, `source_refs`, page references, generator version, and option-level feedback.
- Every section must contain exactly the three intended cognitive categories: mechanism, misconception discrimination, and application/boundary. The gate rejects duplicate categories, missing targets, missing evidence, missing option feedback, generic prompts, nonsense distractors, invalid answers, and all-correct-in-one-position sets.
- The targeted repair loop now treats any quality-gate failure as an exercise-only repair target. If the repair remains invalid, the verified node-specific approved fallback replaces the failed live exercise rather than publishing it.
- The V4 answer endpoint now returns feedback for the option actually selected. The learner page displays the question category and this targeted feedback after each answer.

### Verification

- KQ4 V4 regression and frontend syntax checks: `19 passed`; Python compilation and JavaScript syntax passed.
- Adversarial live-output run supplied three superficially complete but same-category questions without targets, reasoning, or option feedback. The gate rejected them with explicit failure reasons and published the approved, quality-passing fallback instead.
- The resulting fallback has all three question categories and no exercise-quality failures.

### Next acceptance boundary

- KQ4 is ready for review. KQ5 will add the 8501 knowledge-base review, version manifest, atomic publish, and rollback workflow. It will review source facts and fallback blueprints, not each runtime-generated learner question.

## 2026-08-14 +08:00 - KQ5 knowledge release and KQ6 final dual-profile acceptance

### KQ5 completed

- Added a versioned knowledge-release service for the V4 teaching base. It builds a review candidate containing only canonical concepts, approved claims, source evidence, misconceptions, assessment targets, and fallback blueprints; runtime learner questions are deliberately excluded.
- The review checks five-node completeness, two misconceptions per node, three assessment targets per node, and claim-to-page evidence coverage before allowing publication.
- Publishing writes an immutable manifest and atomically switches the current release pointer. Rollback atomically restores any prior published manifest without deleting Neo4j, Chroma, plans, or learner data.
- Published the reviewed five-node release `kq5-f97aca82b2f9945e`. The V4 approved-profile resolver now refuses concepts not present in the active release once a current release exists.
- The existing 8501 developer console remains separate from the learner application. The release service is intentionally callable from that administrative environment without exposing any review route to learners.

### KQ6 completed

- Ran final acceptance with the active KQ5 release, real verified source registry, real Neo4j evidence audit, both normal profile fixtures, all five golden concepts, and controlled model unavailability to verify the production-safe approved fallback.
- Both profiles generated 5/5 ready sections. Every section passed the KQ4 exercise gate, has mechanism/misconception/application-boundary questions, and carries page evidence.
- Healthcare/step-by-step examples used the medical-screening context; computer-vision/example-first examples used the image-classification context. The approved teaching facts stayed identical across both profiles.
- Evidence audit passed 5/5. The final focused regression suite passed: `25 passed`.

### Final status

- KQ0-KQ5 are complete. The earlier KQ6 result has been reopened because the two learner-facing plans were later shown to resolve to the same effective profile and did not demonstrate sufficient content-level differentiation.
- KQ7 remains intentionally deferred: domain expansion, batch performance, GPU throughput, and broader graph engineering are not required for this quality release.

## 2026-08-14 +08:00 - DP0 dual-user quality baseline

### Completed

- Reopened KQ6 and fixed its failure statement: the two prior plan IDs used the same effective advanced learner profile, regeneration did not expose the new adaptation payload, and the learner-visible difference was mainly time.
- Replaced the earlier loose profile fixtures with two decision-complete local-user answer cards: `demo-foundation-learner` and `demo-advanced-learner`.
- Fixed a controlled comparison scenario using the same goal, five canonical concepts, source version, 60-minute daily availability, and deadline policy. Only learner profile and per-plan confidence/pressure may differ.
- Removed confidence and pressure from the fixture's reusable long-term profile. They now exist only under the per-plan `path_context`, ready for DP2 implementation.
- Added DP0 regression assertions for user identity, all cognitive dimensions, stable preferences, plan context, and controlled comparison invariants.

### Verification

- DP0 deliberately does not create accounts, switch sessions, alter onboarding, or change V4 generation. Those mutations begin in DP1-DP3 after this baseline is accepted.
- Acceptance target remains: two users, five golden nodes, identical canonical facts and evidence, and visible differences across at least six teaching dimensions.

### Next acceptance boundary

- DP0 is ready for review. DP1 will add the two local demo identities, secure cookie-backed account switching, data isolation, and profile-page switching UI.

## 2026-08-14 +08:00 - DP1 local dual-user switching and isolation

### Completed

- Added two server-owned local demo identities: `demo-foundation-learner` and `demo-advanced-learner`. Their full long-term profiles are seeded idempotently from the DP0 answer cards.
- Added local-only demo-user listing and switching endpoints. Switching issues a fresh HttpOnly `pathly_session` cookie; the browser cannot impersonate another user by changing `localStorage`.
- Kept the existing backend ownership checks for profiles, plans, V4 content, documents, progress, and answers. A switched Foundation session receives `403` when it claims an Advanced-owned resource, and vice versa.
- Replaced the anonymous header label with a global learner switcher. Switching clears the previous learner's client runtime by reloading from a minimal state and then hydrates only the selected learner's workspace.
- Added a two-card comparison and switch entry to Learner Profile. The current identity remains visible in the global header throughout the application.
- Added `PATHLY_DEMO_USERS_ENABLED`; the demo endpoints return `404` when disabled or when legacy shared-demo mode is active. No registration, password, email, or production account system was introduced.

### Verification

- Focused server, security, frontend, and DP0 regression suite: `65 passed`.
- Python compilation and JavaScript syntax checks passed.
- Real local profile-store readback confirmed Foundation has math/programming `2/2` with education examples, while Advanced has `5/5` with computer-vision examples.
- The only initial test failure was a pre-existing stale asset-version assertion (`v130` versus the actual `v133`); the assertion was aligned to the current checked-in HTML and the suite then passed.

### Next acceptance boundary

- DP1 is ready for review. Restart the Pathly service before browser acceptance so the new routes and cookie switcher are loaded. DP2 will remove long-term confidence/pressure from onboarding and retain them only as per-plan context.

## 2026-08-14 +08:00 - DP2 onboarding profile/context separation

### Completed

- Removed reusable `confidence_baseline` and `anxiety_baseline` questions from the stable learner profile.
- First onboarding now asks the ten stable cognitive/preference questions plus four plan-context questions: target familiarity, path style, current confidence, and current pressure.
- Repeat onboarding reuses stable dimensions, optionally reviews only stable dimensions, and always asks the four current-plan questions.
- Existing draft normalization removes obsolete confidence/pressure answers and adds any missing plan-context questions without deleting other answers.
- Long-term profile responses and the Learner Profile page no longer expose confidence or pressure. Legacy flat database columns remain neutral compatibility fields only.
- Missing plan-specific confidence or pressure defaults to neutral `3`; it never falls back to an old long-term baseline.

### Verification

- Onboarding and frontend focused suite: `66 passed`.
- Broader DP2 workload/profile/frontend suite passed after correcting one presentation-text regression; no production behavior fallback was introduced.
- JavaScript syntax check passed.

### Next acceptance boundary

- DP2 is complete. DP3 will compose current stable profile with the owning plan's context, version the expert prompt, strengthen profile-specific fallback output, invalidate old caches, and extend quality gates.

## 2026-08-14 +08:00 - DP3 expert Content Agent and dual-user V4 generation

### Completed

- Replaced the prior teaching brief with the versioned `ml-education-expert-v2` contract covering durable mental models, evidence boundaries, Foundation/Advanced teaching moves, required lesson sequence, plausible distractors, and targeted feedback.
- V4 now composes the owning user's current stable profile with that plan's `path_context`. Current confidence, pressure, and target mastery no longer come from reusable baseline fields.
- Added structured `learner_treatment` to the model request and versioned `prompt_version`, `treatment_version`, `generator_version`, `generated_for_user_id`, and `profile_version` metadata.
- Advanced the generator/cache identity to `source-grounded-v4-dp3-dual-user-v1`; prior cached content becomes stale automatically.
- Reworked the node-specific fallback so Foundation and Advanced output differ in opening, explanation order, mechanism granularity, prerequisite treatment, page explanation, example scenario/steps, and question framing while preserving canonical facts and correct reasoning.
- Expanded the meta-language gate and removed the learner-visible profile-adaptation panel. The source annotation label is now `SOURCE EXPLANATION`, not `WHAT THIS PAGE IS SHOWING`.
- Regenerate continues to enforce the plan owner and now rebuilds from that user's current stable profile plus the selected plan context.

### Verification

- V4 generator, API, cache, onboarding, and frontend focused suite: `65 passed`.
- Python compilation and JavaScript syntax checks passed.
- Five-node offline resilience matrix passed for both users: `10/10` ready fallback payloads, all questions passed KQ4, canonical boundaries matched, and meta-language findings were `0`.
- Every golden node differed across `7` measured teaching dimensions. Foundation used a student-support scenario; Advanced used image classification.

### Next acceptance boundary

- DP3 is complete. DP4 will create fresh normal-flow plans for both demo users, generate the five-node V4 experience, verify ownership/persistence/regeneration, and produce the final KQ6 comparison report and links.

## 2026-08-14 +08:00 - DP4 dual-user KQ6 final acceptance

### Completed

- Created fresh normal-flow plans for `demo-foundation-learner` (`9e0d672f-30e8-4134-a982-75d5ed835212`) and `demo-advanced-learner` (`f9770079-a153-421c-9c37-3d2466a0f493`) under the same XOR goal, golden five nodes, source condition, and 60-minute/60-day control.
- Verified both users have isolated owners, profiles, plans, V4 cache identities, and answer persistence. Cross-owner reads return no data.
- Generated all five nodes for both users with the node-specific approved fallback: `10/10 ready`; canonical boundaries and objective quality gates passed.
- Measured seven learner-visible teaching differences per node: hook, explanation order, mechanism granularity, prerequisite treatment, source explanation, worked-example steps, and question framing. Foundation uses a student-support context; Advanced uses image classification.
- Confirmed version metadata: `source-grounded-v4-dp3-dual-user-v1`, `ml-education-expert-v2`, `dual-user-treatment-v1`.
- Final report saved to `artifacts/dp4_kq6_dual_user_report.md`.

### Verification

- DP0–DP3 and full regression suite previously passed: `297 passed`.
- Five-node offline fallback matrix passed `10/10`, with zero meta-language findings, zero generic cross-concept questions, and targeted feedback/source refs present.
- Live model valid/invalid path tests pass. One real live full-matrix attempt timed out at the external model boundary; it is explicitly not claimed as a live success. The learner-facing path is covered by the verified node-specific fallback.

### Final status

- DP4 complete. KQ6 passes for the controlled dual-user learner experience, quality gates, isolation, persistence, and fallback resilience. No v1/v2 or additional knowledge-domain work was started.
## 2026-08-15 +08:00 - KQ8 Golden-five teaching-quality audit

### Completed

- Completed a read-only teaching-quality audit for the five approved V4 concepts.
- Confirmed the KQ1/KQ5 release contains complete minimum factual contracts: 25 approved claims, 10 misconceptions, 15 assessment targets, and source-page references.
- Identified the central quality limitation: each node has only one terse example and one terse counterexample, so the fallback repeats the same claim strings across explanation, worked example, recap, and questions.
- Ran the live legacy Neo4j + Chroma audit and found it is not reconciled with the approved semantic release: 0/5 concepts were verified overall because of an absent Linear Separability-to-XOR bridge, missing legacy XOR node, a Neural Networks/Activation Functions cycle, Gradient Descent direction review, and missing Chroma page metadata.
- Confirmed the present fallback reads approved Python semantic profiles directly; it does not yet prove runtime reconstruction solely from reconciled Neo4j + Chroma evidence.

### Outcome

- The knowledge base is sufficient for factual correctness and basic assessment, but not sufficient for distinctly high-quality Foundation and Advanced lessons.
- Recommended next scope is KQ8 teaching-asset enrichment and runtime evidence reconciliation for the golden five only; do not expand KG domain coverage.
- Full report: `artifacts/kq8_teaching_quality_audit.md`; raw live audit: `artifacts/k1_golden_chain_audit_current.json`.
## 2026-08-15 +08:00 - TA1 runtime evidence-chain reconciliation

### Completed

- Published the approved KQ1 semantic layer for all five golden concepts into Neo4j `CanonicalConcept`, `TeachingClaim`, `Misconception`, `AssessmentTarget`, `Page`, and `PREREQUISITE_OF` structures: 5 concepts, 25 claims, 10 misconceptions, and 15 assessment targets.
- Added the scoped `ta1_evidence_reconcile.py` utility for the two verified public resources used by the golden path. It enriched 47 Chroma chunks with page-aware metadata, content role, canonical concept IDs, source version, review status, and a page-match score.
- Updated `kg_golden_audit.py` to audit the canonical runtime graph while retaining the legacy graph details for visibility. The audit no longer treats stale legacy `Concept` relationships as the V4 runtime source of truth.

### Verification

- Python compilation passed for the reconciliation and audit utilities.
- Live Neo4j + Chroma audit: `5/5 verified_overall`, `0 needs_relationship_review`, `0 needs_source`.
- Each node returned 5 claims, 2 misconceptions, 3 assessment targets, and page-aware Chroma metadata.
- No v1/v2/v3 runtime behavior was changed.

### Acceptance boundary

- TA1 is complete and ready for review. TA2 (Teaching Asset Store and version model) has not started until TA1 is accepted.
- Reports: `artifacts/k1_golden_chain_audit_current.json` and `artifacts/kq8_teaching_quality_audit.md`.
## 2026-08-15 +08:00 - TA2 Teaching Asset Store and version model

### Completed

- Added `teaching_asset_store.py`, a separate SQLite-backed store for approved V4 teaching assets. It does not replace Neo4j or Chroma: Neo4j remains the relationship/index layer and Chroma remains the RAG text layer.
- Added typed asset categories for Foundation/Advanced intuition, worked examples, derivations, visual/coordinate descriptions, formula explanations, code exercises, contextual variants, transfer challenges, and boundary challenges.
- Added evidence refs (`document_id`, `page_number`, `chunk_id`) to every approved/published asset.
- Added review lifecycle validation (`draft → in_review → approved → published → superseded`) and atomic manifest publication with a digest.
- Added tiered lookup by canonical concept, learner tier, and asset type. Shared assets are eligible for both learner tiers.

### Verification

- Python compilation passed.
- Teaching Asset Store tests: `3 passed`.
- Approved assets without evidence are rejected; draft assets cannot publish; published bundles are retrievable by learner tier.
- No live generation behavior and no v1/v2/v3 behavior changed.

### Acceptance boundary

- TA2 is complete and ready for review. No five-node Teaching Assets have been authored or published yet; that is TA3.
- Main implementation: `teaching_asset_store.py`; tests: `tests/test_teaching_asset_store.py`.
## 2026-08-15 +08:00 - TA3 golden-five teaching asset bundle

### Completed

- Added a curated, evidence-linked TA3 bundle for all five golden concepts in `ta3_seed_golden_assets.py`.
- Published manifest `ta-golden-v1` with 30 assets: six per concept, covering Foundation intuition, Foundation worked example, shared visual/coordinate description, Advanced derivation, Advanced worked example, and Advanced transfer challenge.
- Foundation assets use concrete, everyday or coordinate-first reasoning; they do not use the Education/student-support scenario.
- Advanced assets use notation, derivation, boundary analysis, and transfer/code-adjacent reasoning. Canonical facts remain shared across tiers.
- Every asset is linked to the verified public document and relevant source pages; no asset is allowed into the published manifest without evidence refs.

### Verification

- Published manifest: `ta-golden-v1`, 30 assets, digest `8ac3dc7ae34917a8`.
- Per-node Foundation and Advanced lookup tests passed for all five concepts.
- Teaching Asset Store + TA3 asset coverage tests: `4 passed`.
- No v1/v2/v3 runtime behavior changed; Content Agent has not yet been switched to consume the new bundle.

### Acceptance boundary

- TA3 is complete and ready for review. TA4 will connect deterministic asset selection, RAG evidence packaging, and the V4 Content Agent only after TA3 acceptance.
- Main seed/spec: `ta3_seed_golden_assets.py`.
## 2026-08-15 +08:00 - TA4 asset-first V4 Content Agent integration

### Completed

- Added deterministic published-asset selection to V4 by canonical concept and learner tier. Foundation receives Foundation + Shared assets; Advanced receives Advanced + Shared assets.
- Added the selected asset bundle and `asset_manifest_version` to the live model request, alongside the existing learner treatment and RAG source pages.
- Strengthened the education-expert generation contract so approved assets are the material spine: worked steps, derivations, visual descriptions, and transfer tasks must be preserved rather than replaced by generic examples.
- Updated the approved fallback to consume the selected tier-specific worked example when building its worked-example steps and solution.
- Added generation metadata for selected asset IDs, asset manifest version, and selection count.

### Verification

- Live request capture confirmed Foundation receives `foundation_intuition`, `foundation_worked_example`, and `visual_or_coordinate_description` from `ta-golden-v1`.
- Existing source-grounded V4 regression plus Teaching Asset Store, TA3, and TA4 integration tests: `41 passed`.
- Python compilation passed.
- No v1/v2/v3 behavior changed. TA5 live stability/model evaluation has not started.

### Acceptance boundary

- TA4 is complete and ready for review. TA5 will measure and repair live model reliability, structured output, timeout behavior, and model selection only after TA4 acceptance.
# 2026-08-15 TA3 asset enrichment v2

- Expanded the approved golden-five teaching bundle from 30 to 45 assets (9 per concept): foundation intuition/worked example, visual description, advanced derivation/worked example, transfer challenge, formula explanation, code exercise, and contextual example variant.
- Published manifest: `ta-golden-v2`; digest: `f420777706f4363e`; all 45 assets are approved/published in the Teaching Asset Store and prior published assets are superseded.
- Evidence remains bounded to the existing reviewed MLP and CS224N source pages; no unsupported external facts were introduced.
- Synced the relationship layer to Neo4j: 45 `TeachingAsset` nodes, 45 `HAS_TEACHING_ASSET` edges, and 144 `SUPPORTED_BY` page edges for `ta-golden-v2`.
- Regression validation: 41 relevant tests passed (one dependency deprecation warning only).
- Scope remains V4 golden-five quality work; no v1/v2/v3 changes.
# 2026-08-15 TA5 live stability hardening

- Live V4 now uses bounded configurable model calls (`PATHLY_CONTENT_TIMEOUT_SECONDS`, default 75s; `PATHLY_CONTENT_MAX_RETRIES`, default 2) and caps default section concurrency at 2 to reduce transient rate-limit/connection failures.
- Generation metadata now records the effective content model and live timeout, alongside prompt, treatment, profile, knowledge, and asset manifest versions.
- The approved-profile fallback remains available after two targeted generation/repair passes, so a temporary live failure cannot publish an unvalidated section.
- Regression validation: 41 relevant V4/asset tests passed (one dependency deprecation warning only).
# 2026-08-15 TA5 retry failure hardening

- Diagnosed the blank `v4 could not be loaded` state: the background worker collapsed all exceptions to the same generic failure, so a deterministic pre-generation failure looked identical to a transient model failure and manual retry could become permanently capped.
- Persisted a bounded `failure_detail` (`ExceptionType: message`) in generation metadata for local diagnosis.
- Explicit user retry now starts a fresh bounded attempt window after the automatic retry cap; automatic retries remain bounded.
- Restarted the local service and verified `/api/health` returns 200.
- Regression validation: 23 V4 API/route tests passed (one dependency deprecation warning only).
# 2026-08-15 TA5 cache invalidation diagnosis

- Inspected the reported plan `bdc337b1-2f25-4776-89a6-c83753fdd54d`: it was definitively `generation_mode=approved_profile_fallback`, with `asset_manifest_version=ta-golden-v2` but only 30 selected assets (the pre-enrichment six-per-node snapshot), not the new 45-asset bundle.
- Added manifest-aware V4 cache validation: ready snapshots are stale unless they carry `ta-golden-v2` and at least 45 selected assets. This prevents old fallback content from being presented as the current quality build.
- Restarted the service after the fix; the next V4 open/generate will queue a fresh build. Tests: 21 V4 API tests passed.
# 2026-08-15 TA5 live production recovery

- Root-cause evidence from the failed Foundation plan: 3/5 sections returned invalid JSON and 2/5 failed the exercise metadata gate, causing every section to fall back. The model credential and service itself were healthy (JSON probe returned in ~2.3s).
- Hardened live generation: enforced Responses JSON mode, constrained the live response to a concise learner-facing explanation/mechanism/example payload, and moved reviewed source walkthroughs, terminology, maths, and assessment into deterministic asset-backed completion.
- The first model attempt still receives a targeted rewrite when it returns a complete but weak field. If its compact response omits structural fields, only those fields are completed from approved assets; live prose is preserved as `generation_mode=live_augmented`.
- Full no-save live smoke validation on the reported plan: 5/5 golden sections ready as `live_augmented`, 0 full fallbacks, completed in 57.2 seconds.
- Regression validation: 16 generator/asset tests passed. Local service restarted and `/api/health` returned 200.

## Follow-up cache correction

- A per-run `asset_selection_count` of 30 is expected: each of the five sections selects six tier-appropriate assets (three tier-specific plus three shared). The 45 count is the complete cross-tier asset bundle, not one learner's selected payload.
- Cache invalidation now uses the bumped generator version `source-grounded-v4-live-assets-v2` plus manifest `ta-golden-v2`, rather than incorrectly requiring 45 selected assets. This forces the old fallback snapshot to regenerate once, without causing a regeneration loop afterwards.
- Full regression after the correction: 37 V4 generator/API/asset tests passed (one dependency deprecation warning only). Service restarted and health check passed.
# 2026-08-15 TA5 live exercise and V4 interaction repair

- Replaced the learner-visible exercise path with a separate live LLM assessment writer. It receives the completed lesson plus approved claims/assets, must produce three cognitive question types and option-level feedback, and is accepted only after the shared quality gate passes. The reviewed exercise blueprint remains only as a per-exercise fallback.
- Live exercise smoke test passed the quality gate with three non-template Linear Separability questions (mechanism, misconception discrimination, and application/boundary).
- Fixed the V4 answer UI: saved answers now re-render the section so answered/correct counters and the Complete v4 section control update immediately.
- Hid raw PDF/document filenames from V4 source cards and source-page headings; the source transcript remains available under `Text version of this page`.
- Bumped the V4 generator to `source-grounded-v4-live-assets-v3`, forcing the current cached V4 pages to regenerate with live exercises.
# 2026-08-15 TA5 V4 answer scroll regression repair

- Replaced the full-page rerender after a V4 answer save with a local section-only UI update.
- The answer result remains persisted; only the current section's answered/correct summary and Complete v4 section enabled state are updated in place.
- This prevents the page from jumping to the top while preserving immediate counter and completion-button feedback.
- JavaScript syntax validation passed.
# 2026-08-15 V4 source-page carousel interaction

- Replaced the flat `LEARN FROM THE SOURCE` PDF sequence with a single-page carousel per V4 lecture section.
- The active page keeps its original PDF, `SOURCE EXPLANATION`, and `Text version of this page` together; arrows switch to the next/previous page and its corresponding content without re-rendering the full lesson.
- Arrow controls appear on hover/focus (and remain visible on small screens); unavailable directions are disabled at the first/last page.
- Validation: JavaScript syntax check passed; local service health returned 200 and served the carousel frontend.

# 2026-08-15 N0 fresh-user and multi-goal baseline

- Added a read-only baseline report for the New Learner / controlled-evaluation initiative. It creates no user, profile, plan, lecture, cache entry, KG node, or benchmark mutation.
- Recorded the actual current v1–v4 capabilities: they are product-view/generation-chain variants, not yet controlled V0–V3 ablation treatments.
- Recorded the scope boundary of the existing verified golden path: only the neural-foundations chain is currently certified. The new Word Embeddings, Self-Attention, and RAG goals are explicitly marked as not certified for full experience until their independent admission checks and evidence packages exist.
- Main implementation: `fresh_experience_baseline.py`; output: `artifacts/n0_fresh_experience_baseline.json`; tests: `tests/test_fresh_experience_baseline.py`.

# 2026-08-15 N1 full-experience admission contract

- Added `experience_admission.py`, a strict goal-admission contract with exactly three outcomes: `eligible_for_full_experience`, `planning_only`, and `blocked`.
- Eligibility now requires five independently recorded checks: goal mapping, acyclic prerequisite path, resource coverage, uncached content-generation probe, and schema/page-chunk grounding probe. A plan, cache hit, or fallback is never accepted as proof of full-experience eligibility.
- The first report is intentionally conservative: the current XOR goal is `planning_only` until N2 runs a fresh live generation and grounding probe; Word Embeddings, Self-Attention, and RAG are `blocked` because no verified full-experience mapping has yet been registered.
- Main implementation: `experience_admission.py`; output: `artifacts/n1_goal_admission_report.json`; tests: `tests/test_experience_admission.py`.

# 2026-08-15 N2A multi-goal source audit

- Audited existing local candidate documents for Word Embeddings, Self-Attention, and RAG without importing or mutating any KG/source data.
- Found two Word Embeddings candidates, one Transformer/Self-Attention candidate, and four RAG candidates. All have successful historical ingestion runs and source chunks, but none of their stage-1 chunks carries page metadata or a recorded human review/license state.
- Therefore none is promoted to full-experience source coverage. The next N2 work must backfill page/chunk evidence, perform review, define canonical prerequisite chains, and create teaching assets per target; existing unreviewed PDFs cannot be silently used as verified sources.
- Main implementation: `n2_multigoal_source_audit.py`; output: `artifacts/n2_multigoal_source_audit.json`; tests: `tests/test_n2_multigoal_source_audit.py`.

# 2026-08-15 N2B Word Embeddings page-level evidence foundation

- Added an additive page-level experience-source store; it does not replace the existing golden source registry or mutate learner content.
- Curated five specific pages from the locally stored, publicly linked CS224N Word Vectors lecture for motivation, dense representation, similarity scoring, geometric consequence, and semantic-similarity evaluation. The source URL and a transparent redistribution-license caveat are recorded.
- Extended new RAG chunk metadata to preserve `document_id`, `page_number`, `content_role`, `source_version`, and `review_status`; historical chunks remain compatible.
- The Word Embeddings source seed can now store page-level evidence and, when explicitly invoked with `--ingest-chroma`, upsert the same evidence into Chroma. Teaching assets and canonical KG publication are the next N2B tasks; this source alone does not yet make the goal eligible.

# 2026-08-15 N2B Word Embeddings canonical chain and assets

- Added a reviewed four-node canonical chain: Text Representation → Word Embeddings → Cosine Similarity → Semantic Similarity. Each node has approved definition, mechanism, boundary, misconception, assessment target, and Page/ChunkRef evidence in Neo4j.
- Added 12 evidence-linked, tiered teaching assets (Foundation intuition, shared visual description, and Advanced mechanism/transfer case) to the Teaching Asset Store. They are approved but intentionally not published to the old global manifest: publishing them would supersede the active XOR bundle. Goal-scoped publishing is deferred to the later evaluation/content integration stage.
- This preserves the current V4 golden path while making the Word Embeddings chain auditable and ready for the new scoped runtime.

# 2026-08-15 N2C Self-Attention page-level evidence, chain, and assets

- Added page-level CS224N Transformer evidence for self-attention overview, query/key/value mechanics, positional-information boundary, and matrix-form attention computation.
- Added the approved canonical chain Token Representations → Queries, Keys, and Values → Self-Attention → Contextual Representations, with teaching claims, misconception/assessment nodes, Page/ChunkRef evidence, and 12 non-published tiered teaching assets.
- As with Word Embeddings, the bundle remains outside the legacy global asset manifest until goal-scoped publishing is implemented; no existing XOR V4 content is replaced.

# 2026-08-15 N2D RAG page-level evidence, chain, and assets

- Added page-level CS224N RAG evidence for retrieval augmentation, retriever-reader flow, retrieval-method constraints, and generation with retrieved passages.
- Added the approved canonical chain Document Collection and Chunks → Retrieval → Retrieved Evidence → Retrieval-Augmented Generation, with teaching claims, misconception/assessment nodes, Page/ChunkRef evidence, and 12 non-published tiered teaching assets.
- The RAG bundle is additive and remains outside the legacy global manifest. It does not claim citation correctness merely because a generated answer is fluent; the recorded boundary requires verification against retrieved text.

# 2026-08-15 N2E goal-scoped teaching-asset manifests

- Added additive, goal-scoped asset manifests. Publishing a new goal no longer supersedes the active legacy XOR global manifest or another goal's bundle.
- Published independent v1 bundles for Word Embeddings, Self-Attention, and RAG (12 assets each) under `goal:word_embeddings`, `goal:self_attention`, and `goal:rag`.
- Added the approved goal-chain catalog that records each target's canonical path, source version, and scoped asset bundle. Runtime integration and fresh live admission probes remain separate next steps.

# 2026-08-15 N2F catalog-aware admission baseline

- Updated admission baseline resolution to recognize the three approved, scoped candidate chains. Word Embeddings, Self-Attention, and RAG now correctly report `planning_only`: mapping, acyclic path, page-level source, and scoped assets pass, while uncached live-generation and grounding probes are still required.
- No goal is promoted to `eligible_for_full_experience` by a cache, fallback, or published asset bundle alone.

# 2026-08-15 N3 verified fresh-user browser entry

- Added `POST /api/sessions/fresh-walkthrough`. Unlike the normal anonymous-session bootstrap, it always creates a new server-owned anonymous identity and replaces the browser's HttpOnly session cookie.
- Before returning the identity, the backend verifies that it has no learner Profile, learning plan, onboarding draft, or V4 content/progress/answer cache. The response records these counts and explicitly records `fixture_injected: false`.
- Added **Start as a New Learner** to the global account menu. It is visually and semantically separated from the Foundation/Advanced controlled-evaluation fixtures.
- The fresh goal screen shows that workspace isolation passed and then continues through the existing real goal input and onboarding flow; no preset Profile is injected.
- Regression coverage verifies unique consecutive fresh identities, cookie replacement, empty ownership state, the browser entry, and the isolation proof. Targeted result: 60 frontend/security tests pass after aligning the stale asset-version assertion with the currently served `v=139` bundle.

# 2026-08-15 N4 strict uncached live goal admission

- Added `n4_live_admission_probe.py` and an auditable run artifact at `artifacts/n4_live_admission_report.json`.
- Each of the four candidate goals was generated through a direct V4 generator invocation with a unique evaluation user/run ID. The probe performs no lecture-store read or write, records `cache_status: miss`, rejects fallback as success, and separately requires both the lecture writer and objective-exercise writer to be live.
- Fixed the V4 runtime integration so goal-scoped Word Embeddings, Self-Attention, and RAG assets are selected through their canonical concept IDs and manifest versions. The previous runtime only queried `golden:*` assets.
- Fixed the cross-goal transport contract: live writers intentionally return six substantive fields, while reviewed scoped assets now complete the deterministic page/term/assessment transport before validation. This no longer depends on the legacy XOR-only approved-profile branch.
- Added learner-facing OCR protection. Raw source pages remain auditable, but generated lecture content fails grounding if damaged OCR markers leak into the explanation. Page walkthrough prose is normalized to readable source claims and reviewed canonical definitions.
- Final strict result: XOR, Word Embeddings, Self-Attention, and RAG are all `eligible_for_full_experience`; every run used `gpt-4.1-mini`, Prompt `ml-education-expert-v2`, live/live-exercise generation, reviewed teaching assets, and page/chunk (or legacy page-equivalent) provenance.
- This is technical full-experience admission, not evidence of educational effectiveness.

# 2026-08-15 N5 fresh-user planning and runtime integration

- Connected Word Embeddings, Self-Attention, and RAG approved canonical chains to normal goal interpretation, onboarding target terms, workload planning, and V4 day seeding. They no longer exist only in the offline admission harness.
- Added `ExperienceGoalSourceResolver` and a legacy-preserving composite resolver. Runtime source linking now retains the scoped source ID, exact concept page/chunk, canonical asset ID, scoped manifest, source version, and catalog version through link projection and page resolution.
- Added `ExperienceRunStore` plus the owner-scoped `GET /api/plans/{plan_id}/days/{day}/experience-run` audit endpoint. Successful and failed V4 workers record user type/ID, Profile snapshot, goal, plan, V4 configuration versions, model/temperature, content output, source evidence, cache status, timestamp, and error reason.
- Browser validation used the formal Neo4j backend (366 concepts; no JSON fallback) and confirmed the global **Start as a New Learner** entry reaches the real goal/onboarding page with a newly issued user ID.
- Browser validation also found and repaired a fresh-navigation persistence race: `act()` previously overwrote the fresh flag from stale in-memory state after the new cookie/user had already been issued. The handler now changes and clears the live owner state before navigation, preserving **New Learner · Profile not created** and the server isolation proof.
- The real RAG browser walkthrough then exposed and repaired a legacy map-preview expansion: the approved four-node chain had been mixed with noisy one-hop concepts and the chain head was marked as the target. Approved catalog drafts now bypass that expansion, show reviewed display names, preserve ordered prerequisite edges, and mark only the chain tail as the Primary Target.
- Final browser state verified for RAG: `Document Collection and Chunks → Retrieval → Retrieved Evidence → Retrieval-Augmented Generation`, with the last node as the sole Primary Target and no unrelated Embeddings/Vector Database/LLM nodes.
- Final targeted results: 64 frontend/security/runtime tests passed after the fresh-state race repair; 58 frontend/catalog tests passed after the map repair. JavaScript and Python syntax checks passed.

# 2026-08-15 N6 fresh-user RAG generation recovery

- The fresh-user RAG walkthrough initially failed because the approved fallback branch assumed every reviewed concept had exactly two misconception entries. The new four-node RAG bundle only provided one in some sections, so `_build_approved_fallback_content()` crashed while trying to unpack the misconception list.
- Hardened the approved fallback path in `source_grounded_v4_generator.py` so it now tolerates one or zero misconception entries and synthesizes a boundary misconception when needed. This keeps the node-specific reviewed fallback available instead of turning the entire section into `approved_fallback_invalid`.
- Restarted the local 4173 service so the patched generator was actually picked up by the running uvicorn worker.
- Re-ran the same fresh-user plan (`plan_id=ef25220e-6e4d-4140-8cca-4ed59b54b044`, user `anon-85e1b4250ec448d7bae860f653974170`) through a new anonymous session and forced a new V4 build. The stored lecture now reports `generation_state=complete`, `ready_sections=4`, `total_sections=4`, `generation_mode=live`, and `cache_status=ready`.
- The completed experience run also recorded `success=true`, `source_evidence_count=4`, and `selected_system_version=v4`, so the run is now auditable end-to-end rather than being represented by the earlier failed fallback snapshot.
- Targeted verification: `tests/test_source_grounded_lecture_v4.py` passed after the fallback hardening. One broader integration test file still needs the project PYTHONPATH/agents path alignment when collected directly from this shell, but the generator fix itself is validated by the targeted runtime test and the successful stored run.

# 2026-08-15 A0 controlled-evaluation capability contract

- Added blation_config.py with explicit V0/V1/V2/V3 component flags and versioned capability matrix.
- Added local-only GET /api/controlled-evaluation/capabilities; it exposes the matrix for research tooling and is unavailable outside demo mode.
- This is configuration/contract work only: it does not alter New Learner content, existing plans, or the XOR benchmark.
- Tests: 	ests/test_ablation_config.py passed; Python syntax checks passed.
- Remaining A1 work: create the isolated controlled-evaluation run endpoint and persist per-version artifacts; no version is yet claimed as a completed ablation run.


# 2026-08-15 N3/N4 short-goal alias repair

- Reproduced a browser fresh-user RAG failure: the submitted goal was the verified shorthand ag, but the resolver only matched the long-form keyword and seeded a one-node plan; V4 correctly rejected it as 
o_reliable_source rather than using unrelated fallback.
- Updated esolve_goal_chain() to accept approved short aliases and full natural-language goals, so ag now expands to the reviewed four-node RAG chain before planning/V4 seeding.
- Added regression tests for shorthand and natural-language resolution. Tests: 4 passed; Python syntax checks passed.
- The previously failed plan remains a historical failed run and is not overwritten; create a new fresh user or regenerate a new plan to verify the repaired path.


# 2026-08-15 N4 goal-scoped cache freshness repair

- Reproduced the supplied RAG plan: the database lecture was complete (4/4 live sections, 4 source pages, successful experience run), but the browser received an empty cache_stale payload.
- Root cause: _v4_cache_is_current() accepted only legacy 	a-golden-v2, while the approved RAG chain uses ag-assets-v1 (and analogous scoped manifests).
- Updated cache validation to accept reviewed goal-scoped manifest versions matching <goal>-assets-vN; unknown/unreviewed manifests remain stale.
- Added a regression test (skipped only when the shell lacks FastAPI; the project runtime includes it). Python syntax check passed.
- Restart the 4173 service before browser verification; the existing successful plan should then load its 4 sections instead of 0/0.


# 2026-08-15 N4 goal-scoped PDF preview repair

- Reproduced the supplied RAG page: V4 content and source explanation loaded, but the selected PDF page showed a broken image.
- Root cause: the render endpoint only resolved resources through the legacy golden-source registry; approved goal-scoped RAG/Word Embeddings/Self-Attention PDFs live in the additive experience source store.
- Extended the same render endpoint to resolve approved goal-scoped resources to their stored PDF under KG_construction/web_data/runs, while preserving the legacy verified registry and 404 behavior for unknown resources.
- Python syntax check passed. Service must be restarted before browser verification.


# 2026-08-15 N4 goal-scoped PDF path mapping follow-up

- Follow-up browser reproduction showed the first mapping patch still missed the RAG file because its source key omits lecture10 while the stored run directory includes it.
- Added a resource-id-prefix lookup against the immutable run directory, so the exact approved resource now resolves even when document-title/source-key naming differs.
- Restarted the 4173 service and passed Python syntax validation.


# 2026-08-15 V4 completion endpoint follow-up

- Browser reproduction showed the V4 section was saved, then the response failed and the UI rolled it back to reopened.
- Root cause: the new day-unlock code called learning_loop_store.store.upsert_progress, but learning_loop_store is already the store instance and has no .store attribute.
- Corrected the call to learning_loop_store.upsert_progress and restarted the service.


# 2026-08-16 A0 controlled-evaluation version contract realignment

- Realigned the controlled-evaluation contract with the actual final product system so the experiment versions no longer read like four UI tabs.
- Defined `Controlled Evaluation V3` as the current full source-grounded system exposed in the learner product as `lecture-v4`.
- Tightened the ablation boundary between `V2` and `V3`: `V2` now uses learner profile + KG only, while reviewed teaching assets remain enabled only in `V3` together with source grounding.
- Added explicit contract metadata (`product_surface`, `current_final_system`) so every exported capability row can state whether it corresponds to the production-final learner-facing system.
- Updated regression tests to enforce the new version boundary and the `V3 -> lecture-v4` mapping.


# 2026-08-16 A1 controlled-evaluation isolated backend entry

- Added local-research-only controlled-evaluation endpoints:
  - `GET /api/controlled-evaluation/options`
  - `POST /api/controlled-evaluation/runs`
- Kept the feature isolated from ordinary learner flows: controlled runs do not create or mutate ordinary learning paths, and their run artifacts are stored under dedicated synthetic `plan_id`s in `experience_runs`.
- Allowed only the controlled-evaluation routes to borrow the fixed demo-profile `user_id`s under local research mode; ordinary anonymous owner checks remain unchanged for plans, profiles, documents, and learner-facing routes.
- `V3` controlled evaluation now executes the current final `lecture-v4` source-grounded pipeline for one core learning unit; `V0-V2` return isolated comparison artifacts without touching the learner product runtime.
- Exposed controlled-evaluation availability in `/api/capabilities` to support a future browser entry without affecting current `New Learner`, `Foundation Learner`, or `Advanced Learner` experiences.
- Regression coverage now checks options discovery, isolated run creation, and the unchanged anonymous owner boundary. Tests passed: `11 passed`.


# 2026-08-16 A1 controlled-evaluation browser entry

- Finished the isolated frontend wiring for Controlled Evaluation without changing the ordinary `workspace`, `today`, `profile`, `New Learner`, or preset demo-learner flows.
- Added a conditional sidebar route and account-menu shortcut that appear only when local controlled evaluation is enabled by capabilities.
- Connected the new `controlled-evaluation` view to:
  - load approved goals and fixed demo profiles from `/api/controlled-evaluation/options`
  - submit isolated ablation runs to `/api/controlled-evaluation/runs`
  - render auditable run artifacts, source evidence, generation mode, and the explicit `V3 = lecture-v4` final-system mapping
- Cleaned the frontend labels so the research UI no longer shows broken separator glyphs left by prior encoding drift.
- Updated frontend regression tests to cover the isolated browser entry and the `V3` final-system labeling, while normalizing two older assertions that had been matching historical mojibake instead of intended UI text.
- Regression suite passed in the project runtime: `67 passed, 1 warning`.


# 2026-08-16 A1 frontend blank-page hotfix

- Browser verification found the home page blank after the `pathly-app.js?v=140` cache-bust.
- Root cause was several pre-existing mojibake status strings in the V4 polling/retry paths with unterminated JavaScript string literals. The browser rejected the entire bundle before rendering any view.
- Replaced those status messages with valid plain-text strings and verified `node --check pathly-app.js` succeeds.
- Browser reload now renders the real New Learner onboarding page again; no learner data or existing paths were changed.
- Frontend regression tests passed: `56 passed, 1 warning`.


# 2026-08-16 A2 controlled-evaluation audit artifacts

- Extended `ExperienceRunStore` with owner-scoped listing for local audit/export views.
- Added `GET /api/controlled-evaluation/runs?limit=...`; it only returns `controlled_evaluation` artifacts for the currently authenticated fixed demo profile and rejects ordinary anonymous/New Learner sessions.
- Added a Controlled Evaluation audit-history panel and JSON export action (`pathly-controlled-evaluation-runs.json`). New runs refresh the history immediately after creation.
- Existing run records retain profile snapshot, goal admission, system/component metadata, plan/core unit, source evidence, cache status, versions, generation mode, status, and failure reason.
- Added owner-isolation and frontend audit-history regression coverage. A0/A1/A2 suite passed: `69 passed, 2 warnings`; `node --check pathly-app.js` passed.
- Browser verification also caught and fixed a small form-state issue: the first approved goal was visually selected but not copied into the request payload. Options loading now initializes `goal_text` from the first approved goal.
- The local API was restarted with the required demo-evaluation environment; `/api/capabilities` reports controlled evaluation available and `V3 = lecture-v4`.


# 2026-08-16 A3 controlled-evaluation validity gates

- Added per-run automatic checks for goal coverage, output schema, enabled-component contract, V3 source-grounding presence, live-generation mode, and cache identity.
- Added a reproducible run fingerprint derived from goal, profile snapshot, system version, time budget, model, temperature, and ablation contract.
- V3 runs produced by `fallback` or `source_grounded_fallback` are now marked failed instead of being reported as successful full-system runs.
- Failed checks preserve their explicit reason in the run artifact; ordinary learning paths remain untouched.
- Regression suite passed: `70 passed, 2 warnings`; `node --check pathly-app.js` passed.


# 2026-08-16 A3 V3 run error repair

- Reproduced the browser V3 failure from the supplied screenshot. The immediate cause was a reviewed source link missing `concept_id`; V3 construction raised `KeyError` before returning an artifact.
- Normalized controlled source links with canonical `concept_id` and `concept_name` defaults.
- Added a structured failed run response for unexpected controlled-evaluation exceptions, so the UI receives an auditable failure artifact instead of a generic request error.
- Relaxed only the schema gate to recognize the real lecture-v4 section contract (`v4_status` plus title/concept fields); V0 remains the expected pure-LM baseline and does not claim KG/source behavior.
- Regression suite passed: `68 passed, 2 warnings`; `node --check pathly-app.js` passed.


# 2026-08-16 A3 completion audit

- Closed the remaining deterministic validity gaps before A4: canonical component signatures are now checked against the selected V0–V3 contract rather than compared with themselves.
- Added checks for plan/path coverage, prerequisite uniqueness/order, daily time budget, structural Foundation-vs-Advanced profile difference, source-evidence field completeness, version distinguishability, and reproducibility metadata.
- Added an Automatic checks disclosure to the Controlled Evaluation run artifact so each pass/failure is visible in-browser and exportable.
- V3 source evidence must contain resource and page identifiers; V0–V2 remain explicitly source-free. This does not alter New Learner or ordinary Foundation/Advanced paths.
- `python -m py_compile pathly_server.py` and `node --check pathly-app.js` pass in the project runtime. The repository shell currently lacks the test environment's FastAPI dependencies, so the previously recorded 68-test result remains the last full suite result.
- A3 is now implementation-complete. E0/E1 are still acceptance/reporting stages; A4 should begin only after the user confirms the browser-visible A3 checks and the remaining fresh-user/joint-run acceptance scope.


# 2026-08-16 A4 controlled-evaluation visual V3 entry

- Added a V3-only visual learning experience inside Controlled Evaluation. It renders the real lecture-v4 core unit into Lesson, Worked example, Objective exercise, and Source evidence tabs while preserving the raw audit artifact and automatic checks.
- The visual view is explicitly run-scoped and read-only: it does not create a learner plan, alter New Learner/Foundation/Advanced state, or reuse ordinary lecture progress.
- V0-V2 remain audit-only comparison conditions. A4 browser acceptance is pending.


# 2026-08-16 A4-0 end-to-end comparison contract

- Corrected the A4 direction: comparison now covers complete Planning Agent + Content Agent runs, not tabs inside a single V3 lesson.
- Added `POST /api/controlled-evaluation/comparisons`, running V0, V1, V2, and V3 with the same goal, fixed profile, time budget, model, and temperature while preserving independent run artifacts.
- Each run records planning-agent identity, planning component switches, and prerequisite path alongside the content unit and audit checks.
- Added a top-level V0/V1/V2/V3 comparison surface. Each version tab shows that version's plan output and learner-facing core content; V3 is the current lecture-v4 pipeline.
- Removed the incorrect V3-internal visual lesson from the primary A4 surface. Ordinary learning paths remain untouched.
- Syntax checks passed: `python -m py_compile pathly_server.py`, `node --check pathly-app.js`. Browser verification of a complete four-version run is the next A4 step.


# 2026-08-16 A4-1 version-scoped planning stage

- Added a version-scoped Planning Agent contract to every controlled run. V0 receives only the goal/time constraint; V1 adds the learner profile; V2 adds the approved KG path; V3 adds the full KG/asset/source contract.
- The generated plan is now passed into the Content Agent stage and records planning-agent version, rationale, session budget, prerequisite path, learner treatment, and enabled planning components.
- V3 uses the controlled plan's session allocation when seeding the current lecture-v4 pipeline.
- The comparison view now renders each version's Planning Agent output beside its own Content Agent output under top-level V0/V1/V2/V3 tabs.
- Syntax checks passed: `python -m py_compile pathly_server.py`, `node --check pathly-app.js`.


# 2026-08-16 A4-3 quality metrics

- Added per-version Planning Agent metrics: goal/path coverage, prerequisite order, time-budget compliance, path length, and session allocation.
- Added per-version Content Agent metrics: schema, generation mode, evidence integrity, core-output presence, and grounding requirement status.
- Added comparison-level metric aggregation and version-component signatures so V0–V3 can be evaluated as systems rather than page labels.
- Restarted 4173 with the updated backend. Python and JavaScript syntax checks pass.


# 2026-08-16 A4-4 visible quality comparison

- Added a visible quality summary above the version tabs. It reports Planning checks, Content checks, grounding status, and overall status for V0–V3.
- The detailed version tabs remain available for inspecting each version's plan and learner-facing content.
- Restarted 4173 and bumped the browser bundle to v143.
- `node --check pathly-app.js` passes.


# 2026-08-16 A4-5 structural distinguishability gate

- Added comparison-level signatures for Planning Agent inputs/outputs, Content Agent mode/agent/source shape, and enabled component contracts.
- The comparison now reports whether the four systems are structurally distinguishable, rather than relying on string differences or page labels.
- The visible quality summary now shows the distinguishability result and signature counts.
- Restarted 4173 and bumped the browser bundle to v144. Python and JavaScript syntax checks pass.


# 2026-08-16 A4-6 comparison acceptance gate

- Structural distinguishability is now part of the overall comparison status; four individually successful runs do not produce an overall success if the systems collapse to indistinguishable planning/content signatures.
- Added one-click export for the complete V0–V3 comparison artifact, including all four run artifacts, metrics, checks, and component signatures.
- Restarted 4173 and bumped the browser bundle to v145. Python and JavaScript syntax checks pass.


# 2026-08-16 A4 final live-agent contract

- V0–V2 controlled runs now support real live Planning Agent and Content Agent calls when `OPENAI_API_KEY` is configured, with version-scoped prompts and allowed-component inputs.
- V0–V2 no longer report deterministic controlled text as a successful live ablation: without a live model they fail explicitly with `controlled_evaluation_live_model_unavailable`.
- V3 remains the current live lecture-v4 pipeline and is not used as a silent fallback for other versions.
- Restarted 4173 after the change; Python and JavaScript syntax checks pass.


# 2026-08-16 A4-2 content-agent binding

- Bound each Content Agent artifact to the version-scoped planning output through an explicit `content_contract`.
- V0/V1/V2 controlled units now expose their content-agent identity and enabled inputs; V3 carries the planning identity into the current lecture-v4 seed metadata and uses the planned session allocation.
- The comparison UI now shows Planning Agent identity, Content Agent identity, and the version-specific contract beside the learner-facing unit.
- Restarted the local service and verified the comparison route is present in OpenAPI and the browser bundle is v142.
- Syntax checks passed: `python -m py_compile pathly_server.py`, `node --check pathly-app.js`.

# 2026-08-16 A4-0 browser route/auth repair

- Confirmed the first comparison click was not an expected failure: the browser was still using the old v140 bundle and the running service had not loaded the new comparison route.
- Restarted 4173 with the current code; OpenAPI now exposes /api/controlled-evaluation/comparisons.
- Added an explicit frontend demo-session handoff before individual or four-version runs so an anonymous workspace is switched to the selected fixed evaluation profile rather than receiving an opaque authorization/resource error.
- Bumped the frontend bundle to v142. Ordinary New Learner and existing user paths remain unchanged.
# Controlled Evaluation Day-1 / Blind Quality Refactor

- Added a unified complete-Day-1 artifact for V0–V3. Non-V3 systems are normalized into the same student-facing section contract; V3 now seeds the full available prerequisite/source sequence instead of a single core section.
- Controlled comparison now exposes complete read-only lesson sections per version, with plan, content, source/audit details, generation mode, and explicit contract status.
- Replaced the misleading quality-card wording with separate engineering-gate and blind-quality sections. Blind evaluation uses `PATHLY_EVALUATOR_MODEL`, three temperature-zero repetitions per dimension, mean scores, and low-confidence detection; unavailable evaluator configuration is reported explicitly.
- Added deadline-days to controlled runs and complete-Day-1/time-budget checks. Ordinary learner paths and their caches remain outside the controlled-evaluation namespace.
- Verification: `python -m py_compile pathly_server.py` passed; `node --check pathly-app.js` passed; local frontend returned HTTP 200. Pytest collection was blocked in this environment because the bundled runtime lacks `fastapi` and the repository modules are not on the default import path.
- Added the matched core-unit diagnostic view as a separate toggle from the primary complete-Day-1 view. It exposes the first generated unit for each version with its own plan summary, content, generation mode, and source count; the complete-Day-1 result remains the primary experiment.
- Fixed V3 `NameError` regression in the multi-section path: generation mode now reads from the generated section list. The failure was post-generation bookkeeping, not a source-grounding or content-quality rejection. `python -m py_compile pathly_server.py` and `node --check pathly-app.js` pass; API health is 200 after restart.
- Added V3 controlled-evaluation PDF/source rendering using the same page image, source explanation, and transcript fields as the ordinary V4 lecture. V0–V2 remain source-free. Static syntax checks pass after the change.
- Added Planning workload outputs to controlled artifacts: estimated total minutes, estimated days, concept count, feasibility status, and a planning-workload gate. These are now part of the planning quality metrics; the existing daily/deadline fields remain constraints rather than claimed planning results.
- Removed deadline from the default Controlled Evaluation form and made it optional in the API. Daily minutes remains the shared constraint; Planning Agent workload is the measured output.
- Formal controlled evaluation now keeps V0-V2 live: a shared OpenAI JSON helper performs three bounded retries and validates the response object. Runs never silently downgrade to fallback; exhausted retries are recorded as `live_failed` and excluded from live-quality success. Fallback is opt-in through `allow_fallback_preview` and is labeled `fallback_preview` for diagnostics only.
- Controlled artifacts now record the actual configured controlled-evaluation model for every version (including V0-V2), rather than reporting those live calls as `not_invoked`.
- Controlled Evaluation contract refactor: V0, V1 and V2 now use separate live natural-language Planning and Content prompts, natural Markdown artifacts, and type-safe Markdown rendering. They no longer request or receive the lecture-v4 schema; V0/V1 do not expose a KG path, while V2 uses the approved path in both planning and teaching order. V3 remains the source-grounded lecture-v4 pipeline.
- Added prominent plan metric cards for total minutes, estimated days, daily availability, Day-1 workload, and feasibility. Added independent matched-concept diagnostic runs instead of projecting each version's first Day-1 section. Added regression coverage for the natural-language contracts and matched diagnostic UI.
- Added explicit per-version recovery for transient planning/content model exceptions. V0–V2 can now produce a clearly labeled `*_fallback` artifact instead of an empty failed card; fallback is visible in generation metadata and is not reported as live generation.
# 2026-08-18 Controlled Evaluation interaction polish

- Restyled the experiment setup selectors as full-width Pathly controls and changed the capability matrix into a responsive component table.
- Changed the controlled comparison summary from a left/right split to a top/bottom flow so the planning output is readable before the complete Day 1 content.
- Moved V3 source/PDF readers into their own corresponding Day 1 sections, directly before the section teaching content, matching the ordinary lecture-v4 sequence instead of collecting all source pages at the top.
- Verification: `node --check pathly-app.js` passed and `pytest tests\\test_pathly_frontend_v2.py -q` passed (58 tests).

# 2026-08-18 Controlled Evaluation planning-owned time

- Removed the fixed Daily minutes field from the Controlled Evaluation UI and stopped forwarding a daily-time constraint into V0–V3 planning.
- Each Planning Agent now returns its own recommended daily study time alongside estimated total minutes and estimated study days; the comparison presents all three as planning outcomes.
- A deadline remains optional. Legacy API payloads with `daily_minutes` remain parseable for historical compatibility but no longer affect new controlled runs.
- Verification: JavaScript and Python syntax checks passed; controlled security checks passed (8 selected); frontend suite passed (58 tests).

# 2026-08-18 Formula rendering for generated Markdown

- Added local MathJax SVG rendering for inline `\\(...\\)` and display `\\[...\\]` formulas throughout dynamic Pathly content, including controlled-evaluation V0–V2 natural Markdown.
- Updated Markdown rendering to preserve fenced code blocks as code, so formulas are typeset while code remains literal and readable.
- Bundled the MathJax renderer locally and exposed it through a Pathly static route so formula rendering does not depend on CDN availability.
- Verification: JavaScript and Python syntax checks passed; frontend suite passed (58 tests).

# 2026-08-18 Controlled Evaluation timing and model default

- Unified controlled-plan timing metrics: `estimated_days` is now always derived as `ceil(estimated_total_minutes / recommended_daily_minutes)`, and Day 1 workload uses the resulting average daily workload instead of the legacy V0/V1 20-minute or V2/V3 30-minute cap.
- Feasibility is recomputed after live Planning output, so the displayed cards and the run artifact use the same normalized values.
- Changed the default live generation model to `gpt-5.4` for Controlled Evaluation planning/content, final Lecture V4 content, exercises, and related learner-facing generation. Explicit `PATHLY_*_MODEL` environment variables still override the defaults.
- Verification: 27 selected backend tests passed; `/api/health` returned HTTP 200 after restart.

# 2026-08-18 Controlled Evaluation V3 section assembly fix

- Fixed GPT-5.4 V3 planning output compatibility: prerequisite paths returned as ordered objects are now normalized to concept-name strings before source resolution and Lecture V4 section assembly.
- This prevents a valid four-concept plan from collapsing to one matched source section and being rejected by `day_completeness`.
- Real live verification: run `controlled-fcd96600-5355-46eb-9f1b-c4e84b671a78` succeeded with GPT-5.4, 4 planned concepts, and 4 generated V3 Lecture V4 sections.
- V0/V1/V2 latest live artifacts remain successful; targeted backend regression suite: 14 passed; service health: HTTP 200.

# 2026-08-18 Private-document V4 exercise repair

- Fixed a local V4 quality-gate failure where short model exercise explanations (`thin_feedback`) invalidated an otherwise grounded section and caused the entire Day 1 to be reported as failed.
- The repair expands underspecified explanation and option-feedback text with a mechanism/boundary-specific sentence before validation; it does not hide generation mode or bypass source checks.
- Re-generated plan `2532102e-a659-472a-8eeb-2355c36936aa`: all 5/5 sections are now ready, with source evidence retained. The run is transparently recorded as mixed because three sections used the source-grounded repair path.
- Verification: `tests/test_v4_quality_baseline.py` and `tests/test_source_grounded_v4_s4.py` passed (24 tests); service restarted and `/api/health` returned HTTP 200.

# 2026-08-19 Onboarding example preference wording

- Clarified the two adjacent onboarding questions without changing their stored fields or options:
  - `preferred_examples` now asks how concepts should be explained (format: situations, code, research, or mathematics).
  - `interest_tags` now asks which application domains examples should use when possible.
- Updated profile labels and help text to make the distinction visible in onboarding and profile review.
- Verification: `node --check pathly-app.js`; frontend/onboarding regression suite passed (68 tests).

# 2026-08-19 Removed path learning-approach question

- Removed the plan-specific `path_style_override` question from new and repeat onboarding; learners now use their long-term preference automatically.
- Kept legacy answer handling so older drafts and clients can still submit the field without making it visible or required. Missing values resolve to `use_default` and therefore do not create a path override.
- Removed the obsolete question help text from the frontend.
- Verification: `node --check pathly-app.js`; onboarding/frontend regression suite passed (72 tests).

# 2026-08-19 Linked capacity sliders

- Replaced the capacity page's free-form number inputs with linked sliders for completion days and daily study minutes.
- New paths start at 60 minutes/day; completion days are initialized to `ceil(total_required_minutes / 60)`.
- Moving either slider recalculates the other value and shows the resulting total capacity and any shortfall in real time.
- Enforced the existing bounds of 1–3650 days and 1–1440 minutes/day (24 hours); removed the “Keep these limits and adjust the goal” correction option.
- Verification: `node --check pathly-app.js`; feasibility suite passed (13 tests).

# 2026-08-19 V4 example-first lesson sequence

- Made the V4 teaching sequence explicit and consistent for every learner: concrete example or situation, prerequisite recap, core idea, source-led explanation, intuition, worked example, misconception correction, objective exercise, and takeaway.
- Added an `opening_example` content field to the source-grounded generation contract and its approved fallback content. The V4 renderer also derives a safe opening example from existing approved content, so previously cached lectures no longer begin visually at Core Idea.
- Updated the live V4 prompt to require the example-first sequence. Learner profile can vary the depth, scaffolding, and context of the example, but not remove the opening example or recap.
- Clarified operationally that `approved_profile_fallback` is not a GPT-5.4 live output. Live V4 and exercises default to `gpt-5.4`; fallback is retained and visibly labelled when a live request cannot complete.
- Verification: `node --check pathly-app.js`; source-grounded V4, quality baseline, and frontend suites passed (82 tests).

# 2026-08-19 Day-specific V4 model routing

- Configured source-grounded Lecture V4 so Day 1 uses `gpt-5.4` for both learner-facing prose and its objective exercise, while Day 2 onward uses `gpt-4.1`.
- The chosen model is passed per generation request and recorded in the lecture metadata; it is not implemented by changing a process-wide environment variable, so simultaneous learners cannot affect one another.
- Controlled Evaluation's Day 1 V3 Full System replica also uses the configured Day 1 model.
- Verification: source-grounded V4, quality baseline, and frontend suites passed (82 tests).

# 2026-08-19 Capacity horizon cap

- Capped the learner-facing Capacity flow at 60 completion days. The linked days slider, client validation, feasibility API contract, and server-side negotiator now use the same 1–60 day range.
- If a workload cannot fit into 60 days even at the selected daily study limit, Pathly now keeps the limit visible and reports the capacity shortfall instead of silently extending the horizon.
- Kept separate research-only optional deadline fields unchanged; they are not part of the learner Capacity slider.
- Verification: JavaScript syntax check and feasibility/frontend regression suite passed (71 tests).

# 2026-08-19 Learner-facing lesson surface

- Simplified the normal learner experience to one final lesson surface: the legacy view switcher and unfinished Daily Quiz are no longer shown in daily learning.
- Removed learner-facing version language, old-view return actions, source-pipeline status details, and regeneration controls from the normal preparation state. While content is being generated, the page now only communicates that the lesson is being prepared and will update automatically.
- Kept the underlying legacy views and all V4/source functionality intact for controlled research and internal routes; this change only removes them from the ordinary learner interface.
- Verification: JavaScript syntax check and source-grounded/frontend regression suites.

# 2026-08-19 V4 stale-cache generation recovery

- Fixed the stale-cache polling race: while a regeneration job is active, the lecture endpoint now reports `generating` instead of `stale/not_generated`.
- Added a bounded client retry when an expired cache is returned as regeneratable, so the learner page requeues generation instead of stopping with an empty lesson.
- Restarted the local service and verified `/api/health` returns `service_ready: true` with Neo4j, ChromaDB, and V4 available.
- `node --check pathly-app.js` and `python -m py_compile pathly_server.py` passed. The local shell Python environment could not collect pytest because FastAPI is not installed there.

# 2026-08-19 Private-document partial-source handling

- A private-document learning path no longer fails its entire Day 1 when one planned concept has no retrievable public source text.
- Sections with `source_text_unavailable` or `no_reliable_source` are omitted from the learner-facing lecture; usable live sections remain available. A day with zero usable sections still fails explicitly.
- This keeps the user-upload path honest: no unsupported section is presented as grounded, and no generic fallback section is inserted silently.

# 2026-08-19 Private-document lecture cache visibility

- Completed Day 1 lectures generated from a learner's own uploaded documents are now returned to that learner even if a later server-side scenario fingerprint differs.
- This avoids hiding a finished private-document lesson behind a stale/failed placeholder after a local restart or non-content configuration change. Explicit regeneration remains available for a fresh result.
- Verification: Python compilation, JavaScript syntax validation, and local service health check passed.
# Interaction polish: onboarding clarity and learning dashboard (2026-08-21)
- Clarified the knowledge-map action copy and added a prominent scope instruction card.
- Grouped onboarding questions into long-term learner profile and current-path sections.
- Renamed self-regulation question to the simpler recovery-level wording.
- Changed V4 multiple-choice options to visibly selectable checkbox-style controls.
- Added optional AI-graded open-response submission for V4 sections; it never affects section completion.
- Removed the dashboard Knowledge Map/Activity Timeline switch and render the timeline directly between the map and planning rationale.
- Syntax check: `node --check pathly-app.js` passed.

# 2026-08-21 V4 example-discipline quality gate

- Added the internal `anchor-counterexample-v1` example contract without changing the visible Lecture V4 module order: one anchor scenario now carries the opening, intuition, mechanism, and worked example; a distinct counterexample is retained inside the existing Boundary area; transfer is reserved for the application exercise.
- Updated the V4 writer and exercise-writer inputs so the live model receives the same example contract. A deterministic, source-bounded guard replaces repeated or missing counterexamples from approved teaching claims instead of regenerating an entire section.
- Applied the guard to live, approved-profile fallback, and source-grounded fallback paths, so a weak single response cannot make the whole day unstable.
- Updated the learner-facing label to `Boundary and counterexample`; no new outer V4 section or repeated case-study card was added.
- The long-running active-generation watchdog now keeps an active job in `generating` state and its default window is 12 minutes, preventing a browser poll from falsely marking a GPT-5.4 Day 1 run as interrupted.

# 2026-08-21 Sequential Day 1 V4 delivery

- Changed normal learner Day 1 delivery from all-section background generation to sequential delivery: entering the day creates only Section 1; completing it queues exactly the next section.
- Future sections remain hidden rather than appearing as unfinished or empty cards. The learner-facing preparation state now says that the first section is being prepared, instead of displaying an inaccurate `0 of N` progress counter.
- Bumped the V4 generator cache identity so existing all-at-once lecture caches do not mask this behavior.
- Verification: source-grounded V4/frontend regression suite passed (48 tests), JavaScript syntax and Python compilation passed; local health endpoint returned HTTP 200 after restart.

# 2026-08-21 Lecture V4 deep-link route preservation

- Fixed the learner URL route for `daily_view=lecture-v4`: a persisted legacy daily-view state can no longer overwrite the explicit V4 deep-link after hydration.
- Recognised the sequential `waiting_for_completion` state as a valid V4 lesson state. A ready first section therefore remains on the final learning surface while later sections wait for learner completion.
- Verified the affected plan retains a ready first section and three intentionally deferred sections; JavaScript syntax validation and 23 source-grounded V4 endpoint tests passed. The live server is serving the updated frontend and reports HTTP 200 health.

# 2026-08-21 Published gold-source cache visibility

- Fixed the actual repeated empty-page cause for newly generated Self-Attention plans: the published `self-attention-gold-v1` asset manifest was incorrectly rejected by the legacy `*-assets-vN` cache-name rule.
- Current `*-gold-vN` and `*-assets-vN` manifests are now accepted while unreviewed manifests remain stale.
- Ready sequential lessons remain visible until the learner explicitly regenerates, even if a non-contract profile fingerprint changes after generation.
- Bumped the learner frontend asset URL to v152 and made explicit `daily_view=lecture-v4` routes authoritative throughout hydration.
- Verified plan `38da6d81-5820-4752-b18e-35e3f360eeb0` through the live API: `waiting_for_completion`, generation mode `live`, 1 ready section and 3 intentionally deferred sections. Cache-policy and V4 endpoint tests passed (26 tests).
