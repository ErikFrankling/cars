import importlib.util,tempfile,pathlib,numpy as np
spec=importlib.util.spec_from_file_location('bd','scripts/berlin_detectors.py'); b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
assert np.allclose(b.geh(np.array([0.,100.]),np.array([0.,100.])),[0,0])
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t)/'edge.xml'; p.write_text('<meandata>'+''.join(f'<interval begin="{q}" end="{q+900}"><edge id="a" entered="2"/></interval>' for q in range(0,3600,900))+'<interval begin="3600" end="4500"><edge id="a" entered="999"/>')
 d=b.sumo_counts(p,{'a','b'}); assert len(d)==2; assert d.set_index('edge').loc['a','SUMO']==8; assert d.set_index('edge').loc['b','SUMO']==0
print('GEH zero handling, complete quarters, sparse zero and truncated-tail checks passed')
