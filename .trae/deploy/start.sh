#!/bin/sh
set -eu

# Railway mounts /app/data after the image is built.  Seed only the immutable,
# public Chroma index on the first boot; private uploads and all learner state
# stay exclusively on the mounted volume.
if [ ! -f /app/data/chroma/chroma.sqlite3 ]; then
  mkdir -p /app/data/chroma
  cp -R /app/public_chroma_seed/. /app/data/chroma/
fi

exec uvicorn pathly_server:app --host 0.0.0.0 --port "${PORT:-4173}"
