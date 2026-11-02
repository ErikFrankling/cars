#!/usr/bin/env bash
# probe.sh <dataset> <name> <url> [maxbytes]: capped anonymous GET, saved under a per-dataset folder, logged.
d=/home/erikf/projects/personal/cars-data/datasets/$1; mkdir -p "$d"
out="$d/$2"; max=${4:-3000000}
code=$(curl -sS -L --compressed -m 60 --range 0-$((max-1)) -A 'Mozilla/5.0 (X11; Linux x86_64)' -o "$out" -w '%{http_code} %{content_type} %{size_download}' "$3" 2>&1)
sha=$(sha256sum "$out" 2>/dev/null | cut -c1-16)
echo "$1/$2 | $3 | $code | sha $sha"
echo "$(date -u +%FT%TZ) | $1/$2 | $3 | $code | sha $sha" >> /home/erikf/.t3/projects/cars/research/truth/data-hunt/scripts-12/fetch-log.txt
