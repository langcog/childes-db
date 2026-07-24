#!/usr/bin/env python
"""chatter_parse: CHAT -> Chatter JSON -> childes-db-style parquet tables.

Prototype of the new childes-db import pipeline. Replicates the childes-db
2021.1 table semantics (see djangoapp/db/models.py, childes_db.py,
transcripts_participants.py) from the typed JSON emitted by the `chatter` CLI
(`chatter to-json file.cha`), and writes one zstd parquet file per table.

Tables produced (columns mirror the 2021.1 MySQL tables, with additions):
  collection, corpus, participant, transcript,
  utterance      (+ ort, spa),
  token          (+ gra_index, gra_head, gra_relation),
  token_morpheme (NEW: one row per morpheme from the typed %mor items;
                  design follows childes-mor by Meylan/Braginsky),
  transcript_by_speaker, token_frequency

Known, documented differences from the 2021.1 build:
  * filenames end in .cha rather than .xml (match on stem).
  * Morphology in current TalkBank .cha files is UD-style (Batchalign/stanza),
    not the old MOR grammar: part_of_speech is a UD POS ("pron", not
    "pro:int"), suffix holds the UD feature chain ("Fin Ind Pres S3"),
    prefix/english are always empty, and num_morphemes counts
    1 (lemma) + n(features) + n(post-clitics).
  * media_start/media_end are seconds (converted from chatter's ms bullets).

Designed to stream: one file is parsed, converted and appended to the parquet
writers at a time; nothing corpus-sized is held in RAM.

Usage:
  python chatter_parse.py --out parquet_proto work/childes/Eng-NA/Brown \
      work/childes/Japanese/Hamasaki
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import subprocess
import sys
import time
import warnings
from datetime import date, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import scipy.special

log = logging.getLogger("chatter_parse")

CHATTER_DEFAULT = os.path.expanduser("~/.local/bin/chatter")

# ---------------------------------------------------------------------------
# lexical diversity: exact port of djangoapp/db/lexical_diversity.py,
# operating on a list of gloss strings instead of Django Token objects.
# ---------------------------------------------------------------------------

def _mtld_calc(word_array, ttr_threshold):
    current_ttr = 1.0
    token_count = 0
    type_count = 0
    types = set()
    factors = 0.0
    for token in word_array:
        token = token.lower()
        token_count += 1
        if token not in types:
            type_count += 1
            types.add(token)
        current_ttr = type_count / token_count
        if current_ttr <= ttr_threshold:
            factors += 1
            token_count = 0
            type_count = 0
            types = set()
            current_ttr = 1.0
    excess = 1.0 - current_ttr
    excess_val = 1.0 - ttr_threshold
    factors += excess / excess_val
    if factors != 0:
        return len(word_array) / factors
    return -1


def mtld(word_array, ttr_threshold=0.72):
    """word_array: list of gloss strings. None below 50 tokens (as in 2021.1)."""
    if len(word_array) < 50:
        return None
    result = (_mtld_calc(word_array, ttr_threshold)
              + _mtld_calc(word_array[::-1], ttr_threshold)) / 2
    if math.isnan(result):
        return 0
    return round(result, 3) if result else result


def _hypergeometric(population, population_successes, sample, sample_successes):
    with warnings.catch_warnings():
        # inf/inf for very large transcripts -> nan; the 2021.1 code treated
        # this RuntimeWarning as an error and returned hdd = 0. We return nan
        # here and let the isfinite check in hdd() do the same.
        warnings.simplefilter("ignore", RuntimeWarning)
        return (scipy.special.comb(population_successes, sample_successes)
                * scipy.special.comb(population - population_successes,
                                     sample - sample_successes)) \
            / scipy.special.comb(population, sample)


def hdd(word_array, sample_size=42.0):
    """word_array: list of gloss strings. None below 50 tokens (as in 2021.1)."""
    if len(word_array) < 50:
        return None
    type_counts = {}
    for token in word_array:
        token = token.lower()
        type_counts[token] = type_counts.get(token, 0.0) + 1.0
    hdd_value = 0.0
    for token_type in type_counts:
        hgeo = _hypergeometric(len(word_array), sample_size,
                               type_counts[token_type], 0.0)
        if not math.isfinite(hgeo):  # port of the RuntimeWarning -> 0 branch
            return 0
        hdd_value += (1.0 - hgeo) / sample_size
    if math.isnan(hdd_value):
        return 0
    return round(hdd_value, 3) if hdd_value else hdd_value


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

# chatter terminator type -> childes-db utterance.type
# (childes_db.py: p->declarative, q->question, e->imperative_emphatic, else the
#  talkbank XML terminator name; names below are the XML names for each mark)
TERMINATOR_TYPE_MAP = {
    "period": "declarative",
    "question": "question",
    "exclamation": "imperative_emphatic",
    "trailingoff": "trail off",
    "trailing_off_question": "trail off question",
    "interruption": "interruption",
    "interruptedquestion": "interruption question",
    "selfinterruption": "self interruption",
    "self_interrupted_question": "self interruption question",
    "brokenquestion": "question exclamation",
    "quoted_new_line": "quotation next line",
    "quoted_period_simple": "quotation precedes",
    "break_for_coding": "broken for coding",
}
MISSING_TERMINATOR_TYPE = "missing CA terminator"


def parse_chat_age(age):
    """CHAT age 'Y;MM.DD' -> age in days (same day math as db/utils.parse_age)."""
    if not age:
        return None
    m = re.match(r"^(\d+)(?:;(\d+)?(?:\.(\d+)?)?)?", age.strip())
    if not m:
        return None
    y = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else 0
    d = int(m.group(3)) if m.group(3) else 0
    days = y * 365.25 + mo * 365.25 / 12 + d
    return days if days != 0 else None


def parse_chat_date(datestr):
    """CHAT date '08-OCT-1962' -> datetime.date, else None."""
    if not datestr:
        return None
    try:
        return datetime.strptime(datestr.strip(), "%d-%b-%Y").date()
    except ValueError:
        try:
            return datetime.strptime(datestr.strip(), "%d-%B-%Y").date()
        except ValueError:
            return None


def bullet_text(data):
    """Flatten a chatter BulletContent (or plain string) to a text string."""
    if data is None:
        return None
    if isinstance(data, str):
        return data
    segments = (data.get("content") or {}).get("segments") or data.get("segments") or []
    parts = [s.get("text", "") for s in segments if s.get("type") == "text"]
    return " ".join(p for p in parts if p) or None


def _pho_item_str(item):
    """A PhoItem is a string or a group (list of strings)."""
    if isinstance(item, str):
        return item
    if isinstance(item, list):
        return " ".join(_pho_item_str(x) for x in item)
    return str(item)


def extract_phonology(utt):
    """Return (actual_items, model_items) from an utterance's pho tiers.

    Sources, in preference order:
      * typed %pho / %mod tiers (PhonBank): dependent tier types 'Pho'/'Mod'
        with data.items = list of PhoItem;
      * %xpho / %xmod tiers (e.g. Providence, Davis): UserDefined tiers with
        label 'xpho'/'xmod' and a whitespace-separated string.

    Either element is None when that tier is absent.
    """
    pho = mod = None
    xpho = xmod = None
    for dt in utt.get("dependent_tiers", []):
        t, data = dt.get("type"), dt.get("data")
        if t == "Pho" and isinstance(data, dict):
            pho = [_pho_item_str(x) for x in data.get("items") or []]
        elif t == "Mod" and isinstance(data, dict):
            mod = [_pho_item_str(x) for x in data.get("items") or []]
        elif t == "UserDefined" and isinstance(data, dict):
            if data.get("label") == "xpho" and isinstance(data.get("content"), str):
                xpho = data["content"].split()
            elif data.get("label") == "xmod" and isinstance(data.get("content"), str):
                xmod = data["content"].split()
    return (pho if pho is not None else xpho,
            mod if mod is not None else xmod)


def word_payload(item):
    """The Word object inside a content item (replaced_word wraps its word)."""
    return item["word"] if item["type"] == "replaced_word" else item


def word_gloss(word):
    return word.get("cleaned_text") or word.get("raw_text") or ""


# ---------------------------------------------------------------------------
# content walking
# ---------------------------------------------------------------------------

# content item types that carry no word material at all
NON_WORD_TYPES = {
    "pause", "event", "annotated_event", "freecode", "annotated_action",
    "separator", "postcode", "tagmarker", "long_event",
    "overlap_point", "internal_bullet", "other_spoken_event",
}
# quotation words are ordinary alignable tokens (old pipeline saw them as
# <w>); pho groups (`‹...›`) wrap ordinary words for %pho alignment
GROUP_TYPES = {"retrace", "annotated_group", "group", "quotation",
               "pho_group"}
WORD_TYPES = {"word", "annotated_word", "replaced_word"}


def walk_content(items, in_retrace, tokens, slots, unknown_types):
    """Recursively walk main-tier content.

    tokens: list of dicts {item, word, in_retrace, slot} (childes-db tokens:
        every word incl. retraces/xxx, but not omissions/fillers/nonwords).
    slots: the mor-alignable unit sequence (MainWordIndex space): words with no
        category and not inside a retrace, plus separators. Each slot is a
        token list index or None (separator).
    """
    for item in items:
        t = item.get("type")
        if t in WORD_TYPES:
            w = word_payload(item)
            category = w.get("category")
            if category is not None:
                # omissions / fillers / nonwords / fragments: the old pipeline
                # never saw these as <w> tokens; they are also outside the
                # mor-alignable domain.
                continue
            # a replaced word is alignable even when its spoken form is
            # xxx/yyy ("xxx [: Iolo]"): %mor annotates the replacement
            alignable = (not in_retrace) and (
                t == "replaced_word" or w.get("untranscribed") is None)
            tok = {"item": item, "word": w, "slot": None}
            if alignable:
                tok["slot"] = len(slots)
                # a replaced word ("gonna [: going to]") expands to one
                # alignable unit (= one %mor item) per replacement word; the
                # old pipeline merged the replacement's morphology into the
                # single spoken token, so all its slots point at this token.
                n_slots = 1
                if t == "replaced_word":
                    rep_words = (item.get("replacement") or {}).get("words") or []
                    n_slots = max(1, len(rep_words))
                for _ in range(n_slots):
                    slots.append(len(tokens))
            tokens.append(tok)
        elif t in GROUP_TYPES:
            inner = (item.get("content") or {}).get("content") or []
            walk_content(inner, in_retrace or t == "retrace",
                         tokens, slots, unknown_types)
        elif t == "separator":
            # commas / tag marks (‡) / vocative marks („) get their own %mor
            # item (e.g. cm|cm) and thus occupy an alignable slot; CA/prosodic
            # separators (e.g. ca_continuation) do not, and neither does
            # anything inside a retrace (%mor skips retraced material).
            if not in_retrace and item.get("kind") in ("comma", "tag",
                                                       "vocative"):
                slots.append(None)
        elif t in NON_WORD_TYPES:
            continue
        else:
            unknown_types.add(t)
            inner = (item.get("content") or {}).get("content")
            if inner:
                walk_content(inner, in_retrace, tokens, slots, unknown_types)


def _append(tok, key, value):
    """Space-join successive morphology values onto a token field."""
    if not value:
        return
    prev = tok.get(key)
    tok[key] = (prev + " " + value) if prev else value


def attach_morphology(tokens, slots, utt, stats):
    """Attach mor + gra info to tokens via chatter's precomputed alignments."""
    tiers = {dt["type"]: dt.get("data") for dt in utt.get("dependent_tiers", [])}
    mor = tiers.get("Mor")
    if not mor:
        return
    alignments = utt.get("alignments") or {}
    mor_align = alignments.get("mor")
    if not mor_align:
        return
    units = (alignments.get("units") or {}).get("main_mor")
    if units is not None and len(units) != len(slots):
        # our reconstruction of the alignable domain disagrees with chatter's;
        # skip morphology for this utterance rather than misattach.
        stats["slot_mismatch"] += 1
        return
    if mor_align.get("errors"):
        stats["mor_align_errors"] += 1
    items = mor.get("items") or []

    # chunk sequence for %gra: each mor item = main chunk + one per post-clitic
    item_main_chunk = []
    chunk = 0
    for it in items:
        item_main_chunk.append(chunk)
        chunk += 1 + len(it.get("post_clitics") or [])

    gra = tiers.get("Gra")
    gra_align = alignments.get("gra")
    gra_by_chunk = {}
    if gra and gra_align:
        relations = gra.get("relations") or []
        for pair in gra_align.get("pairs") or []:
            ci, gi = pair.get("mor_chunk_index"), pair.get("gra_index")
            if ci is not None and gi is not None and gi < len(relations):
                gra_by_chunk[ci] = relations[gi]

    for pair in mor_align.get("pairs") or []:
        si, ti = pair.get("source_index"), pair.get("target_index")
        if si is None or ti is None or si >= len(slots) or ti >= len(items):
            continue
        tok_idx = slots[si]
        if tok_idx is None:  # separator slot (e.g. Japanese comma -> cm|cm)
            continue
        tok = tokens[tok_idx]
        item = items[ti]
        main = item.get("main") or {}
        clitics = item.get("post_clitics") or []
        # typed morpheme list for the token_morpheme table. chatter's Mor
        # item structure (see `chatter schema`) is main + post_clitics, each
        # a MorWord {pos, lemma, features}; UD-style %mor has no
        # prefix/compound substructure (compound lemmas are fused, separated
        # prefixes are their own main-tier tokens), so the prefix / suffix /
        # compound_part types are reserved and currently never emitted.
        morphemes = tok.setdefault("morphemes", [])
        morphemes.append({"type": "stem", "lemma": main.get("lemma"),
                          "pos": main.get("pos"),
                          "features": main.get("features") or []})
        for c in clitics:
            morphemes.append({"type": "clitic", "lemma": c.get("lemma"),
                              "pos": c.get("pos"),
                              "features": c.get("features") or []})
        # accumulate: a multi-word replacement maps several mor items onto one
        # token (old pipeline joined the children's morphology with spaces)
        _append(tok, "stem", main.get("lemma") or "")
        _append(tok, "pos", main.get("pos") or "")
        _append(tok, "suffix", " ".join(main.get("features") or []))
        # old clitic column was " ".join([pos, stem, mk]) -> e.g. "cop be 3S"
        _append(tok, "clitic", " ".join(
            " ".join([c.get("pos") or "", c.get("lemma") or "",
                      " ".join(c.get("features") or [])]).strip()
            for c in clitics))
        n_morph = 0
        if main.get("lemma"):
            n_morph += 1
        n_morph += len(main.get("features") or [])
        n_morph += len(clitics)
        if n_morph:
            tok["num_morphemes"] = (tok.get("num_morphemes") or 0) + n_morph
        rel = gra_by_chunk.get(item_main_chunk[ti])
        if rel and "gra_index" not in tok:  # first item's relation wins
            tok["gra_index"] = rel.get("index")
            tok["gra_head"] = rel.get("head")
            tok["gra_relation"] = rel.get("relation")


