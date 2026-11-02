"""Locked data. A reveal needs a written reason and an approval only Erik can give at his own keyboard. At most 5 per set,
every one in the ledger, and it prints only levels and rounded z. See report 22, section 9."""
import datetime
import hashlib
import json
import os
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / 'ledger.tsv'
APPROVALS = Path(os.environ.get('BENCH_APPROVALS', Path.home() / '.local/share/cars-bench/approvals.tsv'))
ETA = .25
MAX_REVEALS = 5
AGENT_ENV = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'T3CODE_THREAD_ID', 'T3CODE_HOME', 'CODEX_SANDBOX', 'CURSOR_AGENT', 'AGENT_JOB_ID')


def locked_sets():
    return tomllib.loads((HERE / 'splits/locked.toml').read_text())['set']


def token(name, reason):
    return hashlib.sha256(f'{name}\t{reason}'.encode()).hexdigest()[:16]


def approve(name, reason, stdin=None, tty=None):
    """Erik's own act: a real terminal, no agent environment, and the set's name typed back."""
    tty = sys.stdin.isatty() if tty is None else tty
    if not tty or any(k in os.environ for k in AGENT_ENV):
        raise SystemExit('approve is for Erik at a terminal: this session looks like an agent or has no terminal. Nothing approved.')
    if name not in locked_sets():
        raise SystemExit(f'unknown set {name}')
    print(f'Set: {name}\nReason: {reason}\nThis spends one of its {MAX_REVEALS} reveals. Type the set name to approve:')
    if (stdin or input)().strip() != name:
        raise SystemExit('Not approved.')
    APPROVALS.parent.mkdir(parents=True, exist_ok=True)
    with open(APPROVALS, 'a') as f:
        f.write(f'{token(name, reason)}\t{name}\t{datetime.datetime.now().isoformat(timespec="seconds")}\t{reason}\n')
    os.chmod(APPROVALS, 0o600)
    print('Approved. An agent may now run: bench.py reveal --locked', name, '--reason', repr(reason), '--run RUN')


def ledger_rows():
    if not LEDGER.exists():
        return []
    return [dict(zip(('date', 'set', 'run', 'commit', 'config', 'token', 'reason'), l.split('\t'))) for l in LEDGER.read_text().splitlines()[1:] if l]


def reveal(name, reason, run_id, scorer=None):
    sets = locked_sets()
    if name not in sets:
        raise SystemExit(f'unknown set {name}; known: {", ".join(sets)}')
    if not reason.strip():
        raise SystemExit('a reveal needs a written reason')
    tok = token(name, reason)
    approved = APPROVALS.exists() and any(l.split('\t')[0] == tok for l in APPROVALS.read_text().splitlines())
    if not approved:
        raise SystemExit(f'not approved. Erik must run, at his own terminal: bench.py approve --locked {name} --reason {reason!r}')
    used = [r for r in ledger_rows() if r['set'] == name]
    if len(used) >= MAX_REVEALS:
        raise SystemExit(f'{name} is spent: {len(used)} reveals. It joins the tuning data; open a new month.')
    if any(r['token'] == tok for r in used):
        raise SystemExit('this approval is already used')
    import bench
    res = bench.load(run_id)
    if scorer is None:
        s = sets[name]
        raise SystemExit(f"approved, but set {name} ({s.get('source', '')}) has no scorer yet. Nothing was opened and nothing spent.")
    levels = scorer(name, res)
    if not LEDGER.exists():
        LEDGER.write_text('date\tset\trun\tcommit\tconfig\ttoken\treason\n')
    with open(LEDGER, 'a') as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\t{name}\t{res['run_id']}\t{res['commit']}\t{res['config_hash']}\t{tok}\t{reason}\n")
    for lv, x in levels.items():
        z = None if x.get('z') is None else round(x['z'] / ETA) * ETA
        print(f"level {lv}: {x['status']}  worst z about {z}")
    return levels
