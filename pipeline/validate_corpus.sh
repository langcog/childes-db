#!/bin/bash
# Unzip the mirrored TalkBank corpora and run `chatter validate` per corpus.
# Produces pipeline/validation/report.tsv: bank, collection/corpus, n .cha
# files, valid count, invalid count.
# Usage: bash pipeline/validate_corpus.sh
set -u
cd "$(dirname "$0")/.."
CHATTER="${CHATTER:-$HOME/.local/bin/chatter}"
WORK=pipeline/work
REPORT_DIR=pipeline/validation
mkdir -p "$WORK" "$REPORT_DIR"
report="$REPORT_DIR/report.tsv"
echo -e "bank\tcorpus_path\tn_cha\tvalid\tinvalid" > "$report"

find pipeline/raw -name "*.zip" | sort | while read -r zip; do
  rel="${zip#pipeline/raw/}"          # childes/Eng-NA/Brown.zip
  bank="${rel%%/*}"
  corpus_path="${rel#*/}"; corpus_path="${corpus_path%.zip}"
  dest="$WORK/$bank/$corpus_path"
  if [ ! -d "$dest" ]; then
    mkdir -p "$dest"
    unzip -qo "$zip" -d "$dest" || { echo "UNZIP FAILED: $zip"; continue; }
  fi
  n_cha=$(find "$dest" -name "*.cha" | wc -l | tr -d ' ')
  if [ "$n_cha" = 0 ]; then
    echo -e "$bank\t$corpus_path\t0\t0\t0" >> "$report"
    continue
  fi
  out=$("$CHATTER" validate "$dest" 2>&1 | grep -E "^(Valid|Invalid):" || true)
  valid=$(echo "$out" | awk '/^Valid:/{print $2}')
  invalid=$(echo "$out" | awk '/^Invalid:/{print $2}')
  echo -e "$bank\t$corpus_path\t$n_cha\t${valid:-NA}\t${invalid:-NA}" >> "$report"
  if [ "${invalid:-0}" != "0" ] && [ "${invalid:-NA}" != "NA" ]; then
    echo "INVALID FILES in $corpus_path: $invalid/$n_cha"
  fi
done
echo "validation sweep complete: $(wc -l < "$report" | tr -d ' ') corpora"
