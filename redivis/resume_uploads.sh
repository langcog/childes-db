#!/bin/bash
# Resilient upload/release driver: picks up where stage_all.sh left off.
# The hardened upload_redivis.py skips already-completed uploads, so retries
# are cheap; generous retry budget rides out intermittent network drops.
# Usage: PYTHON=<python> bash redivis/resume_uploads.sh [version ...]
set -u
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
VERSIONS=("${@:-2018.1 2019.1 2020.1 2021.1}")
[ $# -eq 0 ] && VERSIONS=(2018.1 2019.1 2020.1 2021.1)

for version in "${VERSIONS[@]}"; do
  echo "=========== upload $version ==========="
  ok=0
  for attempt in $(seq 1 40); do
    if "$PYTHON" redivis/upload_redivis.py --version "$version" --release \
        --notes "childes-db $version, imported from the hosted childes-db MySQL database (langcog/childes-db)."; then
      ok=1; break
    fi
    echo "upload of $version failed (attempt $attempt/40), retrying in 180s..."
    sleep 180
  done
  if [ "$ok" != 1 ]; then echo "upload of $version FAILED permanently"; exit 1; fi
done
echo "ALL UPLOADS RELEASED"
