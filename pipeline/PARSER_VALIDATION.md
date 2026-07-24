# childes-db chatter pipeline prototype — validation report

**Date:** 2026-07-23
**Pipeline:** `pipeline/chatter_parse.py` (CHAT → `chatter to-json` → parquet)
**Scope:** `childes/Eng-NA/Brown` (214 .cha) + `childes/Japanese/Hamasaki` (32 .cha)
**Output:** `pipeline/parquet_proto/*.parquet` (zstd), one file per 2021.1 table:
collection, corpus, participant, transcript, utterance (+`ort`, `spa`),
token (+`gra_index`, `gra_head`, `gra_relation`), transcript_by_speaker,
token_frequency.

Totals: 246 files, 233,340 utterances, 804,890 tokens. Runtime ~70 s
single-process. Internal consistency counters: 0 utterances where the
reconstructed mor-alignment domain disagreed with chatter's
(`slot_mismatch=0`), 0 chatter mor-alignment errors.

## 1. Brown vs. childes-db 2021.1 (live MySQL, database `2021.1`)

Transcripts matched on filename stem (`Adam/020304.cha` ↔
`Eng-NA/Brown/Adam/020304.xml`): **214/214**.

### Per-transcript counts

| metric | 2021.1 total | new total | total diff | Pearson r | exact-match transcripts |
|---|---|---|---|---|---|
| utterances | 184,639 | 184,635 | −0.002% | 1.000000 | 205/214 |
| tokens | 672,429 | 672,689 | +0.039% | 0.999928 | 3/214 |

Median per-transcript |token diff| = 0.43%; max = 3.75%; 11/214 transcripts
exceed 2%.

### Per-speaker MLU-w (transcript_by_speaker, 898 matched rows)

| speaker | n | r | mean diff | mean \|diff\| | max \|diff\| |
|---|---|---|---|---|---|
| CHI | 214 | 0.9987 | −0.024 | 0.038 | 0.27 |
| MOT | 214 | 0.9993 | +0.012 | 0.020 | 0.10 |
| FAT | 68 | 0.9987 | +0.007 | 0.031 | 0.33 |

Corpus-level utterance-weighted MLU-w (diff = new − 2021.1): Adam CHI +0.017,
MOT +0.022, FAT +0.018; Eve CHI +0.016, MOT +0.028, FAT +0.005; Sarah CHI
−0.045, MOT +0.006, FAT +0.013.

Other transcript_by_speaker metrics: num_tokens r=0.9999, num_types r=0.9999,
mtld r=0.9913, hdd r=0.9963 (mtld/hdd ported verbatim from
`djangoapp/db/lexical_diversity.py`, including the None-below-50-tokens rule).

### Why the residual token deviations exist (all traced, none hidden)

Every deviation category examined traces to **content drift in the TalkBank
.cha files** (Brown was re-annotated with Batchalign3/stanza in 2026 — see the
`@Comment: [ba3 morphotag | engine=stanza-1.11.1 …]` headers), not to parser
behavior:

1. **Filler/fragment re-annotation (the Sarah −2 to −3.8% cluster and the CHI
   MLU-w −0.045).** 2021 XML had plain words `um`, `uh`, `ah`, `p`, `ch`;
   current files mark them `&-um`, `&+p`, `&~eye` (filler / phonological
   fragment / nonword). These were never `<w>` tokens in the old XML pipeline
   either — had the old pipeline seen today's files it would drop them too.
   Example (Sarah/020305): 2021.1 gloss `um hat` vs. current line
   `*CHI: &-um (.) hat .` → new gloss `hat`.
2. **Retranscription** (the Adam/020304 +2.3%): previously untranscribed
   material now `xxx` (2021.1 `my paper` → current `my paper xxx`), replaced
   forms normalized (`keep dat [: that]` → `keep that`), compounds split
   (`bunny+rabbit` → `bunny rabbit`).
3. **Utterance-count diffs (9 transcripts, ±1 to +4)**: utterances
   added/removed in retranscription; utterance order stays aligned elsewhere.

Per-utterance behavioral checks on identical content confirm the tokenizer
reproduces the old inventory exactly: words, retraces, quotations and
`xxx`/`yyy` are tokens; omissions (`0det`), fillers (`&-`), fragments (`&+`)
and nonwords (`&~`) are not; a replaced word (`neekle [: nickel]`) is one
token with gloss = spoken form, `replacement` = the correction, and morphology
merged from the replacement words (`gonna [: going to]` → stem `go to`,
pos `verb part`, matching the old join-children behavior).

