# Pathly Runbook

## Local product mode

From `.trae`, run `./start_pathly.ps1`, then open `http://127.0.0.1:4173/`.
The local launcher enables anonymous session ownership, disables demo behavior,
and uses a non-Secure cookie only because localhost is HTTP.

## Production

Build from `project_code`:

```powershell
docker build -f .trae/Dockerfile -t pathly .
docker run --rm -p 4173:4173 --env-file .trae/.env -v pathly-data:/app/data pathly
```

Production requires HTTPS, `PATHLY_REQUIRE_SESSION_AUTH=true`, and
`PATHLY_COOKIE_SECURE=true`. Secrets remain server-side.


`Source-Grounded Lecture View v4` is an isolated pilot. Production keeps
`PATHLY_LECTURE_V4_ENABLED=false` until its source-linking stages are accepted.
Set it to `true` only for a local or explicitly selected pilot environment.

## Boundaries

Pathly is the learner product. Port 8501 is the separate administrator console
for public KG and RAG construction. Pathly never depends on the 8501 page for
runtime APIs.

## Checks

- `/api/health` reports service readiness.
- `/api/capabilities` reports KG, RAG, document, workload, capacity, and schedule support.
- Unauthenticated private API requests return 401.
- Neo4j failure falls back to calibrated JSON and is labelled fallback.
- Unscheduled activities remain visible rather than being discarded.

## Daily learning and Content Agent

After a plan v2 is scheduled, the learner opens `Today Learning`. The first visit activates the path with the browser's local date and IANA timezone. Pathly maps Day N to a calendar date, selects the earliest due learning day, and generates or restores its cached lesson.

The Content Agent attempts Neo4j context first, falls back to the calibrated JSON KG, retrieves public Chroma chunks and linked private chunks, then calls the configured OpenAI model. If the model is unavailable, Pathly renders a deterministic KG/RAG lesson with an explicit `fallback` label and reason. Cache identity includes the current profile version and retrieved source context.

Moving a learning day shifts that day and later dates together. If the resulting final date crosses the confirmed deadline, the API returns a preview and the UI requires a second confirmation before writing any date changes.

Operational checks:

- `/api/capabilities` includes `daily_learning`.
- A private request without the anonymous session cookie returns 401.
- `GET /api/paths/{path_id}/today` restores the active day after refresh.
- Repeated content generation with unchanged inputs returns `cache_status=hit`.
- Citations distinguish `public_rag` from `private_document`.
- `PATHLY_CONTENT_MODEL` selects the server-side model; the default is `gpt-4.1-mini`.
