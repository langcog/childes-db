#!/usr/bin/env python3
"""Upload one staged childes-db version (redivis/staging/<version>/) to the
datapages.childes-db Redivis dataset, then optionally release.

Versions must be uploaded in chronological order (2018.1 -> 2021.1 -> ...);
each Redivis version fully replaces every table (upload_merge_strategy
"replace", set via update() on every run -- the create-time argument does not
take effect and appending would silently double the data on re-release).

Usage: python3 upload_redivis.py --version 2018.1 [--release] [--notes "..."]
Reads REDIVIS_API_TOKEN from .secrets at the repo root.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# set the token before importing redivis
with open(REPO_ROOT / ".secrets") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)

import redivis  # noqa: E402

TABLE_DESCRIPTIONS = {
    "collection": "One row per top-level CHILDES collection (e.g. Eng-NA, Spanish), generally corresponding to a language or region.",
    "corpus": "One row per corpus (e.g. Brown, Providence), linked to its collection.",
    "participant": "One row per participant (children and caregivers) per corpus, with role, demographics, and age range; non-child participants link to their target child.",
    "transcript": "One row per transcript file, with date, language, filename (CHILDES path), PID, and target child info.",
    "utterance": "One row per utterance: gloss, stem, utterance type, token/morpheme counts, phonology, media timestamps, speaker and target-child info (denormalized).",
    "token": "One row per word token: gloss, stem, part of speech, morphology (prefix/suffix/clitic), phonology, speaker and target-child info (denormalized). The largest table.",
    "token_frequency": "Per-transcript word frequency counts by speaker role (gloss x count).",
    "transcript_by_speaker": "Per-transcript per-speaker summary statistics: num tokens/types/utterances/morphemes and derived measures (MLU-w, MLU-m, MTLD, HD-D).",
    "admin": "Import metadata for this childes-db release (date, version string).",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="childes-db version, e.g. 2018.1")
    ap.add_argument("--staging-root", default=str(REPO_ROOT / "redivis" / "staging"))
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--notes", default=None)
    args = ap.parse_args()

    staged = Path(args.staging_root) / args.version
    table_dirs = sorted(d for d in staged.iterdir() if d.is_dir())
    incomplete = [d.name for d in table_dirs if not (d / ".done").exists()]
    if incomplete:
        sys.exit(f"tables not fully exported yet: {incomplete}")

    ds = redivis.organization("datapages").dataset("childes-db")
    if not ds.exists():
        print("creating dataset datapages.childes-db")
        ds.create(
            public_access_level="data",
            description=(
                "childes-db: a database-formatted mirror of CHILDES, the Child "
                "Language Data Exchange System (Sanchez et al. 2019, Behavior "
                "Research Methods). Each dataset version corresponds to a "
                "childes-db release. See langcog.github.io/childes-db-website "
                "and github.com/langcog/childes-db."
            ),
        )
    else:
        print("creating next version of datapages.childes-db")
        ds = ds.create_next_version(if_not_exists=True)

    expected = {}
    # upload small tables first; token last
    for d in sorted(table_dirs, key=lambda d: sum(
            f.stat().st_size for f in d.glob("part-*.parquet"))):
        tname = d.name
        meta = json.loads((d / ".done").read_text())
        expected[tname] = meta["rows"]
        tb = ds.table(tname)
        if not tb.exists():
            tb.create(description=TABLE_DESCRIPTIONS.get(tname))
        tb.update(upload_merge_strategy="replace")
        parts = sorted(d.glob("part-*.parquet"))
        # skip parts already fully uploaded (names are normalized server-side,
        # so compare on alphanumerics only)
        norm = lambda s: re.sub(r"[^A-Za-z0-9]", "", s)
        done_uploads = set()
        for u in tb.list_uploads():
            props = getattr(u, "properties", {}) or {}
            if props.get("status") in ("completed", "succeeded"):
                done_uploads.add(norm(props.get("name", "")))
        print(f"uploading {tname}: {meta['rows']:,} rows in {len(parts)} parts "
              f"({len(done_uploads)} already up)")
        for p in parts:
            upload_name = f"{tname}-{p.name}"
            if norm(upload_name) in done_uploads:
                continue
            for attempt in range(4):
                try:
                    tb.upload(upload_name).create(
                        content=str(p), type="parquet", replace_on_conflict=True)
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    print(f"  {upload_name}: {type(e).__name__}, "
                          f"retrying in {60 * (attempt + 1)}s", flush=True)
                    time.sleep(60 * (attempt + 1))

    if args.release:
        notes = args.notes or f"childes-db {args.version}, imported from the hosted MySQL database."
        print("releasing version...")
        ds.release(release_notes=notes)
        released = redivis.organization("datapages").dataset("childes-db")
        print(f"released as {released.get().properties.get('version', {}).get('tag')}")
        for tname, n in expected.items():
            props = released.table(tname).get().properties
            got = int(props.get("numRows", -1))
            status = "OK" if got == n else "MISMATCH"
            print(f"  {tname}: expected {n:,}, redivis has {got:,} [{status}]")
    else:
        print("uploaded to draft next version (not released)")


if __name__ == "__main__":
    main()
