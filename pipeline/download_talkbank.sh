#!/bin/bash
# Download CHILDES .cha corpora from TalkBank (2026 layout, login required).
#
# TalkBank moved corpus downloads behind authentication; the working URL
# pattern (verified via browser download) is:
#   https://talkbank.org/data/childes/<Collection>/<Corpus>?f=zip
#
# TalkBank uses cookie-session auth (plain HTTP basic auth is ignored): the
# script first POSTs {email, pswd} to https://sla2.talkbank.org/logInUser
# (the same endpoint the website's login modal uses) and stores the session
# cookie, then downloads with that cookie.
#
# Credentials: put them in ~/.netrc (chmod 600):
#   machine talkbank.org login <your-talkbank-email> password <password>
# or run with TB_USER set and you'll be prompted once per run:
#   TB_USER=you@example.com bash pipeline/download_talkbank.sh test
#
# Subcommands:
#   test               download one known corpus (Biling/Gelman), verify zip
#   list <Collection>  fetch the collection index and print corpus links
#   mirror <outdir>    download every corpus in COLLECTIONS to <outdir>
#
# Run `test` first: unauthenticated requests return a 319-byte JS login
# shell with HTTP 200, so success can only be verified by file type.

set -euo pipefail

# BANK=childes (default) or BANK=phon for PhonBank:
#   BANK=phon bash pipeline/download_talkbank.sh mirror pipeline/raw
BANK="${BANK:-childes}"
BASE="https://talkbank.org/data/$BANK"

# Collection lists from the public access indexes (2026-07):
# https://talkbank.org/childes/access/ and https://talkbank.org/phon/access/
# "Derived" (derived datasets, not transcripts) is deliberately excluded.
if [ "$BANK" = "phon" ]; then
  COLLECTIONS=(Biling Chinese Clinical Dutch Eng-NA Eng-UK French German
    Japanese Other Romance Scandinavian Slavic Spanish)
else
  COLLECTIONS=(Biling Celtic Chinese Clinical-Eng Clinical-Other
    DutchAfrikaans EastAsian Eng-AAE Eng-NA Eng-UK Finno-Ugric French Frogs
    German GlobalTales Japanese MAIN Other Romance Scandinavian Slavic
    Spanish XLing)
fi

AUTH_SERVER="https://sla2.talkbank.org"
COOKIE_JAR=$(mktemp)
trap 'rm -f "$COOKIE_JAR"' EXIT

if [ -z "${TB_USER:-}" ]; then
  # parse machine talkbank.org entry from ~/.netrc
  TB_USER=$(awk '$1=="machine" && $2=="talkbank.org" {f=1} f && $1=="login" {print $2; exit}' ~/.netrc)
  TB_PASS=$(awk '$1=="machine" && $2=="talkbank.org" {f=1} f && $1=="password" {print $2; exit}' ~/.netrc)
  # single-line netrc format: machine X login Y password Z
  [ -z "$TB_USER" ] && TB_USER=$(awk '/machine[ \t]+talkbank\.org/ {for(i=1;i<NF;i++) if($i=="login") print $(i+1)}' ~/.netrc)
  [ -z "${TB_PASS:-}" ] && TB_PASS=$(awk '/machine[ \t]+talkbank\.org/ {for(i=1;i<NF;i++) if($i=="password") print $(i+1)}' ~/.netrc)
  [ -z "$TB_USER" ] && { echo "no talkbank.org entry in ~/.netrc and TB_USER not set"; exit 1; }
else
  read -r -s -p "TalkBank password for $TB_USER: " TB_PASS; echo
fi

login() {
  local payload resp
  payload=$(python3 -c 'import json,sys; print(json.dumps({"email": sys.argv[1], "pswd": sys.argv[2]}))' "$TB_USER" "$TB_PASS")
  resp=$(curl -s -c "$COOKIE_JAR" -H 'Content-Type: application/json' \
    -d "$payload" "$AUTH_SERVER/logInUser")
  if ! echo "$resp" | grep -q '"success" *: *true\|"success":true'; then
    echo "TalkBank login failed: $resp"; exit 1
  fi
  echo "logged in as $TB_USER"
}

fetch() { # fetch <url> <outfile>
  curl -sL -b "$COOKIE_JAR" -o "$2" "$1"
}

login

verify_zip() { # verify_zip <file> <label>
  if file "$1" | grep -q "Zip archive"; then
    echo "OK: $2 ($(du -h "$1" | cut -f1))"
  else
    echo "FAILED: $2 — got $(file -b "$1"), $(wc -c < "$1") bytes"
    echo "  (an HTML response means authentication did not take; check ~/.netrc or TB_USER)"
    return 1
  fi
}

case "${1:-}" in
  test)
    tmp=$(mktemp -d)
    echo "downloading $BASE/Biling/Gelman?f=zip ..."
    fetch "$BASE/Biling/Gelman?f=zip" "$tmp/Gelman.zip"
    verify_zip "$tmp/Gelman.zip" "Biling/Gelman"
    unzip -l "$tmp/Gelman.zip" | head -8
    rm -rf "$tmp"
    ;;
  list)
    col="${2:?usage: list <Collection>}"
    tmp=$(mktemp)
    fetch "$BASE/$col/" "$tmp"
    # corpus links appear as hrefs within the collection index
    grep -oE 'href="[^"]+"' "$tmp" | sed 's/href="//;s/"//' | sort -u
    rm -f "$tmp"
    ;;
  mirror)
    out="${2:?usage: mirror <outdir>}"
    mkdir -p "$out"
    # Collections can be nested (e.g. Chinese/Mandarin/<corpus>): try each
    # index entry as a corpus zip first; if that fails, recurse into it as a
    # subdirectory (up to depth 3).
    mirror_dir() { # mirror_dir <rel-path> <depth>
      local path="$1" depth="$2" tmp entries name dest
      [ "$depth" -gt 3 ] && return 0
      tmp=$(mktemp)
      if ! fetch "$BASE/$path/" "$tmp"; then
        echo "  index fetch failed for $path, skipping"; rm -f "$tmp"; return 0
      fi
      entries=$(grep -oE 'href="[^"?]+"' "$tmp" | sed 's/href="//;s/"//;s|/$||' \
        | grep "/data/$BANK/$path/" | awk -F/ 'NF{print $NF}' \
        | grep -vE '^(\.{1,2}|index)$' | sort -u || true)
      rm -f "$tmp"
      if [ -z "$entries" ]; then
        echo "  no entries under $path"; return 0
      fi
      mkdir -p "$out/$BANK/$path"
      for name in $entries; do
        dest="$out/$BANK/$path/$name.zip"
        if [ -s "$dest" ] && file "$dest" | grep -q Zip; then
          echo "  $path/$name: already have"; continue
        fi
        if fetch "$BASE/$path/$name?f=zip" "$dest" && file "$dest" | grep -q "Zip archive"; then
          echo "  OK: $path/$name ($(du -h "$dest" | cut -f1))"
        else
          rm -f "$dest"
          echo "  $path/$name: not a corpus zip, recursing"
          mirror_dir "$path/$name" $((depth + 1))
        fi
        sleep 2  # be polite to the server
      done
    }
    for col in "${COLLECTIONS[@]}"; do
      echo "=== $col ==="
      mirror_dir "$col" 1
    done
    echo "mirror complete: $(find "$out" -name '*.zip' | wc -l | tr -d ' ') zips"
    ;;
  *)
    echo "usage: $0 {test | list <Collection> | mirror <outdir>}"; exit 1;;
esac
