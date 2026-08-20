from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    project_root_env = Path(__file__).resolve().parent.parent / ".env"
    kg_root_env = Path(__file__).resolve().parent / ".env"

    if project_root_env.exists():
        load_dotenv(project_root_env, override=False)
    if kg_root_env.exists():
        load_dotenv(kg_root_env, override=False)