## 2. Hamasaki (new-column validation)

48,705 utterances, 132,201 tokens.

* `ort` non-null on **99.93%** of utterances (the two files' handful of
  utterances without `%ort` are genuinely missing it).
* Morphology: **97.7%** of tokens have pos and lemma; the remainder are `xxx`
  tokens (2,918 — all correctly morphology-free), retraced words, and
  utterances without a `%mor` tier.
* `gra_*`: populated on **100%** of tokens that have morphology;
  `gra_index` strictly increasing within every utterance; `gra_head` ≤
  max(`gra_index`)+1 in 99.999% of utterances (the +1 is the terminator
  relation, PUNCT).
* `spa`: populates where `%spa` exists (3.2% of Hamasaki, 4.2% of Brown
  utterances — matches tier frequency in the files).

### Spot-checks against raw .cha (20203.cha), all exact

| utt | raw | parquet |
|---|---|---|
| 5 | `*CHI: xxx .` / `%ort: xxx .` | gloss `xxx`, ort `xxx .`, no morphology, type declarative |
| 40 | `*MOT: えらい なあ .` / `%mor: adj\|奇麗-S1 part\|な .` / `%gra: 1\|0\|ROOT 2\|1\|MARK` | tokens えらい (stem 奇麗, adj, suffix S1, 1\|0\|ROOT), なあ (な, part, 2\|1\|MARK); ort `erai naa .` |
| 100 | `*MOT: おう じょう ず !` / `%mor: adv\|おう verb\|渡る-Inf-S aux\|ず-Inf-Neg-S !` | 3 tokens with matching pos/lemma/features/gra; `!` → imperative_emphatic |

A comma-bearing utterance was also checked: the `、` separator correctly
consumes its own `%mor` (cm|cm) and `%gra` slot without becoming a token
(gra_index sequence on word tokens skips the comma's index, as in the raw
`%gra`).

## 3. Alignment-domain findings (encoded in `chatter_parse.py`)

Reverse-engineered and verified across all 246 files (0 mismatches):
chatter's mor-alignable unit sequence = words with no category prefix and not
inside a retrace, **plus** one slot per replacement word for
`word [: replacement]` forms, **plus** comma / tag (`‡`) / vocative (`„`)
separators; `xxx`/`yyy`, omissions, fillers, fragments, nonwords and
CA/prosodic separators are outside it. Quotation (`“…”`) contents are ordinary
alignable words.

## 4. Known, documented differences from 2021.1 (unavoidable or intentional)

1. **Morphology is UD-style** (Batchalign, in the source files):
   `part_of_speech` = UD POS (`pron` not `pro:int`), `stem` = UD lemma,
   `suffix` = UD feature chain (`Fin Ind Pres S3`), `clitic` = post-clitic(s)
   as `pos lemma features` (analogous to the old `cop be 3S`), `prefix` and
   `english` always empty. `num_morphemes` = 1 + n(features) +
   n(post-clitics), so **mlu_m/num_morphemes are not comparable to 2021.1**
   (mlu_w is, and was validated above).
2. `transcript.filename` ends `.cha` not `.xml` (match on stem).
3. utterance `actual_phonology`/`model_phonology` are empty (`%pho`/`%mod`
   absent from both prototype corpora; wiring exists for tiers but PhonBank
   handling is out of prototype scope).
4. `media_start/end` in seconds from chatter ms bullets (both corpora
   unlinked → null throughout).
5. `num_types` here is case-insensitive distinct gloss count (matches the
   2021.1 MySQL ci-collation behavior of `DISTINCT gloss`).
6. Participant `name` is null where current `@Participants` headers omit
   names the 2021 files had (e.g. `CHI Adam Target_Child` → `CHI
   Target_Child`); corpus drift, not parser behavior.

## 5. Reproduce

```
python pipeline/chatter_parse.py --out pipeline/parquet_proto \
    pipeline/work/childes/Eng-NA/Brown pipeline/work/childes/Japanese/Hamasaki
```

(venv needs pyarrow + scipy; validation additionally used pymysql + pandas
against MySQL db `2021.1`.)
