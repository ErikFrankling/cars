#!/usr/bin/env bash
# usage: fetch.sh name url  -> downloads pdf, converts to text, logs to ledger. Nothing downloaded is executed.
PATH=/nix/store/54diyf6hv77hggdpd0wqw3yi9c4ac8yr-poppler-utils-26.09.0/bin:$PATH
D=/home/erikf/projects/personal/cars-data/truth/practice/matchreal-20261102
L=/home/erikf/.t3/projects/cars/research/truth/data-hunt/15-fetch-ledger.tsv
n="$1"; u="$2"
code=$(curl -sS -L -m 90 --max-filesize 60000000 -A "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0" -o "$D/pdf/$n.pdf" -w '%{http_code}' "$u")
if head -c 5 "$D/pdf/$n.pdf" 2>/dev/null | grep -q '%PDF'; then
  pdftotext -layout "$D/pdf/$n.pdf" "$D/txt/$n.txt" 2>/dev/null
  p=$(pdfinfo "$D/pdf/$n.pdf" 2>/dev/null | awk '/^Pages/{print $2}')
  w=$(wc -w < "$D/txt/$n.txt")
  s=$(sha256sum "$D/pdf/$n.pdf" | cut -c1-16)
  echo -e "$(date -Is)\t$n\t$code\tpdf\t$p pages\t$w words\t$s\t$u" >> "$L"
  echo "$n OK $code $p pages $w words"
else
  echo -e "$(date -Is)\t$n\t$code\tNOTPDF\t\t\t\t$u" >> "$L"
  echo "$n FAILED code=$code (not a PDF)"
fi
