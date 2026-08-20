# Pathly cloud pilot deployment

This configuration is for a small, HTTPS-only pilot with two simultaneous
testers.  It keeps the learner UI on Cloudflare Pages and sends `/api/*`
through a same-origin Pages Function to one Railway service.  The browser
never contacts Railway directly, so the HttpOnly anonymous-session cookie is
scoped to the Pages domain and Pathly's server-side owner checks continue to
protect every learner's data.

## 1. Create the Railway service

First create a private GitHub repository from `project_code`.  The root
`.gitignore` intentionally excludes `.env`, local learner state, documents,
and runtime logs before the first commit.  Connect that repository or upload
the `project_code` directory as the service
source.  The repository root must be `project_code`, not `.trae`; Railway will
read `railway.toml` and build `.trae/Dockerfile` with the project-root build
context.

Attach one persistent volume at `/app/data`.  Use a single replica for this
pilot: SQLite and the in-process V4 queue deliberately require it.  Create the
following Railway variables (do not place secrets in the repository):

```text
OPENAI_API_KEY=<your server-side key>
PATHLY_REQUIRE_SESSION_AUTH=true
PATHLY_COOKIE_SECURE=true
PATHLY_DATA_DIR=/app/data
PATHLY_PROFILE_DB=/app/data/learner_profiles.db
PATHLY_PLAN_DB=/app/data/pathly_learning.db
PATHLY_PRIVATE_DOCUMENT_DIR=/app/data/private_documents
PATHLY_PRIVATE_CHROMA_DIR=/app/data/private_chroma
PATHLY_CHROMA_DIR=/app/data/chroma
PATHLY_V4_MAX_CONCURRENT_JOBS=1
PATHLY_LECTURE_V4_ENABLED=true
PATHLY_DEMO_USERS_ENABLED=false
KG_BACKEND=neo4j
NEO4J_URI=<cloud Neo4j Bolt URI>
NEO4J_USER=<cloud Neo4j user>
NEO4J_PASSWORD=<cloud Neo4j password>
NEO4J_DATABASE=neo4j
```

Set the content-model variables to models available to your OpenAI project.
The current development defaults use `gpt-5.4`; use an explicitly available
model rather than relying on that default.  The health check is `/api/health`.
Do not share the Railway public URL with testers.

The image contains the immutable public Chroma index.  On a new volume,
`deploy/start.sh` copies that index once into `/app/data/chroma`.  Learner PDFs,
their private Chroma data, sessions, profiles, plans, and answer records are
only ever stored on the mounted volume.

## 2. Create the Cloudflare Pages project

Create a Pages project from the same repository with:

```text
Root directory: .trae
Build command: (leave empty)
Build output directory: .
```

Set the production environment variable below to the Railway HTTPS URL,
without a trailing slash:

```text
PATHLY_BACKEND_ORIGIN=https://<your-railway-service>.up.railway.app
```

The Pages Function in `functions/api/[[path]].js` forwards every API request
to that fixed origin and rewrites `Origin` for the backend's CSRF protection.
It does not expose the backend URL or the OpenAI key to the browser.

Attach a Cloudflare Pages hostname or custom domain, then use only that URL for
testing.  Verify `https://<pages-domain>/api/health` returns a healthy result.

## 3. Verify the pilot before inviting testers

Open the Pages URL in two separate private browser windows.  In each window,
complete a fresh onboarding flow and upload a different PDF.  Confirm that:

- each window receives a different anonymous `user_id`;
- either window receives 403/404 rather than the other user's document;
- both can create a plan;
- concurrent Day 1 generation shows one request queued and eventually completes;
- a Railway redeploy preserves both users' plans and documents;
- `/api/capabilities` shows the cloud Neo4j and public Chroma capabilities.

## Operating limits and next migration

This pilot intentionally uses one Railway replica and a mounted SQLite volume.
It is appropriate for the two-tester evaluation but is not horizontally
scalable.  R2, Postgres, and a managed vector database need storage-adapter
and migration work; they are not enabled by merely setting credentials.  Make
that change after the pilot, with an export/import and rollback plan, rather
than mixing it into the first user test.
