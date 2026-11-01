"""List WFS layer names from saved capabilities. Usage: city_review_wfs.py capabilities.xml"""
import re, sys, pathlib
x = pathlib.Path(sys.argv[1]).read_bytes().decode('utf-8', 'replace')
for m in re.finditer(r'<(?:wfs:)?FeatureType>(.*?)</(?:wfs:)?FeatureType>', x, re.S):
    n = re.search(r'<(?:wfs:)?Name>(.*?)</', m.group(1)); t = re.search(r'<(?:wfs:)?Title>(.*?)</', m.group(1))
    print(n.group(1) if n else '?', '|', t.group(1) if t else '')
