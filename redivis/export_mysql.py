#!/usr/bin/env python3
"""Export one childes-db version from the hosted MySQL server to parquet.

Streams each table with keyset pagination on the primary key and writes
zstd parquet part files of PART_ROWS rows, so an interrupted run resumes
at the last completed part. Django-internal tables are excluded.

Usage: python3 export_mysql.py --version 2018.1 [--staging-root redivis/staging]
Reads CHILDES_MYSQL_* credentials from .secrets at the repo root.
"""

import argparse
import datetime
import fcntl
import json
import sys
import time
from pathlib import Path

import pymysql
import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_TABLES = {"django_migrations", "django_content_type"}
CHUNK_ROWS = 250_000   # rows per SELECT
PART_ROWS = 500_000  # rows per parquet part file

MYSQL_TO_ARROW = {
    "bigint": pa.int64(), "int": pa.int64(), "smallint": pa.int64(),
    "tinyint": pa.int64(), "mediumint": pa.int64(),
    "varchar": pa.string(), "char": pa.string(), "text": pa.string(),
    "longtext": pa.string(), "mediumtext": pa.string(), "enum": pa.string(),
    "date": pa.date32(), "datetime": pa.timestamp("s"), "timestamp": pa.timestamp("s"),
    "double": pa.float64(), "float": pa.float64(), "decimal": pa.float64(),
}


def read_secrets():
    creds = {}
    with open(REPO_ROOT / ".secrets") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                creds[k] = v
    return creds


def connect(creds, version):
    return pymysql.connect(
        host=creds["CHILDES_MYSQL_HOST"], user=creds["CHILDES_MYSQL_USER"],
        password=creds["CHILDES_MYSQL_PASSWORD"], database=version,
        charset="utf8mb4", connect_timeout=30, read_timeout=600,
    )


def table_schema(cur, version, table):
    cur.execute(
        """SELECT column_name, data_type FROM information_schema.columns
           WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position""",
        (version, table),
    )
    fields = []
    for name, dtype in cur.fetchall():
        if dtype not in MYSQL_TO_ARROW:
            sys.exit(f"unmapped MySQL type {dtype} in {table}.{name}")
        fields.append(pa.field(name, MYSQL_TO_ARROW[dtype]))
    return pa.schema(fields)


def coerce(value, typ):
    # zero dates and other malformed temporals can come back as str
    if value is None:
        return None
    if pa.types.is_date(typ) or pa.types.is_timestamp(typ):
        if not isinstance(value, (datetime.date, datetime.datetime)):
            return None
    return value


def rows_to_table(rows, schema):
    cols = []
    for i, field in enumerate(schema):
        cols.append(pa.array([coerce(r[i], field.type) for r in rows], type=field.type))
    return pa.Table.from_arrays(cols, schema=schema)


def export_table(con, version, table, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    done_marker = out_dir / ".done"
    progress_file = out_dir / ".progress.json"
    if done_marker.exists():
        print(f"  {table}: already done, skipping")
        return
    # serialize concurrent exports of the same table (blocks until free)
    lock_file = open(out_dir / ".lock", "w")
    fcntl.flock(lock_file, fcntl.LOCK_EX)
    if done_marker.exists():  # another process finished it while we waited
        print(f"  {table}: done by concurrent process, skipping")
        lock_file.close()
        return

    cur = con.cursor()
    schema = table_schema(cur, version, table)
    colnames = ", ".join(f"`{f.name}`" for f in schema)

    last_id, part_num, total = 0, 0, 0
    if progress_file.exists():
        p = json.loads(progress_file.read_text())
        last_id, part_num, total = p["last_id"], p["part_num"], p["total"]
        print(f"  {table}: resuming after id {last_id} (part {part_num}, {total:,} rows)")

    buffer = []
    t0 = time.time()

    def flush_part():
        nonlocal buffer, part_num
        if not buffer:
            return
        part_path = out_dir / f"part-{part_num:05d}.parquet"
        tmp_path = out_dir / f".tmp-{part_num:05d}.parquet"
        pq.write_table(rows_to_table(buffer, schema), tmp_path, compression="zstd")
        tmp_path.rename(part_path)
        part_num += 1
        buffer = []
        progress_file.write_text(json.dumps(
            {"last_id": last_id, "part_num": part_num, "total": total}))

    while True:
        cur.execute(
            f"SELECT {colnames} FROM `{table}` WHERE id > %s ORDER BY id LIMIT %s",
            (last_id, CHUNK_ROWS),
        )
        rows = cur.fetchall()
        if not rows:
            break
        id_idx = [f.name for f in schema].index("id")
        last_id = rows[-1][id_idx]
        total += len(rows)
        buffer.extend(rows)
        if len(buffer) >= PART_ROWS:
            flush_part()
            rate = total / (time.time() - t0)
            print(f"  {table}: {total:,} rows ({rate:,.0f} rows/s)", flush=True)

    flush_part()
    if total == 0:
        # stage an explicit empty-schema part: with zero uploads, Redivis's
        # "replace" strategy keeps the previous version's rows (stale data)
        buffer = []
        part_path = out_dir / "part-00000.parquet"
        pq.write_table(rows_to_table([], schema), part_path, compression="zstd")
        part_num = 1
    done_marker.write_text(json.dumps({"rows": total, "parts": part_num}))
    progress_file.unlink(missing_ok=True)
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()
    print(f"  {table}: DONE, {total:,} rows in {part_num} parts "
          f"({time.time() - t0:,.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--staging-root", default=str(REPO_ROOT / "redivis" / "staging"))
    ap.add_argument("--tables", nargs="*", default=None,
                    help="subset of tables (default: all non-Django tables)")
    args = ap.parse_args()

    creds = read_secrets()
    con = connect(creds, args.version)
    cur = con.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema=%s AND table_type='BASE TABLE'", (args.version,))
    tables = sorted(t for (t,) in cur.fetchall() if t not in EXCLUDE_TABLES)
    if args.tables:
        tables = [t for t in tables if t in set(args.tables)]

    out_root = Path(args.staging_root) / args.version
    print(f"exporting {args.version}: {tables} -> {out_root}")
    # small tables first so failures on the big ones lose the least work
    def size_key(t):
        cur.execute(
            "SELECT COALESCE(data_length,0) FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name=%s", (args.version, t))
        return cur.fetchone()[0]
    for table in sorted(tables, key=size_key):
        export_table(con, args.version, table, out_root / table)
    con.close()
    print(f"export of {args.version} complete")


if __name__ == "__main__":
    main()
