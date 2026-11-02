# Extracts camera records from the saved trafiken.nu page into JSON. Input is untrusted HTML, parsed as text only.
import re,json,sys,collections
s=open(sys.argv[1],encoding='utf8',errors='replace').read()
i=s.find('imageUrl')
print(repr(s[max(0,i-600):i+500]))
s2=s.replace('\\u0022','"').replace('\\"','"')
ids=re.findall(r'"cameraId":"?([^",]+)',s2); urls=re.findall(r'"imageUrl":"([^"]*)"',s2); print(len(ids),len(urls),len(set(urls)))
print(urls[:5])
print(collections.Counter(re.sub(r'[0-9]+','N',u)[:70] for u in urls).most_common(8))
