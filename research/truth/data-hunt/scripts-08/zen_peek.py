import sys,pyarrow.parquet as pq,pyarrow.compute as pc
p=sys.argv[1];f=pq.ParquetFile(p);print('zen',p,f.metadata.num_rows,f.schema_arrow.names)
for r in f.read_row_group(0).slice(0,6).to_pylist(): print('zen',r)
P=pq.read_table(p);print('zen modes',pc.value_counts(P['mode']).to_pylist()[:8],'agents',pc.count_distinct(P['PId']))
t=pq.read_table(sys.argv[2],columns=['feasibility']);print('zen pop',t.num_rows,pc.value_counts(t['feasibility']).to_pylist())
