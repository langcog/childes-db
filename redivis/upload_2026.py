#!/usr/bin/env python3
"""Upload the 2026.1 release candidate (pipeline/parquet_full/) to the
datapages.childes-db Redivis dataset as the next version (v1.4).

Differences from upload_redivis.py (the per-version MySQL staging uploader):
- reads the full-run layout: <table>.parquet single files or <table>/part-*.parquet
- creates the new token_morpheme table
- synthesizes the admin table row (version "2026.1" + release date)
- expected row counts come from parquet metadata, verified against Redivis
  after release

Usage: python3 upload_2026.py [--release] [--notes "..."]
Reads REDIVIS_API_TOKEN from .secrets. DO NOT run --release without the
identity report + team QA sign-off.
"""

import argparse
import datetime
import os
import re
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as pads
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = Path(os.environ.get("CHILDES_2026_SRC",
                          REPO_ROOT / "pipeline" / "parquet_compact"))

with open(REPO_ROOT / ".secrets") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)

import redivis  # noqa: E402

TABLES = [
    "collection", "corpus", "participant", "transcript", "utterance",
    "token", "token_morpheme", "token_frequency", "transcript_by_speaker",
    "admin",
]

NEW_TABLE_DESCRIPTIONS = {
    "token_morpheme": (
        "One row per morpheme (new in 2026.1): token_id FK, morpheme_order, "
        "type (stem/clitic), UD lemma, pos, and features (JSON-array string), "
        "with the standard denormalized keys. Populated from Batchalign-era "
        "%mor tiers via the chatter parser."
    ),
}

DEFAULT_NOTES = (
    "childes-db 2026.1: full re-import of CHILDES and PhonBank from the "
    "2026-07 TalkBank release via the new chatter-based pipeline "
    "(langcog/childes-db pipeline/). +24% utterances and +28% tokens vs "
    "2021.1 (~73 new corpora). New: token_morpheme table (UD morphology), "
    "%gra dependency columns on token, utterance-level ort (romanization) "
    "and spa (speech acts), PhonBank phonology, media timestamps. "
    "Child identities are path-derived (TalkBank removed header names) and "
    "incorporate Day (2026) participant corrections; numeric ids are "
    "release-internal — use the TalkBank pid for cross-version linkage. "
    "NOTE: num_morphemes/MLU-m are not comparable to earlier versions "
    "(UD morphology re-annotation); MLU-w is comparable. 225 invalid CHAT "
    "files (0.4%) were skipped; see langcog/childes-db issues."
)


def table_files(name):
    single = SRC / f"{name}.parquet"
    if single.exists():
        return [single]
    d = SRC / name
    if d.is_dir():
        return sorted(d.glob("part-*.parquet"))
    return []


def make_admin_file():
    path = SRC / "admin.parquet"
    schema = pa.schema([
        pa.field("id", pa.int64()), pa.field("date", pa.date32()),
        pa.field("version", pa.string()),
    ])
    pq.write_table(pa.Table.from_pylist(
        [{"id": 1, "date": datetime.date.today(), "version": "2026.1"}],
        schema=schema), path, compression="zstd")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--notes", default=DEFAULT_NOTES)
    args = ap.parse_args()

    if not (SRC / "admin.parquet").exists():
        make_admin_file()

    expected = {}
    for t in TABLES:
        files = table_files(t)
        if not files:
            sys.exit(f"no parquet found for table {t}")
        expected[t] = sum(pq.read_metadata(f).num_rows for f in files)
        print(f"{t}: {expected[t]:,} rows in {len(files)} file(s)")

    ds = redivis.organization("datapages").dataset("childes-db")
    ds = ds.create_next_version(if_not_exists=True)

    norm = lambda s: re.sub(r"[^A-Za-z0-9]", "", s)
    for t in TABLES:
        tb = ds.table(t)
        if not tb.exists():
            tb.create(description=NEW_TABLE_DESCRIPTIONS.get(t))
        tb.update(upload_merge_strategy="replace")
        done_uploads = set()
        for u in tb.list_uploads():
            props = getattr(u, "properties", {}) or {}
            if props.get("status") in ("completed", "succeeded"):
                done_uploads.add(norm(props.get("name", "")))
        files = table_files(t)
        print(f"uploading {t}: {expected[t]:,} rows, {len(files)} file(s) "
              f"({len(done_uploads)} already up)")
        for p in files:
            upload_name = f"{t}-{p.name}"
            if norm(upload_name) in done_uploads:
                continue
            for attempt in range(4):
                try:
                    tb.upload(upload_name).create(
                        content=str(p), type="parquet",
                        replace_on_conflict=True)
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    print(f"  {upload_name}: {type(e).__name__}, retry in "
                          f"{60 * (attempt + 1)}s", flush=True)
                    time.sleep(60 * (attempt + 1))

    if not args.release:
        print("uploaded to draft next version (NOT released)")
        return
    print("releasing...")
    ds.release(release_notes=args.notes)
    released = redivis.organization("datapages").dataset("childes-db")
    print(f"released as "
          f"{released.get().properties.get('version', {}).get('tag')}")
    for t, n in expected.items():
        got = int(released.table(t).get().properties.get("numRows", -1))
        print(f"  {t}: expected {n:,}, redivis has {got:,} "
              f"[{'OK' if got == n else 'MISMATCH'}]")


if __name__ == "__main__":
    main()
