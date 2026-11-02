SET memory_limit='1500MB'; SET threads=3;
INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';
COPY (SELECT id, geometry, class, subclass, subclass_rules, access_restrictions, speed_limits, prohibited_transitions, road_flags, road_surface, level_rules, width_rules, destinations, connectors, names, routes, sources, version
 FROM read_parquet('s3://overturemaps-us-west-2/release/2026-10-21.0/theme=transportation/type=segment/*', hive_partitioning=1)
 WHERE bbox.xmin>17.95 AND bbox.xmax<18.15 AND bbox.ymin>59.28 AND bbox.ymax<59.38 AND subtype='road')
TO '/home/erikf/projects/personal/cars-data/datasets/overture-2026-10-21/stockholm_segments.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
