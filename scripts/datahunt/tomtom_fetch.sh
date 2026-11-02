#!/usr/bin/env bash
# Fetch TomTom Traffic Index city pages one at a time and keep only the extracted summary.
# Usage (from the repo root, on the homelab): heavy --small -- scripts/datahunt/tomtom_fetch.sh KEYS.txt ROWS.jsonl
# Appends, so a dropped connection loses nothing already written.
set -u
KEYS=$1
ROWS=$2
S=scripts/datahunt/tomtom_index_extract.py
T=$(mktemp -d)
wc -l "$KEYS"
while read -r k; do
  if curl -sS -L --max-time 40 -A "Mozilla/5.0" -o "$T/p.html" "https://www.tomtom.com/traffic-index/city/$k/"; then
    python3 -I "$S" one "$T/p.html" "$k" >> "$ROWS" || echo "parse failed $k"
  else
    echo "fetch failed $k"
  fi
  sleep 1
done < "$KEYS"
rm -rf "$T"
wc -l "$ROWS"
