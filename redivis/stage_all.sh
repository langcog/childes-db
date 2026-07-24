#!/bin/bash
# Stage all childes-db versions to Redivis, oldest first, releasing each as a
# Redivis version. Exports are resumable; each export is retried on failure.
# Usage: PYTHON=<python-with-pymysql-pyarrow-redivis> bash redivis/stage_all.sh
set -u
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

for version in 2018.1 2019.1 2020.1 2021.1; do
  echo "=========== $version ==========="
  ok=0
  for attempt in 1 2 3 4 5 6 7 8; do
    if "$PYTHON" redivis/export_mysql.py --version "$version"; then
      ok=1; break
    fi
    echo "export of $version failed (attempt $attempt), retrying in 60s..."
    sleep 60
  done
  if [ "$ok" != 1 ]; then echo "export of $version FAILED, aborting"; exit 1; fi

  ok=0
  for attempt in 1 2 3; do
    if "$PYTHON" redivis/upload_redivis.py --version "$version" --release \
        --notes "childes-db $version, imported from the hosted childes-db MySQL database (langcog/childes-db)."; then
      ok=1; break
    fi
    echo "upload of $version failed (attempt $attempt), retrying in 120s..."
    sleep 120
  done
  if [ "$ok" != 1 ]; then echo "upload of $version FAILED, aborting"; exit 1; fi
done
echo "ALL VERSIONS STAGED AND RELEASED"