# ---------------------------------------------------------------------------
# parquet schemas
# ---------------------------------------------------------------------------

def _schema(cols):
    return pa.schema(cols)

SCHEMAS = {
    "collection": _schema([("id", pa.int64()), ("name", pa.string()),
                           ("data_source", pa.string())]),
    "corpus": _schema([("id", pa.int64()), ("name", pa.string()),
                       ("collection_id", pa.int64()),
                       ("collection_name", pa.string()),
                       ("data_source", pa.string())]),
    "participant": _schema([
        ("id", pa.int64()), ("code", pa.string()), ("name", pa.string()),
        ("role", pa.string()), ("corpus_id", pa.int64()),
        ("corpus_name", pa.string()), ("min_age", pa.float64()),
        ("max_age", pa.float64()), ("language", pa.string()),
        ("group", pa.string()), ("sex", pa.string()), ("ses", pa.string()),
        ("education", pa.string()), ("custom", pa.string()),
        ("target_child_id", pa.int64()), ("collection_id", pa.int64()),
        ("collection_name", pa.string())]),
    "transcript": _schema([
        ("id", pa.int64()), ("corpus_id", pa.int64()),
        ("corpus_name", pa.string()), ("language", pa.string()),
        ("date", pa.date32()), ("filename", pa.string()),
        ("target_child_id", pa.int64()), ("target_child_name", pa.string()),
        ("target_child_age", pa.float64()), ("target_child_sex", pa.string()),
        ("collection_id", pa.int64()), ("collection_name", pa.string()),
        ("pid", pa.string())]),
    "utterance": _schema([
        ("id", pa.int64()), ("gloss", pa.string()), ("stem", pa.string()),
        ("actual_phonology", pa.string()), ("model_phonology", pa.string()),
        ("type", pa.string()), ("language", pa.string()),
        ("num_morphemes", pa.int32()), ("num_tokens", pa.int32()),
        ("utterance_order", pa.int32()), ("corpus_name", pa.string()),
        ("part_of_speech", pa.string()), ("speaker_code", pa.string()),
        ("speaker_name", pa.string()), ("speaker_role", pa.string()),
        ("target_child_name", pa.string()), ("target_child_age", pa.float64()),
        ("target_child_sex", pa.string()), ("media_start", pa.float64()),
        ("media_end", pa.float64()), ("media_unit", pa.string()),
        ("collection_name", pa.string()), ("collection_id", pa.int64()),
        ("corpus_id", pa.int64()), ("speaker_id", pa.int64()),
        ("target_child_id", pa.int64()), ("transcript_id", pa.int64()),
        # new columns
        ("ort", pa.string()), ("spa", pa.string())]),
    "token": _schema([
        ("id", pa.int64()), ("gloss", pa.string()), ("language", pa.string()),
        ("token_order", pa.int32()), ("replacement", pa.string()),
        ("prefix", pa.string()), ("part_of_speech", pa.string()),
        ("stem", pa.string()), ("actual_phonology", pa.string()),
        ("model_phonology", pa.string()), ("suffix", pa.string()),
        ("num_morphemes", pa.int32()), ("english", pa.string()),
        ("clitic", pa.string()), ("utterance_type", pa.string()),
        ("corpus_name", pa.string()), ("speaker_code", pa.string()),
        ("speaker_name", pa.string()), ("speaker_role", pa.string()),
        ("target_child_name", pa.string()), ("target_child_age", pa.float64()),
        ("target_child_sex", pa.string()), ("collection_name", pa.string()),
        ("collection_id", pa.int64()), ("corpus_id", pa.int64()),
        ("speaker_id", pa.int64()), ("target_child_id", pa.int64()),
        ("transcript_id", pa.int64()), ("utterance_id", pa.int64()),
        # new columns (from the %gra tier via chatter alignments)
        ("gra_index", pa.int32()), ("gra_head", pa.int32()),
        ("gra_relation", pa.string())]),
    # NEW table (no 2021.1 counterpart): one row per morpheme, from chatter's
    # typed Mor items. `type` is stem | clitic today; prefix | suffix |
    # compound_part are reserved for classic-MOR data if chatter ever exposes
    # them (UD-style %mor fuses compounds and has no prefix marking).
    "token_morpheme": _schema([
        ("id", pa.int64()), ("token_id", pa.int64()),
        ("morpheme_order", pa.int32()), ("type", pa.string()),
        ("lemma", pa.string()), ("pos", pa.string()),
        ("features", pa.string()),  # JSON-array string, e.g. '["Inf","S"]'
        ("language", pa.string()), ("utterance_id", pa.int64()),
        ("transcript_id", pa.int64()), ("corpus_id", pa.int64()),
        ("corpus_name", pa.string()), ("speaker_id", pa.int64()),
        ("speaker_role", pa.string()), ("target_child_id", pa.int64()),
        ("collection_id", pa.int64()), ("collection_name", pa.string())]),
    "transcript_by_speaker": _schema([
        ("id", pa.int64()), ("speaker_role", pa.string()),
        ("language", pa.string()), ("target_child_name", pa.string()),
        ("target_child_age", pa.float64()), ("target_child_sex", pa.string()),
        ("num_utterances", pa.int32()), ("mlu_w", pa.float64()),
        ("mlu_m", pa.float64()), ("mtld", pa.float64()),
        ("hdd", pa.float64()), ("num_types", pa.int32()),
        ("num_tokens", pa.int32()), ("num_morphemes", pa.int32()),
        ("collection_name", pa.string()), ("collection_id", pa.int64()),
        ("corpus_id", pa.int64()), ("speaker_id", pa.int64()),
        ("target_child_id", pa.int64()), ("transcript_id", pa.int64())]),
    "token_frequency": _schema([
        ("id", pa.int64()), ("gloss", pa.string()), ("count", pa.int32()),
        ("speaker_role", pa.string()), ("language", pa.string()),
        ("target_child_name", pa.string()), ("target_child_age", pa.float64()),
        ("target_child_sex", pa.string()), ("collection_name", pa.string()),
        ("collection_id", pa.int64()), ("corpus_id", pa.int64()),
        ("speaker_id", pa.int64()), ("target_child_id", pa.int64()),
        ("transcript_id", pa.int64())]),
}


