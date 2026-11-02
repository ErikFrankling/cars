"""Keep a random share of the vehicles. usage: sthlm_thin.py SRC DST SHARE [SEED]"""
import gzip,random,sys
src,dst,share=sys.argv[1],sys.argv[2],float(sys.argv[3]);r=random.Random(int(sys.argv[4]) if len(sys.argv)>4 else 11);n=k=0
with gzip.open(src,'rt') as f,gzip.open(dst,'wt',compresslevel=3) as w:
    for l in f:
        if l.startswith('<vehicle'):
            n+=1
            if r.random()>=share: continue
            k+=1
        w.write(l)
print(k,'of',n)
