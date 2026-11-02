import os,sys,tempfile,json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
t=tempfile.mkdtemp(); os.environ['BENCH_APPROVALS']=t+'/a.tsv'; os.environ['BENCH_HOME']=t
import reveal,pathlib
reveal.LEDGER=pathlib.Path(t)/'ledger.tsv'
def expect(fn,*a,**k):
    try: fn(*a,**k); print('NO REFUSAL',fn.__name__); return False
    except SystemExit as e: print('refused:',str(e)[:90]); return True
ok=expect(reveal.reveal,'berlin-2019-03','because','run'); 
ok&=expect(reveal.approve,'berlin-2019-03','because')
for k in reveal.AGENT_ENV: os.environ.pop(k,None)
ok&=expect(reveal.approve,'berlin-2019-03','because',stdin=lambda:'yes',tty=True)
reveal.approve('berlin-2019-03','because',stdin=lambda:'berlin-2019-03',tty=True)
import bench
bench.RES=pathlib.Path(t)/'r'; bench.RES.mkdir()
(bench.RES/'run.json').write_text(json.dumps(dict(run_id='run',commit='c',config_hash='h')))
ok&=expect(reveal.reveal,'berlin-2019-03','because','run')
sc=lambda n,r:{'1':dict(status='FAIL',z=3.62)}
l=reveal.reveal('berlin-2019-03','because','run',scorer=sc)
ok&=expect(reveal.reveal,'berlin-2019-03','because','run',scorer=sc)
for i in range(4):
    reveal.approve('berlin-2019-03',f'r{i}',stdin=lambda:'berlin-2019-03',tty=True); reveal.reveal('berlin-2019-03',f'r{i}','run',scorer=sc)
reveal.approve('berlin-2019-03','six',stdin=lambda:'berlin-2019-03',tty=True)
ok&=expect(reveal.reveal,'berlin-2019-03','six','run',scorer=sc)
print('LEDGER lines',len(reveal.LEDGER.read_text().splitlines()),'all as expected',ok)
