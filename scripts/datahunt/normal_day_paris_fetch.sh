B="https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records"
Q(){ curl -sS --max-time 150 -G "$B" --data-urlencode "select=$1" --data-urlencode "group_by=$2" --data-urlencode "limit=$3" --data-urlencode "where=$4" -o "$5"; }
W="t_1h>='2025-11-03T00:00:00' and t_1h<'2025-11-29T00:00:00' and q is not null and k is not null"
Q "date_format(t_1h,'yyyy-MM-dd HH') as t,sum(q) as q,avg(k) as k,avg(q) as qm,count(*) as n" "date_format(t_1h,'yyyy-MM-dd HH')" 1000 "$W" research/truth/data-hunt/14-data/paris_hours.json
Q "date_format(t_1h,'HH') as h,etat_trafic as e,count(*) as n" "date_format(t_1h,'HH'),etat_trafic" 300 "$W" research/truth/data-hunt/14-data/paris_states.json
Q "date_format(t_1h,'yyyy-MM-dd') as d,sum(q) as q,count(*) as n" "date_format(t_1h,'yyyy-MM-dd')" 100 "t_1h>='2025-10-01T00:00:00' and t_1h<'2026-07-01T00:00:00' and q is not null" research/truth/data-hunt/14-data/paris_days.json
