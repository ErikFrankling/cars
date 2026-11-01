"""Print readable text of saved untrusted HTML bodies. Usage: city_review_text.py file [regex [context_chars]]"""
import html, re, sys, pathlib
raw = pathlib.Path(sys.argv[1]).read_bytes().decode('utf-8', 'replace')
raw = re.sub(r'(?is)<(script|style|svg|nav|footer)\b.*?</\1>', ' ', raw)
raw = re.sub(r'(?is)<a\s[^>]*href="([^"]+)"[^>]*>', lambda m: ' [' + m.group(1) + '] ', raw)
t = html.unescape(re.sub(r'(?s)<[^>]+>', ' ', raw))
t = re.sub(r'[ \t\r\f]+', ' ', t); t = re.sub(r'\n\s*', '\n', t)
if len(sys.argv) > 2:
    c = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    for m in re.finditer(sys.argv[2], t, re.I):
        print('...', t[max(0, m.start()-c):m.end()+c].replace('\n', ' '), '...\n')
else:
    print(t)
