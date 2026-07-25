#!/usr/bin/env python
"""child_identity: learn per-corpus path->target-child rules for the 2026 import.

The 2026 TalkBank .cha files dropped @Participants names for most of the
CHILDES bank, so name-based child identity (the 2021.1 mechanism) collapses
every CHI in a corpus into one participant. The identity signal moved into
paths: child subdirectories (Brown/Adam/020304.cha), child filename stems
(Hall/BlackPro/anc.cha), filename prefixes (HSLLD admtp1.cha -> "adm"),
or one child per corpus.

For every corpus with 2021.1 ground truth (PID-matched transcripts; Trevor
Day's OSF corrections supersede 2021.1 for his 17 Eng-NA corpora), this
module LEARNS which path-derived key reproduces the ground-truth child
partition exactly (100% partition equality), applies the accepted rule to all
of the corpus's 2026 transcripts, and emits per-corpus identity maps that
`chatter_parse.py --identity-dir` consumes. Corpora below 100% agreement (or
without ground truth) are flagged for review with their best rule and
disagreement examples.

Usage:
  python child_identity.py --parquet parquet_full \
      --staging-2021 ../redivis/staging/2021.1 \
      --day-csv day_child_mapping.csv \
      --report validation/report.tsv \
      --out child_identity_maps
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict

import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from chatter_parse import enumerate_corpora

CHI_NAME_RE = re.compile(
    r"@Participants:\t?([^\n]*(?:\n\t[^\n]*)*)")


def scan_chi_names(work_root, corpora):
    """{(corpus_id, rel_in_corpus): CHI name} from raw @Participants headers.

    Read from the .cha files directly (not from a parquet that may already
    carry learned identities) so learning is not circular."""
    out = {}
    for i, (bank, rel, n) in enumerate(corpora):
        base = os.path.join(work_root, bank, rel)
        for root, _d, files in os.walk(base):
            for f in files:
                if not f.endswith(".cha"):
                    continue
                p = os.path.join(root, f)
                try:
                    head = open(p, "rb").read(6000).decode("utf-8", "replace")
                except OSError:
                    continue
                m = CHI_NAME_RE.search(head)
                if not m:
                    continue
                part_line = m.group(1).replace("\n\t", " ")
                chi = re.search(r"CHI ([A-Za-z_'\-]+) (?:Target_)?Child",
                                part_line)
                if chi:
                    out[(i + 1, os.path.relpath(p, base))] = chi.group(1)
    return out

# ---------------------------------------------------------------------------
# candidate key functions over the within-corpus relative path
# ---------------------------------------------------------------------------

def _stem(relpath):
    return os.path.splitext(os.path.basename(relpath))[0]


def key_subdir1(relpath, name):
    parts = relpath.split("/")
    return parts[0] if len(parts) > 1 else None


def key_subdir2(relpath, name):
    parts = relpath.split("/")
    return "/".join(parts[:2]) if len(parts) > 2 else None


def key_stem(relpath, name):
    return _stem(relpath)


def key_alpha_prefix(relpath, name):
    m = re.match(r"[A-Za-z]+", _stem(relpath))
    return m.group(0) if m else None


def key_digit_prefix(relpath, name):
    m = re.match(r"[0-9]+", _stem(relpath))
    return m.group(0) if m else None


def _key_prefix(k):
    def f(relpath, name, _k=k):
        s = _stem(relpath)
        return s[:_k] if len(s) >= _k else None
    return f


def key_digit_suffix(relpath, name):
    m = re.search(r"[0-9]+$", _stem(relpath))
    return m.group(0) if m else None


def key_before_last_sep(relpath, name):
    s = _stem(relpath)
    m = re.match(r"^(.*)[_-][^_-]+$", s)
    return m.group(1) if m else None


def key_file(relpath, name):
    return relpath


def key_name2026(relpath, name):
    return name


def key_single(relpath, name):
    return "corpus_child"


def _combo(f, g):
    def fn(relpath, name):
        a, b = f(relpath, name), g(relpath, name)
        return None if a is None or b is None else a + "|" + b
    return fn


# preference order among rules that reach 100% agreement (name2026 is
# promoted to the front when >=95% of the corpus's files carry a CHI name;
# ties among passing rules are broken by fewest distinct keys corpus-wide)
CANDIDATES = [
    ("subdir1", key_subdir1),
    ("subdir2", key_subdir2),
    ("alpha_prefix", key_alpha_prefix),
    ("stem", key_stem),
    ("digit_prefix", key_digit_prefix),
    ("digit_suffix", key_digit_suffix),
    ("before_last_sep", key_before_last_sep),
    ("subdir1+alpha_prefix", _combo(key_subdir1, key_alpha_prefix)),
    ("subdir1+digit_prefix", _combo(key_subdir1, key_digit_prefix)),
    ("subdir1+digit_suffix", _combo(key_subdir1, key_digit_suffix)),
    ("subdir1+stem", _combo(key_subdir1, key_stem)),
    ("prefix6", _key_prefix(6)),
    ("prefix5", _key_prefix(5)),
    ("prefix4", _key_prefix(4)),
    ("prefix3", _key_prefix(3)),
    ("prefix2", _key_prefix(2)),
    ("name2026", key_name2026),
    ("file", key_file),
    ("single", key_single),
]
CANDIDATE_FNS = dict(CANDIDATES)


def partition_agreement(keys, truths):
    """(passes_100, score, examples). Partition equality = key<->child
    bijection on the matched set. score = mean of key-group purity and
    child-group purity for ranking imperfect rules."""
    by_key = defaultdict(Counter)
    by_child = defaultdict(Counter)
    for k, c in zip(keys, truths):
        by_key[k][c] += 1
        by_child[c][k] += 1
    n = len(keys)
    passes = (None not in by_key
              and all(len(v) == 1 for v in by_key.values())
              and all(len(v) == 1 for v in by_child.values()))
    h = sum(max(v.values()) for v in by_key.values()) / n
    c = sum(max(v.values()) for v in by_child.values()) / n
    return passes, round((h + c) / 2, 4), (by_key, by_child)


def disagreement_examples(rel_truth_pairs, fn, names, limit=3):
    """A few (relpath, key, truth_child) rows where the rule conflicts."""
    by_key = defaultdict(set)
    for (rel, truth) in rel_truth_pairs:
        by_key[fn(rel, names.get(rel))].add(truth)
    bad_keys = {k for k, v in by_key.items() if len(v) > 1 or k is None}
    out = []
    for (rel, truth) in rel_truth_pairs:
        k = fn(rel, names.get(rel))
        if k in bad_keys:
            out.append({"file": rel, "key": k, "truth_child": str(truth)})
            if len(out) >= limit:
                break
    return out


def learn_rule(matched, names, name_coverage, all_relpaths):
    """matched: list of (relpath, truth_child). Returns (rule, passed,
    score, examples). Among rules reaching 100% partition equality on the
    matched set, the one producing the fewest distinct keys over ALL corpus
    files wins (coarsest generalization, e.g. digit_prefix over stem when
    unmatched files add session suffixes); ties break by preference order."""
    order = list(CANDIDATES)
    if name_coverage >= 0.95:
        order = [("name2026", key_name2026)] + \
                [c for c in order if c[0] != "name2026"]
    passing = []
    best = None
    truths = [t for _, t in matched]
    for prio, (rule, fn) in enumerate(order):
        keys = [fn(rel, names.get(rel)) for rel, _ in matched]
        passes, score, _ = partition_agreement(keys, truths)
        if passes:
            nkeys = len({fn(rp, names.get(rp)) for rp in all_relpaths})
            # fixed-length prefix rules are the most likely to over-merge
            # unseen children; deprioritize them in the tie-break
            risky = 1 if rule.startswith("prefix") else 0
            passing.append((risky, nkeys, prio, rule))
        if best is None or score > best[1]:
            best = (rule, score, fn)
    if passing:
        passing.sort()
        return passing[0][3], True, 1.0, []
    rule, score, fn = best
    return rule, False, score, disagreement_examples(matched, fn, names)


def detect_rule_unmatched(relpaths, names, name_coverage):
    """Structural heuristic for corpora with no ground truth."""
    if name_coverage >= 0.95:
        return "name2026"
    with_dir = sum(1 for r in relpaths if "/" in r)
    subdirs = {r.split("/")[0] for r in relpaths if "/" in r}
    if len(subdirs) >= 2 and with_dir >= 0.8 * len(relpaths):
        return "subdir1"
    stems = [_stem(r) for r in relpaths]
    if all(re.fullmatch(r"[0-9_]+", s) for s in stems):
        return "single"  # age-coded filenames: one longitudinal child
    return "stem"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build(parquet_dir, staging_2021, day_csv, report_tsv, out_dir,
          work_root=None):
    corpora = [c for c in enumerate_corpora(report_tsv) if c[2] > 0]
    corpus_rel = {i + 1: (bank, rel) for i, (bank, rel, _n)
                  in enumerate(corpora)}
    raw_names = scan_chi_names(work_root, corpora) if work_root else None

    tr26 = ds.dataset(os.path.join(parquet_dir, "transcript")).to_table(
        columns=["id", "pid", "filename", "corpus_id",
                 "target_child_name"]).to_pandas()
    # filename = '<corpus_rel>/<within>'; strip the corpus rel prefix
    tr26["rel_in_corpus"] = [
        fn[len(corpus_rel[cid][1]) + 1:]
        for fn, cid in zip(tr26.filename, tr26.corpus_id)]

    tr21 = ds.dataset(os.path.join(staging_2021, "transcript")).to_table(
        columns=["id", "pid", "filename", "target_child_id",
                 "target_child_name", "corpus_name", "collection_id"]).to_pandas()
    tr21 = tr21.rename(columns={
        "id": "id21", "target_child_id": "child21",
        "target_child_name": "name21"})
    coll21 = ds.dataset(os.path.join(staging_2021, "collection")).to_table(
        columns=["id", "data_source"]).to_pandas().rename(
        columns={"id": "collection_id", "data_source": "ds21"})
    tr21 = tr21.merge(coll21, on="collection_id", how="left")

    # filename-stem fallback index: TalkBank re-minted PIDs for some corpora
    # (Xinjiang, AcadLang, NewmanRatner, ...), so PID joins come up empty
    # there; the 2021.1 filename relative to the corpus is a stable second
    # key. Ambiguous (corpus_name, relstem) keys are dropped.
    def rel21(row):
        comps = row.filename.split("/")
        if row.corpus_name in comps:
            rel = "/".join(comps[comps.index(row.corpus_name) + 1:])
        else:
            rel = comps[-1]
        return os.path.splitext(rel)[0]
    tr21["relstem21"] = tr21.apply(rel21, axis=1)
    fname_index = {}
    seen_dup = set()
    for row in tr21.itertuples():
        k = (row.ds21, row.corpus_name, row.relstem21)
        if k in fname_index:
            seen_dup.add(k)
        fname_index[k] = row
    for k in seen_dup:
        del fname_index[k]

    day = pd.read_csv(day_csv)
    day = day.rename(columns={"transcript_id": "id21",
                              "new_child_id": "day_child"})
    day_ids = set(day.id21)
    day_corpora = set(day.corpus_name)

    m = tr26.merge(tr21[["id21", "pid", "child21", "name21"]],
                   on="pid", how="left")
    m = m.merge(day[["id21", "day_child"]], on="id21", how="left")

    os.makedirs(out_dir, exist_ok=True)
    results = []
    for cid, grp in m.groupby("corpus_id"):
        bank, rel = corpus_rel[cid]
        if raw_names is not None:
            names = {rp: raw_names.get((int(cid), rp))
                     for rp in grp.rel_in_corpus}
        else:  # only safe when parquet_dir was built WITHOUT an identity map
            names = dict(zip(grp.rel_in_corpus, grp.target_child_name))
        name_cov = (sum(1 for v in names.values() if v is not None)
                    / max(len(names), 1))
        relpaths = list(grp.rel_in_corpus)

        # filename-stem fallback for transcripts without a PID match
        ds_name = {"childes": "CHILDES", "phon": "PhonBank"}.get(bank, bank)
        corpus_basename = rel.split("/")[-1]
        n_fname_matched = 0
        fb_child = {}
        fb_name = {}
        fb_id21 = {}
        for row in grp[grp.child21.isna()].itertuples():
            stem_path = os.path.splitext(row.rel_in_corpus)[0]
            hit = fname_index.get((ds_name, corpus_basename, stem_path))
            if hit is not None and pd.notna(hit.child21):
                fb_child[row.rel_in_corpus] = hit.child21
                fb_name[row.rel_in_corpus] = hit.name21
                fb_id21[row.rel_in_corpus] = hit.id21
                n_fname_matched += 1
        if fb_child:
            grp = grp.copy()
            grp["child21"] = grp.apply(
                lambda r: fb_child.get(r.rel_in_corpus, r.child21), axis=1)
            grp["name21"] = grp.apply(
                lambda r: fb_name.get(r.rel_in_corpus, r.name21), axis=1)
            grp["id21"] = grp.apply(
                lambda r: fb_id21.get(r.rel_in_corpus, r.id21), axis=1)
            # extend Day truth through the recovered id21s as well
            day_by_id = dict(zip(day.id21, day.day_child))
            grp["day_child"] = grp.id21.map(day_by_id)

        # ground truth: Day's mapping supersedes 2021.1 where it exists
        is_day = bool(set(grp.id21.dropna()) & day_ids)
        if is_day:
            g = grp[grp.day_child.notna()]
            matched = list(zip(g.rel_in_corpus, g.day_child))
            truth_src = "day"
        else:
            g = grp[grp.child21.notna()]
            matched = list(zip(g.rel_in_corpus, g.child21))
            truth_src = "2021.1"
            if n_fname_matched:
                truth_src = "2021.1+fname"

        rec = {"corpus_id": int(cid), "bank": bank, "corpus": rel,
               "n_transcripts": len(grp), "n_matched": len(matched),
               "n_fname_matched": n_fname_matched,
               "truth_source": truth_src if matched else None,
               "name_coverage_2026": round(float(name_cov), 3)}

        if matched:
            rule, passed, score, examples = learn_rule(matched, names,
                                                       name_cov, relpaths)
            n_truth_children = len({t for _, t in matched})
            rec.update(rule=rule, agreement=score, accepted=passed,
                       n_truth_children=n_truth_children,
                       confidence="high" if passed else "review",
                       examples=examples)
        else:
            rule = detect_rule_unmatched(relpaths, names, name_cov)
            rec.update(rule=rule, agreement=None, accepted=False,
                       n_truth_children=None, confidence="low",
                       examples=[])

        # ------- assignment -------
        # Ground-truth-matched transcripts always take their truth child
        # directly (so even "review" corpora like Bates, where no path rule
        # can reach 100%, reproduce the corrected grouping exactly). The
        # learned rule only generalizes to unmatched (new/renamed) files:
        # a rule key that maps unambiguously to one truth child on matched
        # data joins that child; otherwise the key forms a new child group.
        fn = CANDIDATE_FNS[rec["rule"]]
        truth_by_rel = dict(matched) if matched else {}
        # per-truth-child display name: majority 2021.1 name; for Day
        # corpora keep it only when unique among the corpus's children
        # (split children shared one 2021.1 name -> use the Day label)
        name_votes = defaultdict(Counter)
        for _, row in grp.iterrows():
            if is_day and pd.notna(row.day_child):
                if pd.notna(row.name21):
                    name_votes[row.day_child][str(row.name21)] += 1
            elif not is_day and pd.notna(row.child21) and pd.notna(row.name21):
                name_votes[row.child21][str(row.name21)] += 1
        child_names = {}
        majority = {c: v.most_common(1)[0][0] for c, v in name_votes.items()}
        name_use = Counter(majority.values())
        for c in ({t for _, t in matched} if matched else set()):
            nm = majority.get(c)
            if nm is not None and (not is_day or name_use[nm] == 1):
                child_names[c] = nm
            elif is_day:
                child_names[c] = str(c)  # synthetic Day label
        # rule key -> truth child (only when unambiguous on matched data)
        key2children = defaultdict(set)
        for rel, truth in truth_by_rel.items():
            key2children[fn(rel, names.get(rel))].add(truth)
        key2truth = {k: next(iter(v)) for k, v in key2children.items()
                     if len(v) == 1 and k is not None}

        assignments = {}
        n_fallback = 0
        for rp in relpaths:
            if rp in truth_by_rel:
                truth = truth_by_rel[rp]
                key = "truth:" + str(truth)
                cname = child_names.get(truth, names.get(rp))
            else:
                k = fn(rp, names.get(rp))
                if k is None:  # rule does not cover this file: own child
                    key = "file:" + rp
                    n_fallback += 1
                    cname = names.get(rp)
                elif k in key2truth:
                    truth = key2truth[k]
                    key = "truth:" + str(truth)
                    cname = child_names.get(truth, names.get(rp))
                else:
                    key = "rule:" + str(k)
                    cname = names.get(rp)
            cname = None if (cname is None or pd.isna(cname)) else str(cname)
            assignments[rp] = {"key": key, "name": cname}
        rec["n_fallback_files"] = n_fallback
        rec["n_children_assigned"] = len(
            {v["key"] for v in assignments.values()})
        results.append(rec)

        with open(os.path.join(out_dir, "corpus-%04d.json" % cid), "w") as f:
            json.dump({"corpus_id": int(cid), "bank": bank, "corpus": rel,
                       "rule": rec["rule"], "confidence": rec["confidence"],
                       "assignments": assignments}, f, ensure_ascii=False)

    with open(os.path.join(out_dir, "learn_results.json"), "w") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parquet", required=True,
                    help="existing full-run parquet dir (transcript dataset)")
    ap.add_argument("--staging-2021", required=True,
                    help="2021.1 staged parquet root")
    ap.add_argument("--day-csv", required=True,
                    help="Trevor Day transcript->child mapping CSV (OSF)")
    ap.add_argument("--report", required=True,
                    help="validation sweep TSV enumerating corpora")
    ap.add_argument("--out", required=True, help="identity maps output dir")
    ap.add_argument("--work", default=None,
                    help="work root; when given, CHI names are scanned from "
                         "the raw .cha headers (required if --parquet was "
                         "built with an identity map)")
    args = ap.parse_args(argv)
    results = build(args.parquet, args.staging_2021, args.day_csv,
                    args.report, args.out, work_root=args.work)
    acc = sum(1 for r in results if r.get("accepted"))
    rev = sum(1 for r in results if r.get("confidence") == "review")
    low = sum(1 for r in results if r.get("confidence") == "low")
    print("corpora: %d | accepted(100%%): %d | review: %d | low(no truth): %d"
          % (len(results), acc, rev, low))
    from collections import Counter as C
    print("rules:", C(r["rule"] for r in results))


if __name__ == "__main__":
    main()
