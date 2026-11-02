# Downloads small TGSIM attachments (dictionaries, centerlines, boundaries) listed in saved Socrata metadata.
import json,glob,subprocess,sys,os,urllib.parse
meta,out=sys.argv[1],sys.argv[2]
os.makedirs(out,exist_ok=False)
want={'97n2-kuqi':'I395','7zjf-a4zf':'I294L1','tpsq-zrwa':'I294L2','9uas-hf8b':'I90stat','6a6e-vfvi':'I90mov','brzy-6zfh':'Foggy'}
for id,name in want.items():
    j=json.load(open(f'{meta}/{id}.json'))
    os.makedirs(f'{out}/{name}')
    for a in j['metadata']['attachments']:
        fn=a.get('filename') or a.get('name')
        if fn.endswith('.png') or fn.endswith('.zip') and 'Annotation' in fn and name not in('I395','Foggy'): continue
        u=f"https://data.transportation.gov/api/views/{id}/files/{a.get('assetId') or a.get('blobId')}?filename={urllib.parse.quote(fn)}"
        r=subprocess.run(['curl','-sS','-L','--fail','-m','120','-A','cars-research/1.0','-o',f'{out}/{name}/{fn}',u])
        print(name,fn,r.returncode,flush=True)
