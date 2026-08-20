from pathlib import Path


def test_dockerfile_uses_project_context_without_copying_private_state():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "docker build -f .trae/Dockerfile" in dockerfile
    assert "COPY KG_construction/agents" in dockerfile
    assert "COPY KG_construction/infra" in dockerfile
    assert "global_knowledge_graph_calibrated.json" in dockerfile
    assert "COPY . ." not in dockerfile
    # The public Chroma index is immutable build input.  Learner-owned SQLite
    # state, documents, and private indexes must remain outside the image.
    assert "COPY KG_construction/data/learner_profiles.db" not in dockerfile
    assert "COPY KG_construction/data/pathly_learning.db" not in dockerfile
    assert "COPY KG_construction/data/pathly_private" not in dockerfile
    assert "COPY .env" not in dockerfile
    assert "PATHLY_REQUIRE_SESSION_AUTH=true" in dockerfile
    assert "PATHLY_COOKIE_SECURE=true" in dockerfile


def test_public_environment_and_runbook_document_security_limits():
    env = Path(".env.example").read_text(encoding="utf-8")
    runbook = Path("documents/PATHLY_RUNBOOK.md").read_text(encoding="utf-8")
    privacy = Path("documents/PATHLY_PRIVACY_AND_RECOVERY.md").read_text(encoding="utf-8")
    assert "PATHLY_MAX_PDF_BYTES=" in env
    assert "PATHLY_MAX_PDF_PAGES=" in env
    assert "PATHLY_MAX_DOCUMENT_CHUNKS=" in env
    assert "PATHLY_MAX_PARSE_SECONDS=" in env
    assert "project_code" in runbook
    assert "8501" in runbook
    assert "500" in privacy
    assert "120" in privacy


def test_runtime_requirements_include_planning_dependencies():
    requirements = Path("requirements-pathly.txt").read_text(encoding="utf-8")
    assert "networkx" in requirements
    assert "neo4j" in requirements
    assert "fastapi" in requirements
