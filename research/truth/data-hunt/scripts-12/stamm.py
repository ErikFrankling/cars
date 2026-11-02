# Reads the Berlin detector master xlsx (zip of XML) with stdlib and tests whether v6.4 count ids match it.
import zipfile,re,sys,gzip,collections
z=zipfile.ZipFile(sys.argv[1]); print(z.namelist()[:8])
ss=[re.sub(r'<[^>]+>','',m) for m in re.findall(r'<si>(.*?)</si>',z.read('xl/sharedStrings.xml').decode('utf8'),re.S)]
sh=z.read('xl/worksheets/sheet1.xml').decode('utf8')
rows=[]
for r in re.findall(r'<row [^>]*>(.*?)</row>',sh,re.S):
    row={}
    for ref,attrs,v in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<f>.*?</f>)?<v>(.*?)</v>',r,re.S):
        row[ref]=ss[int(v)] if 't="s"' in attrs else v
    rows.append(row)
print('rows',len(rows)); 
for r in rows[:4]: print(r)
xml=gzip.open(sys.argv[2],'rt',encoding='utf8').read()
locs=re.findall(r'<location refId="([^"]+)" name="([^"]+)"',xml)
ids={re.match(r'\d+',n).group(0) for _,n in locs}
vals=collections.defaultdict(set)
for r in rows[1:]:
    for k,v in r.items(): vals[k].add(str(v))
for k,v in vals.items():
    print(k,rows[0].get(k),len(v),'overlap with count ids',len(v&ids), 'sample',sorted(v)[:2])
