#!/usr/bin/env bash
# fetch.sh NAME URL : one new empty directory per download, then pdftotext. Ledger in papers/ledger.tsv
P=$(command -v pdftotext)
ROOT=/home/erikf/projects/personal/cars-data/truth/merging-20261102/papers
n=$1; u=$2; d=$ROOT/$n; mkdir -p "$d"
code=$(curl -sS -L -m 60 -A 'Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0' -o "$d/raw" -w '%{http_code}' "$u" 2>/dev/null)
sz=$(stat -c %s "$d/raw" 2>/dev/null); m=$(head -c4 "$d/raw" 2>/dev/null)
if [ "$m" = "%PDF" ]; then "$P" -layout "$d/raw" "$d/t.txt" 2>/dev/null; t=pdf; else cp "$d/raw" "$d/t.txt" 2>/dev/null; t=other; fi
w=$(wc -w < "$d/t.txt" 2>/dev/null)
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$n" "$code" "$t" "$sz" "$w" "$u" | tee -a "$ROOT/ledger.tsv"
