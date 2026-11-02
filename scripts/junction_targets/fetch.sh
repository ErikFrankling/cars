#!/usr/bin/env bash
# Report 25 downloads. One new folder per dataset, inert files only, nothing is executed. Resumable.
# Helsinki, Songdo and Pully stay out on purpose: they are locked (bench splits/locked.toml, report 22 section 9).
set -u
R=/home/erikf/projects/personal/cars-data/datasets
get() { d=$1; u=$2; n=${3:-$(basename "$u")}; mkdir -p "$d"; curl -sS -L -C - --retry 3 --retry-delay 10 -m 7200 -o "$d/$n" "$u" || echo "FAILED $u" >&2; echo "$(date +%T) $d/$n $(stat -c %s "$d/$n")"; }
for w in "$@"; do case $w in
  opendd) for i in 1 5 6 7 2 3 4; do get $R/jt25-opendd https://data.l3pilot.eu/OpenDD/opendd_v3-rdb$i.zip; done;;
esac; done