class ParquetSink:
    """Streams row batches into one zstd parquet file per table.

    With `part=None` (prototype mode) each table is a single file
    `<out_dir>/<table>.parquet`. With a part name (full-run mode) each table
    is a directory of per-corpus files `<out_dir>/<table>/<part>.parquet`,
    which pyarrow.dataset reads transparently.
    """

    def __init__(self, out_dir, part=None):
        self.out_dir = out_dir
        self.part = part
        os.makedirs(out_dir, exist_ok=True)
        self._writers = {}

    def _path(self, table_name):
        if self.part is None:
            return os.path.join(self.out_dir, table_name + ".parquet")
        d = os.path.join(self.out_dir, table_name)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, self.part + ".parquet")

    def write(self, table_name, rows):
        if not rows:
            return
        schema = SCHEMAS[table_name]
        if table_name not in self._writers:
            self._writers[table_name] = pq.ParquetWriter(
                self._path(table_name), schema, compression="zstd")
        self._writers[table_name].write_table(
            pa.Table.from_pylist(rows, schema=schema))

    def close(self):
        for w in self._writers.values():
            w.close()
        self._writers = {}


# ---------------------------------------------------------------------------
# main processor
# ---------------------------------------------------------------------------

class Processor:
    def __init__(self, sink, chatter_bin=CHATTER_DEFAULT, data_source="CHILDES",
                 id_offset=0, skip_pids=None):
        """id_offset: base added to every per-corpus table id (participant,
        transcript, utterance, token, token_morpheme, transcript_by_speaker,
        token_frequency). The full-corpus driver gives each corpus a disjoint
        id block so corpora can be processed in parallel with globally unique
        ids and valid cross-table FKs. collection/corpus ids are managed by
        the driver, not offset.

        skip_pids: transcripts whose @PID is in this set are skipped entirely
        (used to drop CHILDES-bank copies of transcripts that also exist in
        the PhonBank tree, which carries the phonology tiers)."""
        self.sink = sink
        self.chatter_bin = chatter_bin
        self.data_source = data_source
        self.id_offset = id_offset
        self.skip_pids = skip_pids or frozenset()
        self.ids = {t: 0 for t in SCHEMAS}
        self.collections = {}      # name -> row dict
        self.corpora = {}          # (collection, name) -> row dict
        self.participants = {}     # lookup key -> row dict
        self.seen_pids = set()
        self.stats = {"files": 0, "skipped_pid": 0, "skipped_invalid": 0,
                      "skipped_crossbank": 0, "slot_mismatch": 0,
                      "mor_align_errors": 0, "utterances": 0, "tokens": 0,
                      "morphemes": 0}
        self.unknown_types = set()

    def _next_id(self, table):
        self.ids[table] += 1
        if table in ("collection", "corpus"):
            return self.ids[table]
        return self.id_offset + self.ids[table]

    # -- header-level objects ------------------------------------------------

    def get_collection(self, name):
        if name not in self.collections:
            self.collections[name] = {"id": self._next_id("collection"),
                                      "name": name,
                                      "data_source": self.data_source}
        return self.collections[name]

    def get_corpus(self, collection, name):
        key = (collection["name"], name)
        if key not in self.corpora:
            self.corpora[key] = {"id": self._next_id("corpus"), "name": name,
                                 "collection_id": collection["id"],
                                 "collection_name": collection["name"],
                                 "data_source": self.data_source}
        return self.corpora[key]

    def get_or_create_participant(self, corpus, collection, pmeta, age,
                                  target_child=None):
        """Mirror of transcripts_participants.get_or_create_participant.

        pmeta: chatter participant entry {code, name, role, id:{...}}.
        Dedup key: (corpus, code, name, role) plus target_child for
        non-target-child participants.
        """
        pid_info = pmeta.get("id") or {}
        code = pmeta.get("code")
        name = pmeta.get("name")
        role = pmeta.get("role")
        key = (corpus["id"], code, name, role,
               target_child["id"] if target_child else None)
        participant = self.participants.get(key)
        if participant is None:
            language = pid_info.get("language")
            if isinstance(language, list):
                language = " ".join(language) or None
            participant = {
                "id": self._next_id("participant"),
                "code": code, "name": name, "role": role,
                "corpus_id": corpus["id"], "corpus_name": corpus["name"],
                "min_age": None, "max_age": None,
                "language": language,
                "group": pid_info.get("group"), "sex": pid_info.get("sex"),
                "ses": pid_info.get("ses"),
                "education": pid_info.get("education"),
                "custom": pid_info.get("custom"),
                "target_child_id": target_child["id"] if target_child else None,
                "collection_id": collection["id"],
                "collection_name": collection["name"],
            }
            self.participants[key] = participant
        # update_age semantics
        if age:
            if participant["min_age"] is None or age < participant["min_age"]:
                participant["min_age"] = age
            if participant["max_age"] is None or age > participant["max_age"]:
                participant["max_age"] = age
        return participant

    # -- corpus / file processing -------------------------------------------

    def process_corpus_dir(self, corpus_dir, collection=None, corpus=None,
                           rel_prefix=None, strict=True):
        """Process every .cha under corpus_dir.

        collection/corpus: pre-built row dicts (full-run mode); derived from
        the path when omitted (prototype mode). strict=False logs and skips
        files chatter cannot parse (known-invalid files) instead of raising.
        """
        corpus_dir = os.path.abspath(corpus_dir)
        corpus_name = os.path.basename(os.path.normpath(corpus_dir))
        collection_name = os.path.basename(os.path.dirname(corpus_dir))
        if collection is None:
            collection = self.get_collection(collection_name)
        if corpus is None:
            corpus = self.get_corpus(collection, corpus_name)
        if rel_prefix is None:
            rel_prefix = os.path.join(collection_name, corpus_name)
        cha_files = []
        for root, _dirs, files in os.walk(corpus_dir):
            for f in sorted(files):
                if f.endswith(".cha"):
                    cha_files.append(os.path.join(root, f))
        cha_files.sort()
        log.info("corpus %s/%s: %d .cha files",
                 collection["name"], corpus["name"], len(cha_files))
        for path in cha_files:
            rel = os.path.join(rel_prefix, os.path.relpath(path, corpus_dir))
            try:
                self.process_file(path, rel, corpus, collection)
            except Exception:
                if strict:
                    log.exception("failed on %s", path)
                    raise
                self.stats["skipped_invalid"] += 1
                log.warning("skipping invalid file %s: %s", path,
                            repr(sys.exc_info()[1])[:300])

    def run_chatter(self, path):
        res = subprocess.run([self.chatter_bin, "to-json", path],
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError("chatter failed on %s: %s"
                               % (path, res.stderr[:500]))
        return json.loads(res.stdout)

    def process_file(self, path, rel_filename, corpus, collection):
        doc = self.run_chatter(path)
        headers = [l["header"] for l in doc["lines"]
                   if l.get("line_type") == "header"]
        pid = next((h.get("pid") for h in headers if h.get("type") == "pid"),
                   None)
        if pid is not None:
            if pid in self.skip_pids:
                self.stats["skipped_crossbank"] += 1
                log.info("skipping %s: PID %s kept from the PhonBank tree",
                         rel_filename, pid)
                return
            if pid in self.seen_pids:
                self.stats["skipped_pid"] += 1
                log.info("skipping %s: PID %s already processed",
                         rel_filename, pid)
                return
            self.seen_pids.add(pid)

        langs = next((h.get("codes") for h in headers
                      if h.get("type") == "languages"), None) or doc.get("languages")
        language = " ".join(langs) if langs else None
        date_str = next((h.get("date") for h in headers
                         if h.get("type") == "date"), None)

        # participants: target child first (as in create_transcript_and_participants)
        pmap = doc.get("participants") or {}
        target_meta = [p for p in pmap.values()
                       if p.get("role") == "Target_Child"]
        target_child = None
        participants = []
        if len(target_meta) == 1:
            tmeta = target_meta[0]
            age = parse_chat_age((tmeta.get("id") or {}).get("age"))
            target_child = self.get_or_create_participant(
                corpus, collection, tmeta, age)
            target_child["target_child_id"] = target_child["id"]
            target_child["age"] = age  # per-transcript age, not persisted
            participants.append(target_child)
        others = [p for p in pmap.values()
                  if not (len(target_meta) == 1
                          and p.get("role") == "Target_Child")]
        code_to_participant = {}
        for pmeta in others:
            age = parse_chat_age((pmeta.get("id") or {}).get("age"))
            p = self.get_or_create_participant(corpus, collection, pmeta, age,
                                               target_child)
            p["age"] = age
            participants.append(p)
        for p in participants:
            code_to_participant[p["code"]] = p

        transcript = {
            "id": self._next_id("transcript"),
            "corpus_id": corpus["id"], "corpus_name": corpus["name"],
            "language": language, "date": parse_chat_date(date_str),
            "filename": rel_filename,
            "target_child_id": target_child["id"] if target_child else None,
            "target_child_name": target_child["name"] if target_child else None,
            "target_child_age": target_child["age"] if target_child else None,
            "target_child_sex": target_child["sex"] if target_child else None,
            "collection_id": collection["id"],
            "collection_name": collection["name"], "pid": pid,
        }
        self.sink.write("transcript", [transcript])

        self.process_utterances(doc, transcript, participants,
                                code_to_participant, target_child,
                                corpus, collection)
        self.stats["files"] += 1

    # -- utterances ----------------------------------------------------------

    def _denorm(self, speaker, target_child, transcript):
        return {
            "corpus_name": transcript["corpus_name"],
            "speaker_code": speaker["code"], "speaker_name": speaker["name"],
            "speaker_role": speaker["role"],
            "target_child_name": target_child["name"] if target_child else None,
            "target_child_age": target_child["age"] if target_child else None,
            "target_child_sex": target_child["sex"] if target_child else None,
            "collection_name": transcript["collection_name"],
            "collection_id": transcript["collection_id"],
            "corpus_id": transcript["corpus_id"], "speaker_id": speaker["id"],
            "target_child_id": target_child["id"] if target_child else None,
            "transcript_id": transcript["id"],
        }

    def process_utterances(self, doc, transcript, participants,
                           code_to_participant, target_child, corpus,
                           collection):
        utt_rows = []
        token_rows = []
        morpheme_rows = []
        # per-speaker accumulators for transcript_by_speaker / token_frequency
        per_speaker = {p["id"]: {"n_utt": 0, "tok_counts": [], "glosses": [],
                                 "morphemes": []}
                       for p in participants}

        order = 0
        for line in doc["lines"]:
            if line.get("line_type") != "utterance":
                continue
            order += 1
            utt = line
            main = utt["main"]
            speaker_code = main.get("speaker")
            speaker = code_to_participant.get(speaker_code)
            if speaker is None:
                # speaker appears in transcript body but not in @Participants
                log.warning("%s: speaker %s not declared; creating participant",
                            transcript["filename"], speaker_code)
                speaker = self.get_or_create_participant(
                    corpus, collection,
                    {"code": speaker_code, "name": None, "role": None},
                    None, target_child)
                speaker["age"] = None
                code_to_participant[speaker_code] = speaker
                participants.append(speaker)
                per_speaker[speaker["id"]] = {"n_utt": 0, "tok_counts": [],
                                              "glosses": [], "morphemes": []}

            term = (main.get("content") or {}).get("terminator")
            if term is None:
                utterance_type = MISSING_TERMINATOR_TYPE
            else:
                ttype = term.get("type")
                utterance_type = TERMINATOR_TYPE_MAP.get(ttype, ttype)

            bullet = main.get("bullet") \
                or (main.get("content") or {}).get("bullet")
            media_start = bullet["start_ms"] / 1000.0 if bullet else None
            media_end = bullet["end_ms"] / 1000.0 if bullet else None
            media_unit = "s" if bullet else None

            tiers = {dt["type"]: dt.get("data")
                     for dt in utt.get("dependent_tiers", [])}
            ort = tiers.get("Ort") if isinstance(tiers.get("Ort"), str) \
                else bullet_text(tiers.get("Ort"))
            spa = bullet_text(tiers.get("Spa"))
            pho_items, mod_items = extract_phonology(utt)

            # tokens
            tokens = []
            slots = []
            walk_content((main.get("content") or {}).get("content") or [],
                         False, tokens, slots, self.unknown_types)
            attach_morphology(tokens, slots, utt, self.stats)

            # token-level phonology uses the 2021.1 rule (reader_utils.
            # get_token_phonology): assign per token, in order, only when the
            # pho tier has exactly one item per token; otherwise
            # utterance-level only. (chatter's main_pho alignment domain
            # includes fillers/nonwords, which are not tokens, so a general
            # 1:1 index mapping onto tokens does not exist.)
            tok_pho = pho_items if pho_items and len(pho_items) == len(tokens) \
                else None
            tok_mod = mod_items if mod_items and len(mod_items) == len(tokens) \
                else None

            utterance_id = self._next_id("utterance")
            denorm = self._denorm(speaker, target_child, transcript)

            utt_gloss, utt_stem, utt_pos = [], [], []
            utt_num_morphemes = None
            for i, tok in enumerate(tokens, start=1):
                gloss = word_gloss(tok["word"])
                stem = tok.get("stem", "")
                pos = tok.get("pos", "")
                nm = tok.get("num_morphemes")
                if gloss:
                    utt_gloss.append(gloss)
                if stem:
                    utt_stem.append(stem)
                if pos:
                    utt_pos.append(pos)
                if nm:
                    utt_num_morphemes = (utt_num_morphemes or 0) + nm
                replacement = ""
                if tok["item"]["type"] == "replaced_word":
                    rep_words = (tok["item"].get("replacement") or {}) \
                        .get("words") or []
                    replacement = " ".join(word_gloss(w) for w in rep_words)
                token_id = self._next_id("token")
                token_rows.append(dict(
                    id=token_id, gloss=gloss,
                    language=transcript["language"], token_order=i,
                    replacement=replacement, prefix="",
                    part_of_speech=pos, stem=stem,
                    actual_phonology=tok_pho[i - 1] if tok_pho else "",
                    model_phonology=tok_mod[i - 1] if tok_mod else "",
                    suffix=tok.get("suffix", ""), num_morphemes=nm,
                    english="", clitic=tok.get("clitic", ""),
                    utterance_type=utterance_type,
                    utterance_id=utterance_id,
                    gra_index=tok.get("gra_index"),
                    gra_head=tok.get("gra_head"),
                    gra_relation=tok.get("gra_relation"),
                    **denorm))
                for j, mor in enumerate(tok.get("morphemes") or []):
                    morpheme_rows.append(dict(
                        id=self._next_id("token_morpheme"),
                        token_id=token_id, morpheme_order=j,
                        type=mor["type"], lemma=mor["lemma"],
                        pos=mor["pos"],
                        features=json.dumps(mor["features"]),
                        language=transcript["language"],
                        utterance_id=utterance_id,
                        transcript_id=transcript["id"],
                        corpus_id=transcript["corpus_id"],
                        corpus_name=transcript["corpus_name"],
                        speaker_id=speaker["id"],
                        speaker_role=speaker["role"],
                        target_child_id=(target_child["id"]
                                         if target_child else None),
                        collection_id=transcript["collection_id"],
                        collection_name=transcript["collection_name"]))

            utt_rows.append(dict(
                id=utterance_id, gloss=" ".join(utt_gloss),
                stem=" ".join(utt_stem),
                actual_phonology=" ".join(pho_items) if pho_items else "",
                model_phonology=" ".join(mod_items) if mod_items else "",
                type=utterance_type,
                language=transcript["language"],
                num_morphemes=utt_num_morphemes,
                num_tokens=len(utt_gloss), utterance_order=order,
                part_of_speech=" ".join(utt_pos),
                media_start=media_start, media_end=media_end,
                media_unit=media_unit, ort=ort, spa=spa, **denorm))

            acc = per_speaker[speaker["id"]]
            acc["n_utt"] += 1
            acc["tok_counts"].append(len(utt_gloss))
            acc["morphemes"].append(utt_num_morphemes)
            acc["glosses"].extend(word_gloss(t["word"]) for t in tokens)

            self.stats["utterances"] += 1
            self.stats["tokens"] += len(tokens)

        self.sink.write("utterance", utt_rows)
        self.sink.write("token", token_rows)
        self.sink.write("token_morpheme", morpheme_rows)
        self.stats["morphemes"] += len(morpheme_rows)

        # transcript_by_speaker + token_frequency
        tbs_rows, tf_rows = [], []
        for p in participants:
            acc = per_speaker[p["id"]]
            glosses = acc["glosses"]
            morphs = [m for m in acc["morphemes"] if m is not None]
            n_utt = acc["n_utt"]
            denorm = {
                "language": transcript["language"],
                "target_child_name": target_child["name"] if target_child else None,
                "target_child_age": target_child["age"] if target_child else None,
                "target_child_sex": target_child["sex"] if target_child else None,
                "collection_name": transcript["collection_name"],
                "collection_id": transcript["collection_id"],
                "corpus_id": transcript["corpus_id"],
                "speaker_id": p["id"],
                "target_child_id": target_child["id"] if target_child else None,
                "transcript_id": transcript["id"],
            }
            tbs_rows.append(dict(
                id=self._next_id("transcript_by_speaker"),
                speaker_role=p["role"],
                num_utterances=n_utt,
                mlu_w=(sum(acc["tok_counts"]) / n_utt) if n_utt else None,
                mlu_m=(sum(morphs) / len(morphs)) if morphs else None,
                mtld=mtld(glosses), hdd=hdd(glosses),
                num_types=len({g.lower() for g in glosses}),
                num_tokens=len(glosses),
                num_morphemes=sum(morphs) if morphs else None,
                **denorm))
            counts = {}
            for g in glosses:
                counts[g] = counts.get(g, 0) + 1
            for g in sorted(counts):
                tf_rows.append(dict(
                    id=self._next_id("token_frequency"), gloss=g,
                    count=counts[g], speaker_role=p["role"], **denorm))
        self.sink.write("transcript_by_speaker", tbs_rows)
        self.sink.write("token_frequency", tf_rows)

    # -- finalization --------------------------------------------------------

    def finalize(self, write_collections=True):
        if write_collections:
            self.sink.write("collection", list(self.collections.values()))
            self.sink.write("corpus", list(self.corpora.values()))
        rows = []
        for p in self.participants.values():
            rows.append({k: p.get(k) for k in
                         SCHEMAS["participant"].names})
        self.sink.write("participant", rows)
        self.sink.close()
        if self.unknown_types:
            log.warning("unhandled content item types: %s",
                        sorted(self.unknown_types))
        log.info("stats: %s", self.stats)


# ---------------------------------------------------------------------------
# full-corpus driver (parallel, resumable)
# ---------------------------------------------------------------------------

# Each corpus gets a disjoint id block for all per-corpus tables (ids are
# release-internal; the TalkBank PID is the externally-facing stable
# identifier). The largest corpus in the 2026 mirror uses ~1e7 token_morpheme
# ids, so 1e9 is ample, and 438 corpora * 1e9 stays far below 2^53 so ids
# survive an R numeric round-trip. The per-corpus marker files record the max
# local id actually used and the QA suite checks no block overflowed.
ID_BLOCK = 10**9

BANK_DATA_SOURCE = {"childes": "CHILDES", "phon": "PhonBank"}

PER_CORPUS_TABLES = ("participant", "transcript", "utterance", "token",
                     "token_morpheme", "transcript_by_speaker",
                     "token_frequency")


def enumerate_corpora(report_tsv):
    """(bank, corpus_relpath, n_cha) for every corpus in the sweep report.

    The sweep report (pipeline/validation/report.tsv) enumerates the TalkBank
    download units, including nested corpora like Other/Setswana/Matlhaku
    that a naive depth-1 directory scan would miss.
    """
    corpora = []
    with open(report_tsv) as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            row = dict(zip(header, line.rstrip("\n").split("\t")))
            corpora.append((row["bank"], row["corpus_path"],
                            int(row["n_cha"])))
    corpora.sort()
    return corpora


PID_RE = re.compile(r"@PID:\s*(\S+)")


def scan_pids(work_root, corpora, bank):
    """All @PIDs found in the given bank's .cha files (header scan only)."""
    pids = set()
    for b, rel, n in corpora:
        if b != bank or n == 0:
            continue
        base = os.path.join(work_root, b, rel)
        for root, _dirs, files in os.walk(base):
            for f in files:
                if not f.endswith(".cha"):
                    continue
                try:
                    with open(os.path.join(root, f), "rb") as fh:
                        head = fh.read(4096).decode("utf-8", "replace")
                except OSError:
                    continue
                m = PID_RE.search(head)
                if m:
                    pids.add(m.group(1))
    return pids


_SKIP_PIDS_CACHE = {}


def _load_skip_pids(path):
    if not path:
        return frozenset()
    if path not in _SKIP_PIDS_CACHE:
        with open(path) as f:
            _SKIP_PIDS_CACHE[path] = frozenset(json.load(f))
    return _SKIP_PIDS_CACHE[path]


def run_corpus_shard(task):
    """Pool worker: process one corpus into per-table part files."""
    t0 = time.time()
    logging.basicConfig(level=logging.WARNING)
    marker = task["marker"]
    if os.path.exists(marker):
        with open(marker) as f:
            return json.load(f)
    part = "part-%04d" % task["idx"]
    # remove stale part files from a previous crashed attempt
    for tbl in SCHEMAS:
        stale = os.path.join(task["out"], tbl, part + ".parquet")
        if os.path.exists(stale):
            os.remove(stale)
    stats = {"idx": task["idx"], "bank": task["bank"], "corpus": task["rel"]}
    try:
        sink = ParquetSink(task["out"], part=part)
        proc = Processor(sink, chatter_bin=task["chatter"],
                         data_source=task["corpus_row"]["data_source"],
                         id_offset=(task["idx"] + 1) * ID_BLOCK,
                         skip_pids=_load_skip_pids(task.get("skip_pids")))
        proc.process_corpus_dir(task["corpus_dir"],
                                collection=task["collection_row"],
                                corpus=task["corpus_row"],
                                rel_prefix=task["rel"], strict=False)
        proc.finalize(write_collections=False)
        stats.update(proc.stats)
        stats["max_local_id"] = max(proc.ids[t] for t in PER_CORPUS_TABLES)
        stats["unknown_types"] = sorted(proc.unknown_types)
    except Exception as e:  # corpus-level failure: report, don't kill the run
        stats["error"] = repr(e)[:500]
    stats["seconds"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    if "error" not in stats:
        with open(marker, "w") as f:
            json.dump(stats, f)
    return stats


def full_run(work_root, out_dir, report_tsv, jobs=8,
             chatter_bin=CHATTER_DEFAULT):
    corpora = enumerate_corpora(report_tsv)
    skipped_empty = [c for c in corpora if c[2] == 0]
    corpora = [c for c in corpora if c[2] > 0]
    log.info("%d corpora with .cha files (%d empty skipped)",
             len(corpora), len(skipped_empty))

    # cross-bank dedup: when the same @PID exists in both trees, the PhonBank
    # copy wins (it carries the phonology tiers). CHILDES-bank workers skip
    # any transcript whose PID appears in the PhonBank tree.
    os.makedirs(out_dir, exist_ok=True)
    phon_pids_path = os.path.join(out_dir, "phon_pids.json")
    if not os.path.exists(phon_pids_path):
        t0 = time.time()
        phon_pids = sorted(scan_pids(work_root, corpora, "phon"))
        with open(phon_pids_path, "w") as f:
            json.dump(phon_pids, f)
        log.info("scanned %d PhonBank PIDs in %.1fs", len(phon_pids),
                 time.time() - t0)

    # deterministic collection / corpus id assignment (same-named collections
    # in different banks stay separate rows, as in 2021.1)
    collections = {}
    tasks = []
    for idx, (bank, rel, _n) in enumerate(corpora):
        ds = BANK_DATA_SOURCE.get(bank, bank)
        cname = rel.split("/")[0]
        key = (ds, cname)
        if key not in collections:
            collections[key] = {"id": len(collections) + 1, "name": cname,
                                "data_source": ds}
        coll = collections[key]
        corpus_row = {"id": idx + 1, "name": os.path.basename(rel),
                      "collection_id": coll["id"], "collection_name": cname,
                      "data_source": ds}
        tasks.append({"idx": idx, "bank": bank, "rel": rel,
                      "corpus_dir": os.path.join(work_root, bank, rel),
                      "out": out_dir, "chatter": chatter_bin,
                      "collection_row": coll, "corpus_row": corpus_row,
                      "skip_pids": (phon_pids_path if bank == "childes"
                                    else None),
                      "marker": os.path.join(out_dir, "markers",
                                             "%04d.json" % idx)})

    pq.write_table(pa.Table.from_pylist(list(collections.values()),
                                        schema=SCHEMAS["collection"]),
                   os.path.join(out_dir, "collection.parquet"),
                   compression="zstd")
    pq.write_table(pa.Table.from_pylist([t["corpus_row"] for t in tasks],
                                        schema=SCHEMAS["corpus"]),
                   os.path.join(out_dir, "corpus.parquet"),
                   compression="zstd")

    import multiprocessing
    t0 = time.time()
    done = 0
    totals = {"files": 0, "utterances": 0, "tokens": 0, "morphemes": 0,
              "skipped_invalid": 0, "skipped_pid": 0,
              "skipped_crossbank": 0, "slot_mismatch": 0}
    failures = []
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(jobs) as pool:
        for stats in pool.imap_unordered(run_corpus_shard, tasks):
            done += 1
            if "error" in stats:
                failures.append(stats)
                log.error("[%d/%d] FAILED %s/%s: %s", done, len(tasks),
                          stats["bank"], stats["corpus"], stats["error"])
                continue
            for k in totals:
                totals[k] += stats.get(k, 0)
            log.info("[%d/%d] %s/%s: files=%d utt=%d tok=%d morph=%d "
                     "skipped=%d (%.1fs)", done, len(tasks), stats["bank"],
                     stats["corpus"], stats.get("files", 0),
                     stats.get("utterances", 0), stats.get("tokens", 0),
                     stats.get("morphemes", 0),
                     stats.get("skipped_invalid", 0), stats["seconds"])
    log.info("FULL RUN DONE in %.1f min: %s | %d corpus failures",
             (time.time() - t0) / 60, totals, len(failures))
    for f in failures:
        log.error("failed corpus: %s/%s: %s", f["bank"], f["corpus"],
                  f["error"])
    return totals, failures


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("corpus_dirs", nargs="*",
                    help="corpus directories, e.g. work/childes/Eng-NA/Brown")
    ap.add_argument("--out", required=True, help="output parquet directory")
    ap.add_argument("--chatter", default=CHATTER_DEFAULT,
                    help="path to the chatter binary")
    ap.add_argument("--data-source", default="CHILDES")
    ap.add_argument("--full-run", action="store_true",
                    help="process every corpus under --work (parallel, "
                         "resumable; corpora come from --report)")
    ap.add_argument("--work", default=None,
                    help="work root containing <bank>/<collection>/<corpus>")
    ap.add_argument("--report", default=None,
                    help="validation sweep TSV enumerating corpora")
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    if args.full_run:
        if not (args.work and args.report):
            ap.error("--full-run requires --work and --report")
        return full_run(args.work, args.out, args.report, jobs=args.jobs,
                        chatter_bin=args.chatter)
    if not args.corpus_dirs:
        ap.error("corpus_dirs required unless --full-run")
    sink = ParquetSink(args.out)
    proc = Processor(sink, chatter_bin=args.chatter,
                     data_source=args.data_source)
    for corpus_dir in args.corpus_dirs:
        proc.process_corpus_dir(corpus_dir)
    proc.finalize()
    return proc


if __name__ == "__main__":
    main()
