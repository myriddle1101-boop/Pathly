FROM python:3.11-slim

WORKDIR /app
COPY .trae/requirements-pathly.txt /tmp/requirements-pathly.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /tmp/requirements-pathly.txt

# Build from project_code: docker build -f .trae/Dockerfile -t pathly .
# Only runtime code and the public KG enter the image; private data and .env do not.
COPY .trae/*.py /app/.trae/
COPY .trae/*.js /app/.trae/
COPY .trae/*.css /app/.trae/
COPY .trae/index.html /app/.trae/index.html
COPY .trae/documents/PATHLY_PRIVACY_AND_RECOVERY.md /app/.trae/documents/
COPY KG_construction/agents /app/KG_construction/agents
COPY KG_construction/infra /app/KG_construction/infra
COPY KG_construction/env_loader.py /app/KG_construction/env_loader.py
COPY KG_construction/stage1_adaptive_chunking.py /app/KG_construction/stage1_adaptive_chunking.py
COPY KG_construction/web_data/global /app/KG_construction/web_data/global
# This is public retrieval data only.  It is copied to a non-mounted seed
# location so a fresh persistent volume can initialize itself without ever
# baking learner uploads or SQLite state into the image.
COPY KG_construction/data/chroma /app/public_chroma_seed
COPY .trae/deploy/start.sh /app/start.sh

RUN mkdir -p /app/data/private_documents /app/data/private_chroma /app/data/chroma
WORKDIR /app/.trae
ENV PATHLY_REQUIRE_SESSION_AUTH=true
ENV PATHLY_COOKIE_SECURE=true
ENV PATHLY_DATA_DIR=/app/data
ENV PATHLY_PROFILE_DB=/app/data/learner_profiles.db
ENV PATHLY_PLAN_DB=/app/data/pathly_learning.db
ENV PATHLY_PRIVATE_DOCUMENT_DIR=/app/data/private_documents
ENV PATHLY_PRIVATE_CHROMA_DIR=/app/data/private_chroma
ENV PATHLY_CHROMA_DIR=/app/data/chroma
ENV PATHLY_KG_JSON=/app/KG_construction/web_data/global/global_knowledge_graph_calibrated.json
EXPOSE 4173
CMD ["/bin/sh", "/app/start.sh"]
