#!/usr/bin/env bash
# name url lines in $1; saves pdf/html under validation-lit and converts to text. Downloads are never executed.
D=/home/erikf/projects/personal/cars-data/datasets/validation-lit
while read -r n u; do
  [ -z "$n" ] && continue
  [ -s "$D/$n.txt" ] && { echo "have $n"; continue; }
  curl -sSL -m 60 -A 'Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/120.0' -o "$D/$n.bin" "$u" || { echo "FAIL $n $u"; continue; }
  if head -c 5 "$D/$n.bin" | grep -q '%PDF'; then pdftotext -layout "$D/$n.bin" "$D/$n.txt" 2>/dev/null; else python3 -I -c "import re,sys,html;s=open(sys.argv[1],'rb').read().decode('utf8','ignore');s=re.sub(r'(?is)<(script|style).*?</\1>','',s);s=re.sub(r'<[^>]+>',' ',s);s=html.unescape(s);open(sys.argv[2],'w').write(re.sub(r'[ \t]+',' ',s))" "$D/$n.bin" "$D/$n.txt"; fi
  echo "$n $(wc -w < "$D/$n.txt") words $u"
done < "$1"
