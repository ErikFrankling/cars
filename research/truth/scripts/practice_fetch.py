#!/usr/bin/env python3
"""Fetch sources for report 15. Input lines: slug url. Each goes into its own directory, is converted to text and logged."""
import concurrent.futures, hashlib, html.parser, json, pathlib, re, subprocess, sys, time

ROOT = pathlib.Path("/home/erikf/projects/personal/cars-data/truth/practice/opus-20261101")
LEDGER = pathlib.Path("/home/erikf/.t3/projects/cars/research/truth/15-fetch-ledger.jsonl")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


class Strip(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "br", "tr", "li", "div", "h1", "h2", "h3", "h4", "td", "th"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def fetch(slug, url):
    d = ROOT / slug
    d.mkdir(parents=True, exist_ok=True)
    raw = d / "raw"
    r = subprocess.run(["curl", "-sSL", "--max-time", "120", "--max-filesize", "150000000", "-A", UA,
                        "-H", "Accept: text/html,application/pdf,*/*", "-o", str(raw), "-w", "%{http_code} %{content_type} %{url_effective}", url],
                       capture_output=True, text=True)
    code, ctype, eff = (r.stdout.split(" ", 2) + ["", "", ""])[:3]
    rec = {"slug": slug, "url": url, "http": code, "ctype": ctype, "final": eff, "err": r.stderr.strip()[:200], "date": time.strftime("%Y-%m-%d")}
    if raw.exists() and raw.stat().st_size:
        b = raw.read_bytes()
        rec["bytes"], rec["sha256"] = len(b), hashlib.sha256(b).hexdigest()
        txt = d / "text.txt"
        if b[:5] == b"%PDF-":
            subprocess.run(["pdftotext", "-layout", str(raw), str(txt)], capture_output=True, timeout=300)
            rec["pdf_pages"] = (txt.read_text(errors="ignore").count("\f") if txt.exists() else 0)
        else:
            s = Strip()
            try:
                s.feed(b.decode("utf-8", "ignore"))
                t = re.sub(r"\n\s*\n+", "\n", "".join(s.out))
                txt.write_text(t)
            except Exception as e:
                rec["parse_err"] = str(e)[:100]
        rec["text_chars"] = len(txt.read_text(errors="ignore")) if txt.exists() else 0
    return rec


def main():
    items = [l.split(None, 1) for l in sys.stdin.read().splitlines() if l.strip() and not l.startswith("#")]
    with concurrent.futures.ThreadPoolExecutor(5) as ex, LEDGER.open("a") as f:
        for rec in ex.map(lambda it: fetch(it[0], it[1].strip()), items):
            f.write(json.dumps(rec) + "\n")
            print(rec["slug"], rec["http"], rec.get("bytes"), rec.get("pdf_pages", "-"), rec.get("text_chars"), rec["ctype"][:20], rec["err"][:50])


main()
