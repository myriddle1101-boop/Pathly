$ErrorActionPreference = "Stop"

$PathlyDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $PathlyDir
$Python = Join-Path $ProjectDir "KG_construction\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project Python environment not found: $Python"
}

Set-Location -LiteralPath $PathlyDir
$env:PATHLY_TEST_COMPAT = "false"
$env:PATHLY_REQUIRE_SESSION_AUTH = "true"
$env:PATHLY_COOKIE_SECURE = "false"
$env:KG_BACKEND = "neo4j"
# Avoid local `localhost` resolving to an unavailable IPv6 endpoint before Bolt.
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
# Local presentation: browsers share one Pathly learner while public/private data stores remain separate.
$env:PATHLY_LOCAL_DEMO_SHARED_MODE = "false"
$env:PATHLY_DEMO_USERS_ENABLED = "true"
if (-not $env:PATHLY_CONTROLLED_EVAL_MODEL) { $env:PATHLY_CONTROLLED_EVAL_MODEL = "gpt-5.4" }
if (-not $env:PATHLY_CONTENT_MODEL) { $env:PATHLY_CONTENT_MODEL = "gpt-5.4" }
if (-not $env:PATHLY_EXERCISE_MODEL) { $env:PATHLY_EXERCISE_MODEL = "gpt-5.4" }
# V4 is generated just in time.  Preserve GPT-5.4 for the Day 1 experience
# and route later source-grounded days to GPT-4.1 to keep the full path viable.
if (-not $env:PATHLY_V4_DAY1_MODEL) { $env:PATHLY_V4_DAY1_MODEL = "gpt-5.4" }
if (-not $env:PATHLY_V4_LATER_DAY_MODEL) { $env:PATHLY_V4_LATER_DAY_MODEL = "gpt-4.1" }
& $Python .\neo4j_preflight.py --start-desktop --timeout 45
if ($LASTEXITCODE -ne 0) {
    throw "Neo4j production preflight failed. Pathly was not started with a fallback KG."
}
& $Python -m uvicorn pathly_server:app --host 127.0.0.1 --port 4173


