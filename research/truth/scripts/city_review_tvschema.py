"""Summarise Trafikverket's public API schema document. Usage: city_review_tvschema.py body objecttype [...]"""
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
print(type(d), list(d)[:10] if isinstance(d, dict) else len(d))
def walk(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, path+'/'+k)
        yield path, o
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from walk(v, path+'/'+str(i))
want = sys.argv[2:]
for path, o in walk(d):
    n = o.get('name') or o.get('Name') or o.get('objecttype') or o.get('ObjectType') if isinstance(o, dict) else None
    if n in want:
        print('=====', n, path)
        print(json.dumps(o, ensure_ascii=False)[:14000])
