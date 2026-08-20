# Pathly Privacy and Recovery

## Anonymous identity

Pathly creates an unguessable server-side anonymous session. The browser keeps
only an HttpOnly, SameSite=Lax cookie. Production uses Secure cookies over
HTTPS. Profiles, documents, drafts, estimates, decisions, and plans are owned
by the session identity; client-supplied user IDs are never trusted.

Anonymous sessions do not support cross-device recovery. Clearing the cookie
removes access to the anonymous workspace.

## Private materials

- Text PDFs up to 25 MB, 500 pages, 5000 chunks, and 120 seconds of parsing are supported.
- Private files, chunks, mappings, and indexes remain in the learner's private space.
- Private concepts never enter Neo4j or the public JSON KG.
- Scanned PDFs become `ocr_required`; invalid or oversized PDFs return recoverable states.
- Deleting a document removes its file, chunks, mappings, and private index without changing the public KG.

## Recovery

- Refresh restores the active onboarding draft and latest path from SQLite.
- Failed parsing can be retried or the document can be deleted.
- Neo4j failure falls back to calibrated JSON KG.
- Model failure uses a deterministic template and is labelled fallback.
- Capacity conflicts require an explicit learner decision.
- Schedule conflicts remain in `unscheduled_activities`.

## Daily content privacy

Daily lessons are owned by the anonymous server-side user and cannot be read by another session. The cache stores the rendered lesson, short citation excerpts, source identifiers, retrieval counts, and generation mode. It does not add private document text or private concepts to the public knowledge graph. OpenAI and retrieval credentials remain server-side. Structured service logs do not record lesson or document bodies.
