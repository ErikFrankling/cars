#!/usr/bin/env python3
"""Builds the big report at cars-data/report/index.html. Re-run after new results.

Numbers come from research reports and run outputs, collected with sources in cars-data/report/facts/.
"""
import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assets import CSS, JS

ROOT = Path(__file__).resolve().parents[2]
DATA = Path('/home/erikf/projects/personal/cars-data')
OUT = DATA / 'report'
VIDEOS = {v['slug']: v for v in json.load(open(OUT / 'facts/videos.json'))}
PHONE = {'berlin_day': 'phone/berlin_day.mp4', 'berlin_zoom': 'phone/berlin_zoom.mp4', 'stockholm_day': 'phone/stockholm_day.mp4',
         'render-samples__bologna': 'phone/bologna.mp4', 'render-samples__ring': 'phone/ring.mp4'}
SKIP = {'berlin_wait', 'one_av_damped', 'one_av_human', 'tmp__hu__gal__courtesy_i80_0', 'tmp__hu__gal__courtesy_i80_1'}
FACT = DATA / 'truth/stockholm/factorial'
METRICS = {r['name']: r for r in (json.loads(l) for l in open(FACT / 'metrics.jsonl') if l.strip())}
NEW_DAY = DATA / 'videos/stockholm_recipe_day.mp4'
if NEW_DAY.exists() and (OUT / 'posters/stockholm_recipe_day.jpg').exists():
    VIDEOS['stockholm_recipe_day'] = dict(path=str(NEW_DAY), slug='stockholm_recipe_day', width=1920, height=1080, title='Stockholm after the fix, one day', caption='Replacement trips at 60% with route feedback.', kind='city', quality='good')
    PHONE['stockholm_recipe_day'] = 'phone/stockholm_recipe_day.mp4'
used = set()
chapters = []
figs_all = []
esc = html.escape


def lamp(k):
    return f'<span class="lamp {k}"><i></i><i></i><i></i></span>'


LEVEL = {'g': 'Checked against the real world', 'a': 'Simulation only', 'r': 'Failed or not done', 'l': 'Published research'}


def fact(level, text, tag=''):
    icon = '<span class="bk"></span>' if level == 'l' else lamp(level)
    t = f' <span class="tag">{esc(tag)}</span>' if tag else ''
    return f'<li>{icon}<span class="sr">{LEVEL[level]}: </span><div>{text}{t}</div></li>'


def facts(*items):
    return '<ul class="facts">' + ''.join(fact(*i) for i in items) + '</ul>'


def head(title, dest):
    n = len(chapters) + 1
    i = f'x{n}'
    chapters.append((i, n, title))
    return f'<header class="gantry" id="{i}" data-t="{esc(title)}"><div class="sign"><div class="sign-in"><span class="exit">Exit {n}</span><h2>{esc(title)}</h2><p class="dest">{esc(dest)}</p></div></div></header>'


def stats(*rows):
    return '<div class="stats">' + ''.join(f'<div class="stat"><b>{a}</b><span>{b}</span></div>' for a, b in rows) + '</div>'


def vs(a, atxt, b, btxt):
    return f'<div class="vs"><div><b>{a}</b><span>{atxt}</span></div><div><b>{b}</b><span>{btxt}</span></div></div>'


def note(title, text, bad=False):
    return f'<div class="note{" bad" if bad else ""}"><b>{esc(title)}</b>{text}</div>'


def chart(title, sub, t, x, series, **kw):
    spec = dict(title=title, t=t, x=x, s=[dict(n=n, c=c, v=v, **({'d': 1} if c == 'real' and t == 'lines' and False else {})) for n, c, v in series], **kw)
    legend = ''
    if len(series) > 1:
        legend = '<div class="legend">' + ''.join(f'<span><i style="background:var(--{c})"></i>{esc(n)}</span>' for n, c, _ in series) + '</div>'
    rows = ''.join('<tr><td>' + esc(str(xv).replace('|', ' ')) + '</td>' + ''.join(f'<td>{"none" if s[2][i] is None else (f"{s[2][i]:,}" if isinstance(s[2][i], (int, float)) else esc(s[2][i]))}</td>' for s in series) + '</tr>' for i, xv in enumerate(x))
    hdr = '<tr><th></th>' + ''.join(f'<th>{esc(s[0])}</th>' for s in series) + '</tr>'
    payload = esc(json.dumps(spec), quote=True)
    sub_h = f'<div class="cs">{sub}</div>' if sub else ''
    return (f'<div class="chart" data-spec="{payload}"><div class="ct">{esc(title)}</div>{sub_h}{legend}<div class="plot"></div><div class="tip"></div>'
            f'<details class="nums"><summary>Show the numbers</summary><div class="tbl"><table>{hdr}{rows}</table></div></details></div>')


def table(headers, rows, wide=()):
    h = ''.join(f'<th{" class=w" if i in wide else ""}>{esc(c)}</th>' for i, c in enumerate(headers))
    b = ''.join('<tr>' + ''.join(f'<td{" class=w" if i in wide else ""}>{c}</td>' for i, c in enumerate(r)) + '</tr>' for r in rows)
    return f'<div class="tbl"><table><tr>{h}</tr>{b}</table></div>'


def media(slug):
    v = VIDEOS[slug]
    if slug in PHONE:
        return PHONE[slug]
    rel = Path(v['path']).relative_to(DATA / 'videos')
    return 'media/' + str(rel)


def clip(slug, title=None, cap=None, data_k=None):
    v = VIDEOS[slug]
    used.add(slug)
    ar = f"{v['width']}/{v['height']}"
    k = f' data-k="{data_k}"' if data_k else ''
    title = title or v['title']
    cap = cap if cap is not None else v['caption']
    return (f'<div class="clip"{k}><button class="frame" data-ar="{ar}" data-src="{media(slug)}" data-poster="posters/{slug}.jpg" aria-label="Play {esc(title)}">'
            f'<img loading="lazy" src="posters/{slug}.jpg" alt="" style="aspect-ratio:{ar}"><span class="play"></span></button>'
            f'<div class="ti">{esc(title)}</div><div class="ca">{esc(cap)}</div></div>')


def clips(*items):
    return '<div class="clips2">' + ''.join(clip(*i) if isinstance(i, tuple) else clip(i) for i in items) + '</div>'


def dims(path):
    with open(path, 'rb') as f:
        h = f.read(24)
    return f'width="{int.from_bytes(h[16:20], "big")}" height="{int.from_bytes(h[20:24], "big")}"'


def fig(src, cap):
    p = ROOT / src if not src.startswith('/') else Path(src)
    name = src.replace('/', '__').lstrip('_')
    dst = OUT / 'figures' / name
    if p.exists():
        shutil.copy2(p, dst)
    else:
        print('missing figure', src)
    figs_all.append((name, cap))
    return f'<figure><img loading="lazy" src="figures/{name}" {dims(dst)} alt="{esc(cap)}"><figcaption>{esc(cap)}</figcaption></figure>'


# ---------------------------------------------------------------- chapters
B = []

B.append('<div class="page">')
B.append('<p class="answer" style="margin-top:2.2rem">This is everything built and tested so far. Each claim carries a traffic light, so you can see at a glance how much it is worth.</p>')
B.append(f'''<div class="key">
<div>{lamp('g')}<span><b>Green:</b> checked against measurements of real cars, real roads or real counts.</span></div>
<div>{lamp('a')}<span><b>Amber:</b> works in simulation. Checked against another model or theory, not real traffic.</span></div>
<div>{lamp('r')}<span><b>Red:</b> failed, or not done yet.</span></div>
<div><span class="facts"><span class="bk" style="display:block;margin:0 0 0 1px"></span></span><span style="margin-left:2px"><b>Book:</b> what published research says, not our own result.</span></div>
</div>''')
B.append('</div>')

B.append('<div class="page">')
B.append(head('The verdict', 'What is proven, what is only simulated, what is broken'))
B.append('<p class="answer">The engine is real and fast, the driver is measurably better than the old ones, and the no-traffic-light junction beats a good signal in clean tests. A real city is not reproduced yet. That is the big open problem.</p>')
B.append('</div>')
B.append('<div class="boardwrap"><div class="page" style="max-width:none"><div class="board">')
B.append(f'''<section class="panel g"><div class="head">{lamp('g')}<h3>Proven against reality</h3></div><ul>
<li><b>A driver model that predicts real drivers better than its calibrated rivals</b>, clearly in four of five test sets. 9 to 26% better than a fully calibrated Krauss model on tracks it never saw, and 17% better on German motorway data when trained only on US data. In Python, and the GPU version matches within 1%.</li>
<li><b>The GPU version comes close to real traffic on the road.</b> Waves travel backwards at 34.4 km/h against a real 33.7. Lane changes take 4.8 to 5.1 s against a real 5.05 to 5.6. Not merged yet, and some constants were chosen on the same data.</li>
<li><b>Real data exposed the famous test scenarios.</b> The public Berlin scenario carries 0.576 of the traffic measured at 93 sites. 46% of Stockholm's old trips contain an immediate U-turn.</li>
<li><b>Drivers really do let you in.</b> On I-80, 610 of 610 cars merged from a lane that ended, with a median wait of 22.6 s.</li></ul></section>''')
B.append(f'''<section class="panel a"><div class="head">{lamp('a')}<h3>Works in simulation</h3></div><ul>
<li><b>Speed.</b> A whole day of the public Berlin scenario, 2.25 million trips, in 147.5 s. One Berlin hour runs 5.4 million car updates per second against SUMO's 0.17 on the same PC, and many copies in one GPU world reach 58 million.</li>
<li><b>Junctions with no lights.</b> 5,679 cars per hour against 3,888 for a traffic light with the same self-driving cars, one lane each way, straight on. With 2 lanes and 20% turns at 5,200 cars per hour: 4.1 s delay against 20.2 s, and 0.01 stops per car against 0.96.</li>
<li><b>Stockholm no longer locks up, at 60% demand.</b> 2,449 teleports over a full day against 290,352, and 43 km/h against 9. It carries 60% of the real toll-ring traffic and some real signals are deleted, so it isn't validated Stockholm.</li>
<li><b>No more late braking at one junction.</b> Hard brakes fall from 2,688 to 8 per run at 5,200 cars per hour, and cars over 3 m/s² from 92% to 1%, with the same flow and delay.</li>
<li><b>Safety with failing radios.</b> No contacts at a single junction at any message loss, up to 100%. Lost messages only cost time.</li>
<li><b>The safety rule.</b> 0 contacts in 503,333 attack cases, in a one-dimensional Python test.</li>
<li><b>A real neural network drives.</b> One trained car removes a stop-and-go wave: 2,049 cars per hour against 1,743, in Python. The same weights give the same flow in GPU code. A simple formula still does slightly better, at 2,097.</li></ul></section>''')
B.append(f'''<section class="panel r"><div class="head">{lamp('r')}<h3>Not working yet</h3></div><ul>
<li><b>Stockholm doesn't match its real sensors.</b> 77.3% error at sensors the model was never fitted to, where the year-to-year noise is 12.4%. It carries about a third of the real flow there. No calibrated test has finished.</li>
<li><b>Full real traffic still locks Stockholm up.</b> 70,595 teleports by 10:00, and 150,956 on the map closest to the real signal register.</li>
<li><b>No lights in a real district isn\'t ready at full demand.</b> On the new demand it\'s better or level at 30 to 60%, but up to 18% worse than generated signals at 100%, and the planned version up to 41% worse. Only 50 of 199 junctions are coordinated.</li>
<li><b>Overloaded grid.</b> Planning across junctions cuts contacts from 265 to 3 in 42 runs, not to zero. The zero-collision rule still fails there.</li>
<li><b>New drivers and physics in a city.</b> With teleports off, the human driver still locks up on the fixed Stockholm demand: 114,298 of 167,295 cars stuck by 10:00. Neither is merged yet.</li>
<li><b>Not done.</b> Most self-driving tiers have only smoke tests. D9 and M4 aren't built. The "remove humans step by step" experiment hasn't been run.</li></ul></section>''')
B.append('</div></div></div>')
B.append('<div class="page">')
B.append(clip('gallery__d8__versus_signal', 'Best single clip: three ways to run one junction', 'Same junction, same arrivals. Left: no signal. Middle: a traffic light with the same self-driving cars. Right: a traffic light with human-like cars. At one moment in this run: 56 cars at 49 km/h, 81 at 29 km/h, 193 at 10 km/h. Simulated, no real vehicles.'))
B.append(note('Read this before the numbers', 'Almost everything after the speed chapter sits on branches not merged into main yet, and agents are still running, so unfinished numbers can move. This is a snapshot from 1 November 2026, about 01:30 on 2 November.'))

# ---- Speed
B.append(head('How fast is it?', 'Every car in a city, on one graphics card'))
B.append('<p class="answer">Very fast on big jobs. Not magic on small ones. A full day of the public Berlin scenario takes about two and a half minutes.</p>')
B.append(stats(('147.5 s', 'one Berlin day: 2,248,884 trips, up to 38,439 cars on the road'), ('340.6 s', '1,134 complete simulation runs, the entire thesis sweep'), ('58.2 M', 'car updates per second, at 414,519 cars'), ('< 2 ms', 'per simulation step on Berlin')))
B.append(clip('berlin_day', 'The Berlin scenario, one working day', None))
B.append(chart('Same PC: car updates per second, in millions', 'The GPU loses on tiny jobs and pulls away as the network grows.', 'bars',
               ['Ring|200 cars', 'I-80', 'Bologna', 'Charlotten-|burg', 'Berlin|1 hour'],
               [('SUMO, 1 thread', 'old', [0.84, 0.46, 0.50, 0.35, 0.17]), ('SUMO, 4 threads', 'alt', [1.32, 0.54, 0.65, 0.52, None]), ('cars, GPU', 'ours', [0.50, 0.60, 0.80, 1.10, 5.40])]))
B.append(chart('More cars means more throughput, up to about 400,000', 'Copies of Bologna in one GPU world. Million updates per second against cars in the world.', 'lines',
               [811, 3242, 12976, 51952, 207223, 414519, 829214], [('cars, GPU', 'ours', [0.8, 2.5, 8.1, 25.1, 50.8, 58.2, 56.3])], xn=True, xlog=True, log=True, xl='cars in the world', xu='cars'))
B.append(facts(
    ('a', 'Berlin runs roughly 480 to 1,700 times faster than real time, depending on the hour.', 'read off a chart'),
    ('a', 'First hour of Berlin, same PC: 19.44 s against SUMO\'s 164.0 s in total, or 4.93 s against 157.26 s once running. That is 8.4 times or 32 times.'),
    ('a', 'A small single job is slower on the GPU: a ring of 200 cars takes 2.35 s against SUMO\'s 1.56 s.'),
    ('r', 'Speed of the new physics mode in normal traffic is unmeasured, because the only runs so far are dominated by gridlock (3.2 to 5.9 million updates per second).'),
))
B.append(note('Corrected from what I told you before', 'The old report said "35×" for Berlin\'s first hour. The bench file gives 8.4× in total, or 32× once running. "100 times or more" holds only for big sweeps. SUMO\'s "8.2 h" sweep time has no timing log and looks extrapolated. The "about 7 h" for a Berlin day is a published figure from another machine. So treat the 170× as a rough figure, not a measurement.'))
B.append(table(['Whole job', 'SUMO', 'cars'], [['Bologna sweep', '6.4 h (not logged)', '195 s'], ['I-80 sweep', '58 min (not logged)', '69 s'], ['Ring sweep', '40 min (not logged)', '50 s'], ['Two signal sweep', '7.5 min (not logged)', '26 s'], ['Berlin first hour', '164 s', '19.4 s'], ['Berlin day', 'about 7 h (published, other machine)', '148 s']]))
B.append('<h4>Rendering costs the simulation nothing</h4><p>You asked for this directly. Pictures are drawn afterwards from a recorded file with <code>cars replay</code>, with no simulation running, and a normal run draws nothing. Recording only costs when you ask for it: tracing all 7,200 steps of Charlottenburg takes 12.2 s instead of 9.6 s. Half an hour of Stockholm with its last 600 steps traced takes 3.24 s instead of 3.00 s. A 600 s window costs 0.2 s.</p>')
B.append(clip('berlin_zoom', 'From the whole city down to one roundabout', None))
B.append(clips('stockholm_slussen', 'bologna_rush', 'render-samples__bologna', 'render-samples__ring'))

# ---- Trust
B.append(head('Can you trust any traffic simulator?', 'What the field knows about itself'))
B.append('<p class="answer">Less than the industry implies. Models get flows roughly right and queues badly wrong, and even reality barely passes the trade\'s own test.</p>')
B.append(vs('88%', 'of hours where a real Berlin detector passes the fit test against itself a week earlier', '16%', 'of hours where the simulated Berlin passes against the same real detectors'))
B.append(chart('Stockholm 2006 toll: predicted traffic reduction against what happened, %', 'A static model, not microsimulation. Flows came out fairly close.', 'bars', ['Toll ring', 'Morning in', 'Evening in', 'Off-peak in'], [('Predicted', 'old', [16, 16, 18, 14]), ('Actual', 'real', [20, 19, 22, 24])]))
B.append(vs('19%', 'predicted cut in delay on one queue route', '94%', 'actual cut. Queues were what the model missed.'))
B.append(facts(
    ('l', 'Road forecasts: of 183 projects, half were off by over ±20% and a quarter by over ±40%. Across 1,291 projects the mean error was 17.3%.'),
    ('l', 'No audited sample of microsimulation forecasts checked after opening was found: "plausible for flows and unproven for queues".'),
    ('l', 'Driver models typically miss individual trajectories by 15 to 30%. Drivers differ from each other by more than models do.'),
    ('l', 'Teleporting isn\'t universal, and no guideline gives an accepted percentage. SUMO teleports, Vissim removes waiting cars, Aimsun lets cars miss turns, MATSim pushes through. All treat stuck cars as a modelling fault.'),
    ('l', 'Simulators aren\'t crash-free, and simulated conflicts predict real crashes worse than traffic volume does: R² 0.41 against 0.68. So we report no crash-rate claims.'),
    ('g', 'Real detectors against themselves one week apart: 88.5% of lanes pass, 28% of detectors miss the 85% bar, and the median difference is 8.7% per lane.'),
    ('a', 'I audited our own design choices against the literature: 47 decisions, 14 established, 20 adapted, 13 invented. The invented ones are flagged in the reports.'),
))

# ---- Drivers
B.append(head('Real human drivers', 'Measured from about 36,000 real manoeuvres, then rebuilt'))
B.append('<p class="answer">We measured real drivers, then ran a tournament on tracks the models had never seen. The chosen model came out best in every set, clearly in four of five.</p>')
B.append(chart('Predicting real drivers: error in the gap after 30 s, metres', 'Lower is better. Python prototype. Held-out real tracks from five sets, the last from Germany. Calibrated means fitted to data.', 'bars',
               ['I-395', 'I-90/94|run 6', 'I-90/94|other day', 'I-294', 'A39|Germany'],
               [('Chosen model', 'ours', [5.93, 4.15, 4.00, 10.60, 11.30]), ('Gipps, calibrated', 'av', [6.16, 5.04, 5.05, 11.55, 12.92]), ('Krauss, calibrated', 'human', [6.77, 5.33, 5.43, 11.70, 12.78]), ('SUMO defaults', 'old', [7.86, 6.31, 6.16, 13.68, 14.90])]))
B.append(facts(('g', 'It also beats Wiedemann 99, the family behind the best-known commercial tool, in every set: for example 4.00 m against 5.36 m. And IDM calibrated: 4.00 against 5.54 m.', 'Python'),
               ('g', 'Fit on US data only, scored on German A39: 11.64 m, against 14.05 m for the best Krauss and 20.57 m for IDM, over 5,248 windows.', 'Python'),
               ('g', 'The GPU kernel gives the same answers as the Python model on the same real tracks: 5.94 vs 5.93, 4.13 vs 4.15, 3.98 vs 4.00, 10.65 vs 10.60, 11.22 vs 11.30 m.', 'GPU, not merged')))
B.append(chart('Speed swings along a real line of 8 cars', 'Real platoons hold steady. Old models grow or fade. Standard deviation of speed in m/s, by position in the line. Real data: 239 chains, 1,792 followers.', 'lines',
               [1, 2, 3, 4, 5, 6, 7, 8], [('Real', 'real', [1.87, 1.86, 1.87, 1.89, 1.84, 1.86, 1.87, 1.87]), ('Chosen model, GPU', 'ours', [1.87, 1.89, 1.91, 1.93, 1.89, 1.90, 1.91, 1.93]), ('Krauss defaults, 1 s', 'human', [2.00, 2.14, 2.29, 2.44, 2.55, 2.65, 2.82, 3.01]), ('Krauss calibrated', 'alt', [1.74, 1.65, 1.57, 1.51, 1.41, 1.35, 1.29, 1.27])], xl='car in the line', xu='', ymin=1))
B.append(chart('After someone cuts in, how fast does the gap recover?', 'Seconds of gap at each time after the cut-in. The simulated driver recovers at the real pace.', 'lines',
               [0, 2, 5, 10, 15, 20, 25], [('Real, I-395', 'real', [0.72, 0.75, 0.88, 1.09, 1.22, 1.31, 1.41]), ('Real, A39 Germany', 'old', [0.72, 0.80, 0.91, 1.02, 1.12, 1.21, 1.27]), ('Chosen model, GPU', 'ours', [0.73, 0.84, 0.93, 1.08, 1.21, 1.34, 1.42])], xn=True, xl='seconds after the cut-in', xu='s', ymin=.5))
B.append('<h3>What real drivers actually do</h3>')
B.append(facts(
    ('g', '<b>A lane change takes 5 to 6 seconds</b>, not an instant: 5.6 s on the German A39 (34,904 cars), 5.2 s on US roads, 5.8 s for trucks. It barely depends on speed. SUMO\'s default rule refuses gaps real drivers take: it allows only 35% of real US congested lane changes.'),
    ('g', '<b>A queue leaves a green light about one car every 2 seconds</b>: 2.0 s, or 1,800 cars per hour per lane, from 4,214 queues. Only 55 long queues, on one Sunday in Braunschweig, so this is thin. Los Angeles agrees: 1.9 s median.'),
    ('g', '<b>Stop-and-go waves travel backwards at about 34 km/h</b> in real chains: 33.7 km/h. Our GPU model: 34.4.'),
    ('g', '<b>At yellow, half of drivers stop only from 5.1 s or more away</b>, and almost nobody brakes hard for it: 0.6% stop if it needs 2 to 3 m/s².'),
    ('g', '<b>Entering a roundabout takes a gap of about 3 s</b>: 2.95 s, from 7,131 decisions at three small Swiss rings.'),
    ('g', '<b>Thirty seconds of driving doesn\'t identify a person\'s style.</b> Population values predict the next 30 s better than a fit to that very driver.'),
))
B.append(fig('research/truth/fig/05v2-lane-change.png', 'Real lane changes take about 5 s in two countries.'))
B.append(fig('research/truth/fig/05v2-platoon.png', 'Speed swings along real platoons stay level, old models grow or fade.'))
B.append('<h3>Do people let you in? Yes.</h3>')
B.append(stats(('610 of 610', 'cars on the I-80 lane that ended got in'), ('22.6 s', 'median wait. The longest was 79 s.'), ('59%', 'chance a nearby car lets you in'), ('1 in 16', 'followers actively yield. Most courtesy is just tolerance.')))
B.append(chart('The slower the other car, the more it lets you in', 'I-80, 1,023 cases. Share of cars that let the waiting car in, by the other car\'s speed relative to it.', 'bars', ['3+ m/s|slower', '1-3|slower', 'about|same', '1-3|faster', '3+ m/s|faster'], [('Let in, %', 'ours', [90, 62, 51, 55, 36])]))
B.append(facts(
    ('g', 'Urgency comes from running out of road, not from time waited: the waiting-time effect is indistinguishable from zero, and the distance effect is strong (13,509 states).'),
    ('g', 'At a lane end people roughly take turns: most often one main-lane car between two merging cars, 249 of 558 against 137 for random order. SUMO gets the wait about right but turn-taking wrong: no main-lane car between merging cars in 66% of cases, against a real 26%.'),
    ('g', 'Merge on the GPU: median wait 20 to 24 s against a real 22.6, and no car failed to merge. The shape was tuned to pass, though.', 'GPU, not merged'),
    ('g', 'Lane change on the GPU: 4.77 s in congestion and 5.09 s in free flow, against a real 5.05 to 5.6. Time in both lanes 2.65 and 2.83 s, against a real 2.8.', 'GPU, not merged'),
    ('l', 'Blinkers aren\'t in any dataset we used, so their effect on letting in is unmeasured. You asked about this. There\'s no data for it yet.'),
))
B.append(fig('research/truth/fig/14-turn-taking.png', 'Real, random, SUMO and an early prototype: how drivers take turns at a lane end.'))
B.append(clips(('gallery__humans__courtesy_i80_0', 'Courtesy on the I-80 shape, one', None), ('gallery__humans__courtesy_i80_1', 'Courtesy on the I-80 shape, two', None)))
B.append(facts(('a', 'A permanent lock is fixed: a car needing the other lane of a very short road stopped back on the junction lane and blocked it for good. Stockholm has 11,015 lanes under 15 m. On a 5 m stub, arrivals went from 7 of 96 to 140 of 140, with 20 of those cars rerouted.', 'GPU code on CPU, not merged')))
B.append('<h3>Where the new driver still misses</h3>')
B.append(facts(
    ('r', 'Roundabout: the earlier 5.60 s gap was mostly our own estimator, now fixed. It reads 2.95 s against a real 2.95, but only at 300 cars per hour per arm: 2.40 s at 250 and 4.07 s at 350, twice the real spread.'),
    ('r', 'No capacity drop: flow after a breakdown comes out 7 to 13% higher than before, because speed falls early and there is no high-flow state to drop from. Published guidance asks for this test before any city claim.'),
    ('r', 'Queue discharge misses on the GPU: headway 2.29 to 2.36 s (band 1.8 to 2.2). Standing spacing now passes at 0.1 s steps (7.41 m, band 7.0 to 8.2), but not at 0.5 or 1 s. The Python prototype had passed.'),
    ('r', 'Too much courtesy: 83 to 88% let in against a real 59%. The cause is found: real drivers merge with 0.9 m of lane left, ours about 80 m early, so too few get passed. A setting that fixes it raises the median wait to 38 s, so it stays off.'),
    ('r', 'Ring jam: 49 to 53% of cars stopped and a mean speed of about 2 km/h, against the Python model\'s 25% and 3.9 m/s. It stays too jammed. Wave speed 29 to 30 km/h at 0.5 s steps, real about 20.'),
    ('r', 'Signal approaches: cars spend longer in the wrong lane than in SUMO. Worst case: 17 of 1,000 cars arrived on a 30 m approach at 2,000 cars per hour with spillback.'),
    ('r', 'Some of this agreement is partly tuned to the same data, and merging only passes after a large shift of the published constants. A blind test needs new data, and the better datasets (highD, SHRP2) need your application.'),
))

# ---- Physics
B.append(head('Real physics', 'Braking, grip, power, hills and bodies in 2D'))
B.append('<p class="answer">The old update rule lets a car stop in half the distance tyres allow. The new physics fixes that and works in clean tests. In a city, it doesn\'t hold up yet.</p>')
B.append(chart('Stopping distance at 9 m/s² braking, metres', 'The old rule at 1 s steps stops impossibly short: from 50 km/h that implies 19.7 m/s², where a real car manages 8.30 to 8.91 on dry road (ADAC).', 'bars', ['30 km/h', '50 km/h', '100 km/h'], [('Old rule, 1 s steps', 'human', [0.00, 4.89, 29.33]), ('Old rule, 0.1 s steps', 'old', [3.45, 10.03, 41.48]), ('Correct physics', 'ours', [3.86, 10.72, 42.87])]))
B.append(chart('Cars per green hour through a signal, against Swedish design values', 'Straight on is right, turning isn\'t. Trafikverket\'s values are design numbers, not measurements. GPU at 0.1 s steps.', 'bars', ['Straight', 'Right', 'Left', 'Double turn'], [('Design value', 'real', [1900, 1700, 1700, 1500]), ('Physical driver', 'ours', [1906, 1395, 1585, 1739]), ('Human driver', 'human', [1858, 1452, 1434, 1199])]))
B.append(chart('Side road capacity against theory, cars per hour', 'Small time steps follow the theory. 1 s steps fall behind in heavy traffic.', 'lines', [100, 300, 600, 900], [('Theory', 'real', [1056, 846, 620, 451]), ('GPU, 0.1 s steps', 'ours', [1116, 927, 639, 363]), ('GPU, 1 s steps', 'human', [930, 729, 417, 276])], xn=True, xl='main road flow, cars per hour', xu='cars/h'))
B.append(facts(
    ('a', 'The new safe-speed rule: 0 collisions in 23,956 trials under a hard-braking leader, where the old rule crashed 252 times in 4,000. One lane, Python, and the first three versions failed.', 'Python'),
    ('a', 'Emergency stops on the GPU: 25 vehicle pairs, no contact, least gap 1.29 m at 1 s steps and 2.50 m at 0.1 s, hardest braking 8.3 m/s².', 'GPU, not merged'),
    ('a', 'Straight-through flow hits the Swedish design value at both step sizes: 1,882 and 1,906 against 1,900. Jam spacing 7.50 m against 7.43 m.', 'GPU, not merged'),
    ('a', 'Five test cars follow the official WLTC test cycle exactly on the GPU, with energy books balancing within 0.0002%.', 'GPU, not merged'),
    ('a', 'One power number gets four real combustion cars\' 0 to 100 km/h within -14.5% to +8.4% across a 5:1 power range. Corners and hills behave as the formulas say (40 t truck: 57 km/h on 3%, 38 km/h on 5%), though there\'s no real measurement to compare with.'),
    ('l', 'Real drivers use far less than the car can do. Measured acceleration is about 2 m/s² falling with speed (4,820 cars), so the model separates what the car can do from what the driver asks for.'),
))
B.append(fig('research/truth/fig/11-physics-check.png', 'Car ability against the test cycle, lane-change shapes, and the impossible stops on the right.'))
B.append('<h3>Where physics fails today</h3>')
B.append(table(['Run, no teleports', 'Cars', 'Stuck', 'Mean speed'], [
    ['Berlin morning, physical driver', '286,323', '222,559', '1.85 m/s'],
    ['Berlin morning, human driver', '277,620', '199,380', '2.53 m/s'],
    ['Stockholm morning, physical driver', '183,829', '77,641', '1.59 m/s'],
    ['Stockholm at 50% demand, old trips', '119,309', '35,424', ''],
    ['Stockholm morning, new demand, physical driver', '160,046', '132,453', '1.61 m/s'],
    ['Stockholm morning, new demand, human driver', '167,295', '114,298', '2.57 m/s'],
    ['Stockholm at 1% demand', '2,757', '39 (was 184 four builds ago)', ''],
    ['Berlin at 1% demand', '22,481', '3,849 (17%)', ''],
]))
B.append(clips(('gallery__humans__gridlock_stockholm_verkstadsgatan', 'A gridlock cycle in Stockholm', 'Verkstadsgatan, with the earlier driver on the old demand. Mostly a lane and its reverse blocking each other.'), ('gallery__humans__gridlock_berlin_cycle', 'A gridlock cycle in Berlin', 'A cycle of waiting cars with the earlier driver on the old demand.')))
B.append(facts(
    ('r', 'Even at 1% demand cars get stuck, from lane and right-of-way waits, not traffic. That points to faults in the map or the rules. The count is shrinking build by build.'),
    ('r', 'The 2D body check still finds contacts in cities: 3,347 incidents at Stockholm 50%, and "other" is the biggest category, still unexplained.'),
    ('r', 'Turning flow misses the design values: right turn 1,336 to 1,395 against 1,700. The newest build passes 34 of 44 of its own physics tests.'),
    ('r', 'Fuel and electric efficiency are invented inputs so far (for example 6 l/100 km, 85% and 60% regeneration), and real Stockholm slopes aren\'t loaded. So energy numbers are comparisons, not findings.'),
))

# ---- Cities
B.append(head('Real cities', 'Why Berlin was half empty and Stockholm locks up'))
B.append('<p class="answer">We ran the public city scenarios against real counters. Berlin holds about half the real traffic. Stockholm doesn\'t lock up because of too many cars: it has the wrong trips on a badly converted map. Fixing that stops the lockup at 60% demand, but neither city matches reality yet.</p>')
B.append('<p>Word you need: a <b>teleport</b> is a stuck car the simulator lifts out and puts down further along. Every simulator has a version of it. A lot of teleports means the city has locked up.</p>')
B.append('<h3>Berlin: half the traffic is missing</h3>')
B.append(chart('Berlin: real traffic against the simulation, hour by hour', 'Crossings per hour at 93 real detector sites, September 2024, against the public BeST scenario. Your suspicion was right: too little traffic, a weak morning peak and an empty night.', 'lines',
               list(range(24)), [('Real', 'real', [11828, 7727, 5834, 6126, 10656, 29036, 49612, 63933, 67405, 64030, 61153, 61749, 63579, 65854, 70683, 73835, 72759, 68990, 64054, 52769, 41953, 34007, 29106, 20289]),
                                 ('Simulated', 'ours', [315, 282, 380, 719, 1687, 11752, 26609, 31744, 34405, 37920, 40263, 39953, 40057, 41217, 43519, 45425, 46782, 45752, 42784, 39429, 28460, 17746, 10458, 4468])], xn=True, xl='hour of day', xu=':00'))
B.append(chart('Where did the traffic go?', 'Share of measured traffic at each stage. Most was lost building the scenario, not in any simulator.', 'bars', ['Official 2019|network', '148-149 sites', '93 sites'], [('MATSim source', 'alt', [0.75, 0.96, 0.93]), ('BeST input file', 'old', [0.50, 0.62, 0.59]), ('cars run', 'ours', [0.49, 0.61, 0.58])], ref=dict(v=1, l='Real traffic')))
B.append(facts(
    ('g', 'BeST is almost exactly "Berliners driving inside Berlin": 2.25 million trips against a survey\'s 2.21 million. No room for commuters from outside, visitors, deliveries or freight. Motorways leaving the city fall to 0.06 of real at the edge.'),
    ('g', 'Only 14.1% of 149 sites are within ±20%. 35.6% are below half.'),
    ('g', 'It isn\'t a clock bug. The best time shift is zero (r = 0.979).'),
    ('a', 'Our simulator loses only about 2% of the gap. It tracks published SUMO within 1% from 05:00 to 17:00. Then one jam on the A100 at Wilmersdorf grows from 17 road pieces at 15:00 to 614 at 20:00.'),
    ('a', 'Decision: keep BeST unchanged as a speed benchmark. A realistic Berlin would be built from MATSim v6.4 (4.42 million trips). Not built.'),
))
B.append(fig('research/truth/fig/berlin-review-volume-ladder.png', 'Most of Berlin\'s missing traffic vanished when the scenario was built, not in the simulator.'))
B.append(fig('research/truth/fig/berlin-review-motorways.png', 'The scenario loses the motorways that leave the city.'))
B.append(fig('research/truth/fig/berlin-review-evening-cluster.png', 'One connected jam grows from 49 to 614 road pieces between 16:00 and 21:00.'))
B.append('<h3>Stockholm: why it locks up</h3>')
B.append(stats(('46%', 'of the old trips contain an immediate U-turn'), ('99.55%', 'of its traffic counts are estimates, last updated 2016'), ('64%', 'of real toll-ring crossings made by the old 2.9 million trips'), ('00:05', 'first teleport, at night, with 793 cars driving')))
B.append(clip('stockholm_day', 'The old Stockholm day: it never recovers', 'By evening 41,000 cars crawl at 4 km/h. This is the failure we set out to explain, on the old demand.'))
B.append('<h4>The measured causes, biggest first</h4><p>About 70 controlled runs of the simulator, teleports by 10:00. Differences under about 10% are noise, and effects don\'t add up.</p>')
B.append(table(['Cause', 'What we changed', 'Effect on teleports'], [
    ['1. Wandering random routes', 'Same trips on shortest paths', '<b>-94%</b>, 28,253 to 1,721'],
    ['2. No route response', 'Three rounds of drivers learning routes', '<b>-89%</b>, 8,062 to 849'],
    ['3. More demand than this map carries', 'Replacement trips at 100, 80, 60, 40%', '70,595, 28,078, 10,131, 3,058'],
    ['4. Fragmented signals, links shorter than a car', 'Signal flags on the map', '-40% to -71%, but this deletes real signals too'],
    ['5. On-ramps forced to yield', 'Ramp rule fixed for 70 km/h motorways', '-14%'],
    ['6. Slow drivers', 'Acceleration 2.6 instead of 1.5', '-8% to -20%'],
    ['7. U-turns', 'Removed from the trips', '-18%. The first draft got this wrong.'],
    ['Signal timing type', 'Fixed-time instead of actuated', '+3%, no effect'],
], wide=(0, 1, 2)))
B.append(fig('research/truth/fig/stockholm-ladder.png', 'The key result. At the same distance driven, the replacement trips cause about a tenth of the teleports. Route feedback is the near-vertical drop.'))
B.append(fig('research/truth/fig/stockholm-teleport-map.png', 'Where cars get stuck. Left: at night, under light load, already stuck. Middle: morning on the old demand. Right: shortest paths and signal flags.'))
B.append(fig('research/truth/fig/stockholm-classfit.png', 'The old fit starved the main roads: motorways got 55% of their target, side streets 108%.'))
B.append(chart('The biggest single fix is better routes', 'Teleports by 10:00 on the same demand. Log scale. Warning: the best bar uses a map with too few traffic lights, see below.', 'hbars',
               ['Fixed-time signals', 'Baseline', 'U-turns removed', 'Better acceleration', 'Signal flags on map', 'Same km, thinned', 'Shortest paths + no turnarounds', 'Shortest paths + turn lanes', 'Shortest paths', 'Shortest paths + signal flags'],
               [('Teleports', 'ours', [29080, 28253, 23159, 22704, 16827, 5907, 6829, 4202, 1721, 498])], log=True))
B.append(chart('More trips did not mean more real traffic', 'Planned toll-ring crossings as a share of the real 400,976 per charge day.', 'hbars', ['Old 2.9 M trips', 'Old 60% file', 'Replacement: 1.32 M longer trips', 'Same on the register map', 'Learned routes at 60%', 'Learned routes at 80%'], [('Share of real', 'ours', [0.644, 0.395, 0.974, 1.015, 0.600, 0.789])], ref=dict(v=1, l='Real')))
B.append(chart('Route feedback works at reduced load, not at full load', 'Teleports by 10:00 after each round of drivers learning better routes. Log scale.', 'lines', ['Start', 'Round 1', 'Round 2', 'Round 3'], [('60%, low-signal map', 'ours', [8062, 1226, 948, 849]), ('60%, register map', 'human', [52249, 47323, 34203, 25119]), ('Full demand, low-signal map', 'alt', [72120, 117148, 111082, 114071])], log=True))
B.append('<h3>A Stockholm that doesn\'t lock up</h3><p>The recipe: real paths instead of random walks, fitted to the counts, on a repaired map, at 60%, with drivers learning routes from a day that isn\'t jammed. It isn\'t real Stockholm yet, but for the first time a whole day runs.</p>')
B.append(table(['Full day', 'Old scenario', 'Recipe'], [['Teleports', '290,352', '<b>2,449</b>'], ['Teleports per 1,000 trips', '177.6', '<b>3.1</b>'], ['Mean speed', '8.9 km/h', '<b>42.8 km/h</b>'], ['Mean time lost', '760 s', '<b>114 s</b>'], ['Still driving at midnight', '18,491', '2,235'], ['Never got on the road', '115,961', '1'], ['Collisions', '35,342', '51'], ['Trips arrived', '1,616,859', '788,725'], ['Distance driven', '3.90 M km', '6.44 M km'], ['Share of real toll-ring traffic (planned)', '40%', '60%']]))
if 'stockholm_recipe_day' in VIDEOS:
    B.append(clip('stockholm_recipe_day', 'Stockholm after the fix, one day', 'Same camera and speed as the old clip above. At 20:25: 5,032 cars at 42 km/h, where the old clip has 41,237 at 4 km/h. Replacement trips at 60% with route feedback, teleports still on and about half the trips. Not validated Stockholm.'))
_h = range(24)
_tp = lambda n: [int(METRICS[n]['by_hour'].get(str(i), {}).get('tp', 0)) for i in _h]
_sp = lambda n: [round(METRICS[n]['speed_by_hour'].get(str(i), 0), 1) for i in _h]
B.append(chart('Mean speed, hour by hour', 'km/h. The old day collapses from morning on. The recipe holds steady all day.', 'lines', list(_h), [('Old 60% day', 'human', _sp('base60')), ('Recipe', 'ours', _sp('v2_day2'))], xn=True, xl='hour of day', xu=':00', ymin=0))
B.append(chart('Teleports, hour by hour', 'Log scale. About 120 times fewer over the day, and this run has about half the vehicles, so compare per trip: 177.6 against 3.1 per 1,000.', 'lines', list(_h), [('Old 60% day', 'human', _tp('base60')), ('Recipe', 'ours', _tp('v2_day2'))], log=True, xn=True, xl='hour of day', xu=':00'))
B.append(fig('research/truth/fig/stockholm-running.png', 'Vehicles on the road: the old day never empties.'))
B.append(facts(
    ('a', 'It isn\'t our engine: SUMO locks up on the same old demand too. Running and inserted cars match within 2%, though cars has 35 to 64% more teleports. Its first teleport was at 00:06:44, on the same road where cars has the most in the first hour.', 'runs cut under 10 min'),
    ('a', 'Volume alone isn\'t the cause. Lockup rises smoothly with no safe level: 712 teleports at 15% demand, 124,345 at 100%.'),
    ('a', 'Same trips on shortest paths: 94% fewer teleports. U-turn removal only cuts 18%. Fixed-time signals change nothing outside noise.'),
    ('a', 'It isn\'t too many cars. Real Stockholm carries 2.5 times the toll-ring traffic of the old 60% file. The counts never needed 2.9 million trips: fitted on real paths, they need 1.32 million.'),
    ('a', 'The old trips were mostly short fragments: only 15,079 of 79,013 routes carried anyone, and 1,284 of 1,922 signals control no crossing road movement.'),
    ('r', 'At 100% the recipe still locks up, and that is only partly explained. Only 19% of counted roads match their counts (GEH under 5), and motorway distance is 32% of target. So this answers whether a day can run, not whether it is right.'),
    ('r', 'Engine bug found: cars ignores turn bans on connections, so cars drive through them. Being fixed on its own branch. The recipe\'s routes already respect them.'),
    ('r', 'The recipe leaves bus lanes open to cars, which is wrong. Closing them raises teleports by 10:00 from 849 to 1,934.'),
    ('g', 'A replacement with fewer, longer trips (1.32 million, mean 8 km) matches the real toll ring at 0.974 without being fitted to it directly, though its trip-length setting was varied, so it isn\'t fully blind. It\'s still fitted to the old estimated street counts, not the measured ones.'),
))
B.append(note('Three warnings about those wins', '<p><b>Too few signals.</b> The map with the best results has 457 traffic lights, while the real register has 519 installations in the city alone. On the map closest to the register (903 controllers), the same demand does far worse: 631,888 teleports over a day. That map runs generated signal programs, so without the real plans we can\'t tell how much of this is the programs. That makes real signal plans the most valuable missing data.</p><p><b>Teleports carry every good result.</b> With teleports off, Stockholm stalls with 64 to 67% of trips unfinished.</p><p><b>Real signal timing isn\'t public.</b> Every generated signal uses the same default 90 s cycle, and no map here has real timing.</p>', True))
B.append('<h3>The honest test against real sensors</h3>')
B.append(vs('12.4%', 'normal year-to-year change at real Stockholm sensors', '77.3%', 'our error at sensors the model never fitted, best demand so far, uncalibrated'))
B.append(chart('Lockup falls fast, the fit to reality barely moves', 'Stockholm route-choice loop with teleports on, still running. Teleports per day, in thousands, by iteration. Over the same iterations, error at the held-out sensors only goes from 79.5% to 77.3% and flow stays about a third of real (0.283 to 0.34).', 'bars', [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [('Teleports, thousands', 'ours', [284, 261, 180, 160, 123, 118, 127, 142, 138, 54])]))
B.append(facts(
    ('g', 'A frozen hold-out exists: 260 of 847 measured sites kept whole, chosen before any fit, plus all 2025 values. Measured counts: 63,047 records from 4,053 sites.'),
    ('r', 'The final calibrated test hasn\'t finished. It\'s queued. The reading above is a monitor with nothing fitted. It has also been looked at every iteration, so it\'s no longer strictly unseen.'),
    ('r', 'Stockholm today can test demand, not congestion: no dated days, no peak speeds, no travel times, no signal plans. Better sources need your keys (Trafikverket, Trafiklab, Trafikkontoret), which are on your to-do list.'),
))
B.append(fig('research/truth/fig/maps07/s12_steriks_fleming_base.png', 'A real Stockholm junction as generated: 12 simulated signal controllers against 4 real ids, and bus lanes open to cars.'))
B.append(fig('research/truth/fig/maps07/s12_steriks_fleming_v5.png', 'The same junction rebuilt from the public register: 4 controllers, bus lanes closed (magenta).'))
B.append(facts(
    ('g', 'One real signal becomes many in the map: 1,304 controllers against 519 real installations inside the city. Rebuilding from the register gives 492.'),
    ('a', '745 of 3,690 signal approaches sit on road stubs shorter than a car. The rebuild doesn\'t solve that (still 741).'),
    ('l', 'Melbourne has the strongest open evidence (3,867 signal sites, 406 infrared sensors, survey, signal sheets). Stockholm stays primary, and Melbourne later as a stricter test. The engine doesn\'t support left-hand traffic yet.'),
))
B.append('<h3>The route-choice loop on the real engine</h3>')
B.append(chart('Luxembourg (LuST): the loop\'s best result', 'Teleports per day by iteration. Log scale. From 173,401 to 1,014, with unfinished trips going to zero and mean trip time falling from 9,265 s to 762 s. Teleports stayed on: with them off the same loop stays at 74% unfinished.', 'lines', [0, 1, 2, 4, 7, 9, 11, 13, 16, 19, 23, 29, 33, 35], [('Teleports', 'ours', [173401, 101359, 53922, 25296, 73055, 15545, 9793, 3450, 1565, 1537, 1230, 729, 758, 1014])], log=True, xn=True, xl='iteration', xu=''))
B.append(facts(
    ('a', 'Everybody re-routing at once is harmful, as theory says. On a 13×13 grid at 200% load it goes from 33% to 66 to 70% unfinished. A capped 15% reaches zero, then relapses.'),
    ('a', 'On a small test with known truth, calibration moves the totals but barely finds who goes where: zone-pair correlation 0.704 to 0.751. Counts alone can\'t recover trips, and that matches published warnings.'),
    ('r', 'Nothing has converged. Every convergence file says false, including LuST at a 7.67% gap against the 2% target. Stockholm\'s second demand guess melts down with about 1.5 million teleports.'),
    ('a', 'SUMO 1.28 on LuST\'s published routes jams too: 30,327 cars on the road and 16,792 teleports at 16:44, as the route-choice agent reported from a run still in progress. So that jam isn\'t only ours.', 'not in its report yet'),
))
B.append(clips('gallery__stockholm-signal-0__follow', 'gallery__stockholm-roundabout-0__clip', 'gallery__stockholm-signal-0__clip', 'gallery__berlin-ramp-1__clip', 'gallery__berlin-signal-1__clip', 'gallery__roundabout__follow', 'replay__stockholm-teleports', 'replay__stockholm-collision', 'berlin_a100'))

# ---- Comms and safety
B.append(head('Cars that talk, and can\'t crash', 'Real 5G standards, real radio limits, one safety rule'))
B.append('<p class="answer">Every car broadcasting everything ten times a second doesn\'t fit in the radio. Once a second can. Safety never depends on a message arriving, and the physics says why.</p>')
B.append('<p><b>The safety rule in one breath.</b> Each car keeps one number: the furthest point the car ahead is guaranteed to reach, however hard it brakes. It can do anything as long as it can still stop before that point. A message can only move that point backward. Only its own sensors or a signed promise can move it forward.</p>')
B.append(stats(('503,333', 'attack cases, 0 contacts. Lost messages, replay, sensor dropout, full-brake leaders.'), ('97.7%', 'crash rate when one assumption is removed, here a forged message, so the test can detect failure'), ('< 1 m', 'gained by a 3 ms radio over 35 ms at 30 m/s. 1 m/s² of brake uncertainty costs 7.1 m.')))
B.append(chart('Gap needed behind another car, metres', 'Calculated from measured braking, by how much you trust the car ahead. A signed promise shrinks the gap, but raises impact speed from 20 to 29 m/s if the leader stops dead at 30 m/s.', 'lines', [50, 60, 108, 130], [('Must survive it stopping dead', 'human', [27.1, 36.2, 97.5, 135.5]), ('No trust, its brakes known', 'ours', [19.1, 24.6, 60.0, 81.2]), ('Signed promise', 'av', [11.0, 13.0, 22.5, 26.9])], xn=True, xl='km/h', xu='km/h'))
B.append(chart('What the radio can carry, Mbit/s', 'Each car\'s plan in a dense city, derived from ETSI message sizes. A 20 MHz channel carries 3.2 Mbit/s and 40 MHz 6.3. No field measurement of 5G direct car-to-car radio exists at any density.', 'bars', ['1,000 cars,|10 times/s', '3,000 cars,|10 times/s', '1,000 cars,|once/s'], [('Wanted', 'human', [24.2, 72.7, 3.5]), ('Available, 20 MHz', 'ours', [3.2, 3.2, 3.2]), ('Available, 40 MHz', 'av', [6.3, 6.3, 6.3])]))
B.append(facts(
    ('a', 'Our 2035 assumption, which is a judgement: status 2 to 4 times a second, intent about once, 20 MHz of NR sidelink. Called science fiction: 10 Hz from everyone to everyone, 3 ms and 99.999% city-wide, raw sensor sharing.'),
    ('a', 'A status message costs nearly five times its content on air: 41 bytes becomes 192. With a 16-point path it\'s 303, and with a certificate 442.'),
    ('a', 'Message age cancels in the maths, so the safety check needs no clock, and old or replayed messages are harmless. Largest numerical error 2.3e-13 m over 200,000 samples.'),
    ('a', 'Derived gap against the UN self-driving regulation at 60 km/h: 24.6 m against 26.7 m, with no fitting.'),
    ('l', 'Broadcasting intended paths is legitimate today: ETSI TS 103 900 V2.3.1 (May 2026) has a Path Prediction container. Coordinated crossing isn\'t a standard: the MCM is still a draft.'),
    ('l', 'Real radio: LTE-V2X 18 to 52 ms in the field, 0% loss at 400 m, 17% at 450 m. 1.1 dB moved loss from 0.44% to 99.84%. It falls off a cliff.'),
    ('l', 'Real savings from telling cars the signal timing are small: under about 1% of fuel per trip in Berkeley Lab\'s field data. Our own warning: if the simulator shows 20% across a city, suspect an artefact first.'),
    ('l', 'Satellite positioning alone can\'t do lane level in a city canyon: 2.73 to 45.5 m in Hong Kong with a good receiver. Austin with carrier phase reaches 17 cm, with no solution 13% of the time.'),
    ('r', 'The safety test is one-dimensional. Lateral motion, pedestrians and being hit from behind are outside it. On a road with no known grip limit, no finite gap is safe. It isn\'t a machine-checked proof.'),
))
B.append(fig('research/truth/fig/08-required-gap.png', 'Gap needed at each speed by trust level. Dots are the UN rule.'))

# ---- Signal-free
B.append(head('Junctions with no traffic lights', 'Tier D8: cars thread through at speed'))
B.append('<p class="answer">At a single junction it beats a good traffic light with the same cars by 17 to 44% in capacity in the Python model and 23 to 46% in the GPU runs. No contacts in any capacity, demand or radio-failure run. A car stalling in the box does cause contacts, and a saturated grid or a real district at peak doesn\'t hold yet.</p>')
B.append('<h4>How it works</h4><ol class="steps"><li>Every half second, the junction\'s coordinator reads each approaching car\'s distance and speed.</li><li>It schedules whichever car can reach its line first without crossing anything already reserved. Opposing streams go together. Crossing streams thread about 1.1 s apart.</li><li>Cars far out get advice and adjust. Cars close in get a firm grant, written down before the car can see it.</li><li>A car with no firm grant always stays able to stop before the line. So a lost message costs time, never safety.</li><li>A grant needs room on the exit lane, checked again at the last moment the car can still stop.</li><li>Separately, any car that can still stop brakes for something its own sensors see in the way.</li></ol>')
B.append(clip('gallery__d8__paths_and_slots', 'See the plan: paths and slots', 'Green lines are planned paths, the wide parts are where paths cross, and a green ring marks a car holding a firm slot.'))
B.append(clip('gallery__d8__weave', 'Threading at speed', None))
B.append(stats(('5,679', 'cars per hour, 1 lane, no signal. AV signal 3,888.'), ('9,918', 'cars per hour, 2 lanes, no signal. AV signal 6,837.'), ('4.1 s', 'delay at 5,200 cars per hour, 2 lanes, 20% turns. AV signal 20.2 s.'), ('0.01', 'stops per car, same case. AV signal 0.96.')))
B.append('<p class="small">These headline numbers ran on the RX 7900 XT, seeds 0 and 1. Sweeps below ran the same shader code mostly on the CPU, because the GPU queue was too long, and a 26-case check found flows the same in 14 and within 1.3% on the other single-junction cases.</p>')
B.append(chart('Maximum flow, cars per hour', 'By lane layout. Python model, and the GPU shader code lands within 5% in all 28 cells (largest gap 3.6%). Much of the jump from human signal comes from the cars themselves: 41 to 64% would appear behind a signal too.', 'bars',
               ['1 lane|straight', '1 lane|20% turn', '1 lane|35% turn', '2 lanes|straight', '2 lanes|20% turn', '2 lanes|35% turn', '3 lanes|20% turn'],
               [('Human signal', 'human', [2700, 2127, 1857, 3600, 3555, 3384, 5208]), ('AV signal', 'av', [3894, 3021, 2505, 6843, 5412, 4578, 7254]), ('No signal', 'ours', [5619, 3600, 3021, 9834, 6462, 5346, 8850])]))
B.append(chart('Delay against demand, seconds per car', '2 lanes, 20% turns. Log scale. No signal stays low far longer.', 'lines', [600, 1500, 3000, 4200, 5200, 6500], [('Human signal', 'human', [4.3, 6.6, 14.9, 75.7, 149.1, 217.2]), ('AV signal', 'av', [1.1, 1.6, 3.2, 5.1, 21.0, 89.1]), ('No signal', 'ours', [0.7, 1.1, 1.6, 2.3, 4.1, 13.8])], log=True, xn=True, xl='cars per hour offered', xu='cars/h'))
B.append('<h3>Radios fail, nothing crashes</h3>')
B.append(chart('Message loss costs time, not safety', 'Delay in seconds at 3,000 and 5,000 cars per hour, log scale. Zero contacts at every level. Assumes perfect positions and clocks, which isn\'t modelled yet and matters more than loss.', 'lines', ['0%', '10%', '30%', '50%', '70%', '90%', '100%'], [('3,000 cars/h', 'ours', [1.7, 1.7, 1.9, 2.3, 6.0, 266.1, 432.9]), ('5,000 cars/h', 'human', [4.3, 5.4, 4.6, 7.9, 54.2, 372.7, 465.1])], log=True))
B.append(clips(('gallery__d8__loss_70pct', '70% of messages lost', None), ('gallery__d8__coordinator_crash', 'The coordinator crashes', 'Down for 60 s. No contacts: cars stop and take turns by sensing. Delay 5.6 s at 3,000 cars per hour and 21.3 s at 5,000.'), ('gallery__d8__exit_blocked', 'Blocked exit, protection on', '0 overlaps, 2.9 car-seconds stopped in the box.'), ('gallery__d8__exit_blocked_unprotected', 'Blocked exit, protection off', 'Failure on purpose: 17 overlaps and 572 car-seconds. This shows the test can detect failure.')))
B.append(facts(
    ('a', 'Single junctions: 0 overlaps, 0 ungranted crossings and 0 teleports across every no-signal capacity, demand and radio-fault run. Injected stalls are the exception, below. The other overlaps were in the deliberately unprotected case and one in a human signal baseline.', 'mostly CPU-run shader'),
    ('a', 'At 100% loss, flow is 552 cars per hour with sensing alone. Without that rule it deadlocks. That rule is my own addition, not from a paper.'),
    ('a', 'Below saturation on a 9-junction grid: 15,720 against 14,992 cars per hour, delay 11 s against 37 s, 0 overlaps. One seed.'),
    ('l', 'Published fair comparisons give small or conditional gains. Tachet\'s famous 2× compares a 1 s rolling headway with a 2 s queue slot. No real vehicles have shown saturated signal-free crossing, the largest verified test being about three cars.'),
))
B.append('<h3>Where it breaks</h3>')
B.append(table(['Overloaded 9-junction grid', 'Cars/h', 'Delay', 'Contact events'], [
    ['2 lanes, no signal', '15,803', '112 s', '<b>57</b> (3 seeds)'], ['2 lanes, AV signal', '15,291', '136 s', '0 (3 seeds)'],
    ['2 lanes, metered to 280 cars', '17,372', '103 s', '10 (4 seeds)'], ['2 lanes, metered to 240', '16,508', '115 s', '5 (4 seeds)'], ['2 lanes, metered to 200', '14,872', '139 s', '0 (4 seeds)'],
    ['1 lane, no signal', '9,539', '121 s', '18 (3 seeds)'], ['1 lane, AV signal', '8,413', '154 s', '0 (3 seeds)'], ['1 lane, metered to 140', '8,798', '137 s', '0 (4 seeds)']]))
B.append(facts(
    ('r', 'On 2 lanes, the contact-free metering level carries 3% less than a signal. Four seeds of 450 s can\'t show any level is safe.'),
    ('r', 'On the old demand, a 1 km Stockholm district at 8,000 cars per hour carried 1,846 against 2,659 with signals at their real positions and generated timing. 64 of 108 junctions were refused, because OpenStreetMap draws one junction as a chain of short links. The next chapter re-tests it on the new demand.'),
    ('r', 'One real Stockholm junction with its signal removed: 3,088 against 2,613 cars per hour. But the same conflict table with a signal gives 3,078, so most of the gain comes from the cars, not from removing the light.'),
    ('r', 'A stalled car does cause collisions at the chosen setting: 0.10 and 0.30 per stall, plus 5 ungranted crossings. The stricter setting saw none in 63 stalls, but with turns it gives away nearly the whole gain (-8% to +3%). I set the first as default for now. It\'s your call.'),
    ('r', 'Not modelled: position error, clock error, pedestrians, mixed traffic, several car types. The earlier CPU model also undercounted contacts, by missing tails still in the box. The GPU audit found and fixed that.'),
    ('r', 'Cost at city scale on the real GPU is unmeasured: that job waited over 1.5 hours for its turn and was stopped. On the CPU, 2,500 junctions cost 2.15 ms per step, 0.92 without the coordinator, 58 MB.'),
))
B.append(note('These clips show the controller before planning', 'They still brake late. The rebuilt version is in the next chapter.'))
B.append(clips(('gallery__d8__grid_overload_metering', 'Overload, with and without metering', None), ('gallery__d8__grid', '9 junctions, no signals', None), ('gallery__d8__stockholm_junction', 'A real Stockholm junction, signal removed', None), ('gallery__d8__stall_level_a', 'A car stalls, chosen setting', 'Shows a real contact.'), ('gallery__d8__stall_level_b', 'A car stalls, stricter setting', None), ('gallery__d8__weave_turns', 'Threading with turning cars', None)))

# ---- Plan ahead
B.append(head('No more braking at the line', 'Your correction, measured, built and tested'))
B.append('<p class="answer">You watched the clips and said the cars shouldn\'t brake in front of the junction, because they know far ahead when everyone arrives. You were right, and it\'s built. At 5,200 cars per hour, hard braking falls from 2,688 events to 8 per run with the same flow and delay. Between junctions it\'s only partly built, it isn\'t yet good for a city at full demand, and it still has a few contacts on overloaded grids.</p>')
B.append(clip('gallery__d8__plan__versus_5200', 'Same arrivals: late braking on top, planned below', 'Top: today. Bottom: every car knows every other car\'s arrival. Red means braking over 1 m/s², bright over 2.5. Running totals top right.'))
B.append(stats(('92% to 1%', 'cars braking over 3 m/s² at 5,200 cars per hour'), ('2,688 to 8', 'hard brakes per run at 5,200 cars per hour'), ('4.4 to 4.3 s', 'delay at 5,200 cars per hour'), ('60 to 1.2 ms', 'mean miss of its slot at 3,000 cars per hour, one seed, perfect positions')))
B.append(fig('research/truth/fig/d8/plan/speed_distance_3000.png', 'Every car\'s speed on its way in, same arrivals. Orange is today: sudden dips and turning cars braking hard in the last 35 m. Blue is planned: cars settle early, and turning cars slow over 100 m.'))
B.append(chart('Speed thrown away by braking on the way in, m/s per car', 'Three seeds, 600 s, 2 lanes, 20% turns. Gentlest is the least braking that still reaches the line at the same moment and takes the corner at its turn speed. It\'s per car and ignores other cars, so real traffic won\'t quite reach it.', 'bars', ['3,000 cars/h', '5,200 cars/h'], [('Today', 'human', [3.08, 6.05]), ('Planned', 'ours', [2.18, 3.43]), ('Gentlest possible', 'old', [1.44, 2.01])]))
B.append(chart('Energy braked away, Wh per car', 'Same runs. This is kinetic energy, the fuel and battery effect isn\'t modelled in this tier yet.', 'bars', ['3,000 cars/h', '5,200 cars/h'], [('Today', 'human', [13.1, 24.9]), ('Planned', 'ours', [9.4, 14.8]), ('Gentlest possible', 'old', [6.7, 9.3])]))
B.append('<h4>How it works</h4><ol class="steps"><li>Every car broadcasts when it expects to reach the line, as far out as the radio reaches.</li><li>Slots are given far upstream and move only for a reason. New cars take free space instead of pushing others back.</li><li>Each car holds a steady speed to arrive on its slot, with limits on braking and jerk. Hard braking is only for safety events, and each one is counted.</li><li>A car plans from the broadcast plan of the car ahead, not just the gap.</li><li>The safety rule is unchanged: without a firm grant a car can always stop.</li></ol>')
B.append(clip('gallery__d8__plan__arrivals_3000', 'Every car says when it will arrive', 'The label beside each car is its broadcast arrival time, to the millisecond. The chart below shows slots filling up long before the cars arrive: amber is planned, green is firm.'))
B.append(clips(('gallery__d8__plan__versus_3000', 'Same comparison at 3,000 cars per hour', 'Top: today. Bottom: planned.'), ('gallery__d8__plan__close_3000', 'Close up', 'The junction up close with planning on.')))
B.append(fig('research/truth/fig/d8/plan/braking_by_distance.png', 'Where the speed is lost. At 3,000 cars per hour, the share in the last 50 m falls from 71% to 49%, and what remains is mostly turning cars slowing for the corner.'))
B.append(fig('research/truth/fig/d8/plan/time_distance_3000.png', 'Time against distance, the classic traffic picture, with the slots marked.'))
B.append(facts(
    ('a', 'I reran it separately with my own metric, one seed, 280 s. 3,000 cars per hour: speed lost 3.25 to 2.25 m/s, cars over 3 m/s² 72% to 0. 5,200: 8.64 to 4.95 m/s, 96% to 0. Flow and overlaps stayed the same or better.'),
    ('a', 'Cost at 3,000 cars per hour: delay rises 0.4 s, from 1.5 to 1.9 s. Below saturation, flow is the same.'),
    ('a', 'Single junctions: zero overlaps in the capacity and demand runs. One contact appeared at 80% message loss at 5,000 cars per hour.', 'CPU-run shader'),
    ('a', 'Turning cars are slower than the map allows, and that\'s correct: at map speed a corner peaks at 8.6 to 10.4 m/s², beyond dry grip of about 8.6 and far over our 4.37 limit. The simulator has no tyres, so it would happily give 12 to 20% more flow that no real car could drive. The cap is now 4.0 m/s², and cars speed up after the apex, which adds 1.8 to 2.4%.'),
    ('a', '<b>How close to a millisecond?</b> The message and clock carry 1 ms. With perfect positions, 72% of cars arrive within 1 ms of their slot at 3,000 cars per hour. With 0.3 m of position error the mean miss is 25 ms, so tens of milliseconds is the honest figure.'),
    ('a', 'What tighter timing buys: a 0.2 s margin instead of 0.3 s gains flow in every test, up to 11.1%, with 0 contacts in 54 runs with no position error. It\'s as safe as 0.3 s up to 0.3 m of position error, and worse at 1 m (6 contacts against 2), so the default stays 0.3 s.'),
    ('l', 'The standard CAM Path Prediction field resolves only 0.1 s, so 1 ms needs a new field. That is a proposal, in no standard.'),
))
B.append(chart('Saturated capacity, planned against today, % change', '4 seeds, 800 s. T is straight through, M has 20% turns, H has 35% turns. The gate was no more than 2% below today. One cell still misses it and the cause isn\'t found.', 'bars', ['1 lane|T', '1 lane|M', '1 lane|H', '2 lanes|T', '2 lanes|M', '2 lanes|H', '3 lanes|M'], [('Change, %', 'ours', [2.3, 0.7, 1.0, 6.1, 1.6, -4.2, -1.4])]))
B.append('<h3>Planning across junctions: the first step</h3><p>City blocks are too short to plan inside one junction, so a slot at one junction now waits until the car will have room on its exit, using the next junction\'s plan to know when that room appears. So a late slot downstream slows the car upstream. This is less than you described: a car still holds one junction\'s slot at a time, and the full plan along a route isn\'t built.</p>')
B.append(clip('gallery__d8__plan__grid_24000', 'Overloaded grid: today against planning across junctions', '24,000 cars per hour offered on 9 junctions. Running totals top right on each side.'))
B.append(table(['Grid, 6 seeds', 'Cars/h today', 'Cars/h planned', 'Contacts today', 'Contacts planned', 'Hard brakes today', 'Hard brakes planned'], [
    ['1 lane, 4,000', '3,976', '3,989', '0', '0', '4,431', '11'], ['1 lane, 9,000', '8,865', '8,864', '2', '0', '13,952', '196'], ['1 lane, 14,000', '9,557', '9,793', '58', '<b>1</b>', '18,100', '1,136'],
    ['2 lanes, 8,000', '7,919', '7,920', '0', '0', '6,057', '29'], ['2 lanes, 16,000', '15,885', '15,849', '4', '0', '17,065', '210'], ['2 lanes, 20,000', '17,965', '18,151', '78', '<b>2</b>', '29,802', '1,215'], ['2 lanes, 24,000', '16,203', '15,493', '123', '0', '29,109', '1,828']]))
B.append(facts(
    ('a', '3 contacts in 42 runs, against 265 today. I reran two seeds at 24,000 with the exact settings: the planned runs matched exactly, with 0 contacts against 25 and 10 today.', 'CPU-run shader'),
    ('r', 'Zero contacts is your requirement and it isn\'t met: 3 remain. Adding metering at the edge gives 0 in 9 runs, but carries less. Contacts here are chaotic: the same seed differs with the thread count.'),
))
B.append(clip('gallery__d8__plan__stockholm_60pct', 'Stockholm district, 60% of the new demand', 'Left: generated signals. Middle: no signal today. Right: planning across junctions. Same arrivals. Signal timing isn\'t the real timing.'))
B.append(chart('Time lost per trip, Sveavägen district, seconds', 'New demand from the Stockholm report, 2 seeds, with spread. Self-driving cars throughout. Signal timing is generated. 50 of 95 junctions here are coordinated, the rest use normal priority.', 'bars', ['30% demand', '60% demand', '100% demand'], [('AV on signals', 'av', [23.9, 33.7, 56.5]), ('No signal, today', 'alt', [19.8, 33.8, 66.4]), ('No signal, planned', 'ours', [21.5, 32.9, 79.7])]))
B.append(facts(
    ('a', 'On the corrected demand, "worse than signals" no longer holds for today\'s no-signal control at 30 to 60%: 17% better at 30%, level at 60%. At 100% it\'s 18% worse on this map and level on the map with joined nodes. The earlier 1,846 against 2,659 used demand we now know was wrong.'),
    ('r', 'Planning costs time in a city: 20 to 22% more than today\'s no-signal control at 100%, and 20 to 41% more than signals, though with 11 to 42 times fewer hard brakes. So it isn\'t a good city policy yet. Median block is 55 m and 21% are under 25 m, which leaves too little distance to plan. Only 50 of the net\'s 199 junctions are coordinated.'),
    ('r', 'Contact counts in Stockholm aren\'t comparable between policies, because only coordinated boxes are audited. In one 45 s window the signal panel shows 594 frames of overlap flagged by the picture\'s body check, against none for both no-signal panels. Overlaps on one merging lane at 100% demand remain unexplained.'),
))
B.append('<h3>Where planning still fails</h3>')
B.append(facts(
    ('r', 'A plan held along the whole route, and one coordinator for chained map nodes, aren\'t built. The published design for this (Chalaki and Malikopoulos) has an upper level setting arrival times along the route, and I found no finite road storage in it.'),
    ('r', 'Capacity: 2 lanes with 35% turns stays 4.2% under today, and even a 0.2 s margin doesn\'t clear the 2% gate on 6 seeds.'),
    ('r', 'Stalled cars on the grid: 24 to 28% less flow than today, though with fewer contacts (34 against 66, and 1 against 20). They still aren\'t zero.'),
    ('r', 'Message loss on the grid: at 30% loss, 15 contacts against 2 today. Cause not found. Heavy loss at one junction is fixed: at 70% it\'s now 4,236 against 4,350 cars per hour, where it was 3,234 against 4,548.'),
    ('r', 'A 1,000 m approach at 5,200 cars per hour gains almost nothing and adds delay. Far-out slots at 5,200 still move nearly as much as today.'),
    ('r', 'The published energy-optimal cubic speed profile lost to a simpler cruise-and-ramp. Resequencing dynamically brakes least, but costs up to 22% at saturation, so it stays optional. Max pressure was tried and dropped.'),
    ('r', 'Not modelled: tyres, drifting satellite and clock error, real signal programmes, correlated message loss, humans, pedestrians, and the physics layer\'s energy model. City runs still need teleports. All numbers ran the shader code on the CPU, because the GPU queue never freed up.'),
))

# ---- Tiers
B.append(head('The ladder of self-driving cars', 'Tiers D1 to D9, M1 to M4, each adding one capability'))
B.append('<p class="answer">The deterministic tiers up to D8 now exist in code on branches, but only D8 is properly measured. The rest are smoke tests on an older build, and those already show that some assumed gains vanish.</p>')
rows = [
    ('a', 'D1 Safe sensor driver', 'Built, smoke test', 'All 22 on a ring: 1,548 cars/h, no waves (human 1,736 with waves). One among 22 humans does worse. 1.5 contacts per merge run.'),
    ('a', 'D2 Predictive', 'Built, smoke test', 'All 22: 3,411 cars/h, 87 Wh/km. But always under a 1 s gap, 6.4 m/s impact if the leader stops dead.'),
    ('a', 'D3 Connected follower', 'Built, smoke test', 'Merge: 182 s against 367 s for humans. All-D3 ring keeps its waves. Fix committed, not measured.'),
    ('r', 'D4 Negotiating', 'Built, smoke test', 'Worse in the only data: merge 485 s with negotiation on, 180 s off. Fix committed, not measured.'),
    ('a', 'D5 Signal aware', 'Built, smoke test', 'Stopped 1.8 s against 51.9 s. Energy -21% on a fixed-time road, -8% on a green wave. Suspiciously high. Hard braking went up.'),
    ('a', 'D6 Signal partner', 'Built, smoke test', 'Delay 20 s against 85 s on a badly timed road, but 27 s against 33 s on a good one, and energy +11%. Worse on a Stockholm sub-net, 1 seed.'),
    ('a', 'D7 Platooning', 'Built, smoke test', 'All 22: 3,918 cars/h. 153 Wh/km, 9.2 m/s impact if the leader stops dead. Contacts on corridors.'),
    ('a', 'D8 Signal-free', 'Built and measured', 'See the previous chapters. Fails on an overloaded grid and a real district at peak.'),
    ('r', 'D9 Network coordinated', 'First step built', 'A slot waits for room on the exit using the next junction\'s plan. Contacts on overloaded grids 265 to 3. Routing and plans along the route aren\'t built.'),
    ('a', 'M1 Learned following', 'Python done, GPU part-trained', 'Python: 2,049 cars/h. GPU training at 42 of 70 generations.'),
    ('r', 'M2 Learned driving', 'Kernel built, no usable result', 'Contact in 100% of runs so far, raw.'),
    ('r', 'M3 Learned cooperation', 'Inputs built, no usable result', 'With rule: no contacts, 570 cars/h, rule overrides 62% of the time.'),
    ('r', 'M4 Learned communication', 'Not built', 'Only if research supports it.'),
]
B.append('<ul class="facts">' + ''.join(fact(l, f'<b>{esc(n)}</b>. {esc(s)}. {esc(t)}') for l, n, s, t in rows) + '</ul>')
B.append(chart('Ring road, all 22 cars the same tier: cars per hour', 'Preliminary: older build, 4 seeds, no real vehicles. Short gaps explain most of the jump, and those gaps have a price in a crash.', 'hbars', ['Humans', 'D1 Safe sensor', 'D2 Predictive', 'D3 Connected', 'D7 Platooning'], [('Cars per hour', 'ours', [1736, 1548, 3411, 1778, 3918])]))
B.append(chart('A fair baseline kills most of a signal tier\'s gain', 'Delay in seconds. D6 looks amazing against a badly timed road, then almost vanishes against a good green wave. Preliminary, 2 seeds.', 'bars', ['Fixed-time', 'Green wave', 'Actuated'], [('Humans', 'human', [84.65, 33.32, 25.91]), ('D5 Signal aware', 'av', [85.19, 32.65, 26.14]), ('D6 Signal partner', 'ours', [19.97, 27.23, 19.15])]))
B.append(facts(
    ('r', 'Zero contacts is a hard requirement, and these runs fail it: merge 122, corridor 16, Stockholm sub-net 134 (including humans). Mostly neighbour-lane and lane-start. Humans have them too.'),
    ('r', 'No sweep, no message-loss sweep and no feature on/off table exists yet. Those are the measurements you asked for. They wait on the GPU queue, and D8 and D1 to D7 currently use different car models, so they can\'t share a chart.'),
))

# ---- NN
B.append(head('Neural-network drivers', 'A real trained network, with and without the safety rule'))
B.append('<p class="answer">A real network learns to erase a traffic wave. So does a two-line formula, slightly better. Without the safety rule, networks crash as soon as they meet a kind of driver they didn\'t train on.</p>')
B.append(chart('One car out of 22 on a ring: flow', 'Cars per hour. Python. Note that this model is more generous than the field: real ring experiments range from -2.5% to +14.1%. In GPU code the same weights give 2,050.', 'hbars',
               ['Human model (no AV)', 'PI formula', 'FollowerStopper formula', 'Network, evolved', 'Network, gradient (PPO)', 'Network, trained on mixed humans', 'Network, no gap floor (tailgates)', 'Plain imitation', 'Network, energy reward only (parks)'],
               [('Cars per hour', 'ours', [1743, 2097, 2092, 2049, 2076, 1997, 2151, 563, 28])], cols=['human', 'av', 'av', 'ours', 'ours', 'ours', 'alt', 'alt', 'alt']))
B.append(fig('research/truth/fig/13-ring-learning.png', 'Both training methods learn to remove the wave.'))
B.append(fig('research/truth/fig/13-learned-law.png', 'What the network actually learned: a smooth, gentle rule. Nothing magic.'))
B.append(table(['Hard-brake test, contact in % of runs', 'Raw', 'With safety rule', 'Rule overrides'], [
    ['Evolved, 1 s floor', '67-70', '0', '1.2-1.3%'], ['Evolved, varied ring', '34', '0', '0.47%'], ['PPO, 1 s floor', '5', '0', '0.05%'], ['DAgger imitation', '100', '0', '0.24%'], ['Evolved, no floor', '100', '0', '36.17%'], ['PPO, no floor', '100', '0', '61.67%'], ['Evolved on mixed humans', '0', '0', '0%'], ['PI formula', '0', '0', '0%']]))
B.append(facts(
    ('a', 'Raw networks crash on a different kind of human: contact in 91 to 100% of runs. What it trained on matters more than how: trained on a mix of humans, 0 to 6%.'),
    ('a', 'Rewards get gamed. An energy-only reward parks the car (28 cars per hour). With no gap floor it tailgates at 1.1 to 3.9 m. Training under the rule makes it dependent: remove the rule and 94% contact.'),
    ('a', 'Evolution beats gradient on computer time: 61 s against 212 s to the same gate. That\'s why the GPU version uses it.'),
    ('a', 'At a motorway merge the best run gives +18% flow and -31% delay, but across 8 runs delay ranges from -32% to +18%. Unreliable.'),
    ('g', 'Copying real drivers: a fitted equation still wins. Spacing error 3.98 to 11.25 m against 4.69 to 12.58 m for the network, and Krauss 5.49 to 13.47 m. Plain imitation ends in collisions in up to 50% of windows.'),
    ('a', 'The network runs inside the GPU shader, matching Rust to within 9.54e-7 over 100,000 inputs. Same weights: 2,050 cars per hour on GPU against 2,049 in Python. Energy doesn\'t match between the two engines (95.7 against 68 Wh/km), so don\'t compare energy across them.', 'GPU, not merged'),
    ('r', '"Whether any learned policy beats a designed controller when both are held to the same gap, on anything: evidence so far says no." GPU training stalled in the queue at 42 of 70 generations. M2 and M3 are unusable so far.'),
))
B.append(fig('research/truth/fig/13-merge-learning.png', 'Merge: a warm start reaches human level, from scratch it parks.'))

# ---- Removing humans
B.append(head('Removing humans', 'What happens as drivers go away'))
B.append('<p class="answer">Our own experiment hasn\'t been run, because it needs the tiers finished. The research says: be careful, because the assumed following gap decides almost everything.</p>')
B.append(chart('Real robotaxis follow further back than the humans around them', 'Cars per hour per lane, derived from field trajectories. The thesis-era simulated AV has about twice the capacity of the real Waymo fit. The assumed gap decides the sign of the result.', 'bars', ['40 mph', '65 mph'], [('Real humans near Waymo', 'human', [2398, 2740]), ('Real Waymo, fitted', 'av', [1972, 2208]), ('Thesis AV', 'ours', [3736, 4371])]))
B.append(facts(
    ('a', 'Same I-80 scenario in SUMO: a 0.6 s gap gives travel time -22.5%, and the fitted Waymo gap gives +90%. The gap alone is 99% of the tier\'s time-loss cut on I-80 and 69% in Bologna.', 'SUMO, not cars'),
    ('l', 'No field evidence shows that replacing human drivers reduces congestion in a real city. No causal estimate was found in either direction.'),
    ('l', 'Commercial cruise control makes waves worse: 7 of 7 models unstable. A few designed damping cars do work locally: on Stern\'s ring, fuel -22 to -43%; on I-24, speed variance -52% near the cars, fading by 1,400 m.'),
    ('l', 'Robotaxis drive a lot empty: 53.6% occupied over 86.3 million miles. Modelling meta-analysis says +5.95% travel.'),
    ('l', 'Strongest real benefit is safety: pedestrian injury crashes -92% over 56.7 million miles (CI -99 to -66). Waymo\'s own staff, not independently replicated.'),
    ('l', 'Software failures are shared: Waymo crossed 7,000+ dark signals in the December 2025 San Francisco outage.'),
    ('l', 'People on foot are untested everywhere. No field trial exists of a dense signal-free junction with free pedestrians or cyclists. One group crossing costs about 3 car slots per lane.'),
    ('r', 'The step-by-step experiment (13 shares, 35,100 screening runs, ten hypotheses) is a plan. The only runs at different shares so far are smoke tests at 5, 50 and 100%.'),
))

# ---- What's next
B.append(head('What is still wrong', 'The short list, in order of what it blocks'))
B.append('<ol class="steps">'
         '<li><b>Real-city accuracy isn\'t proven.</b> No city passes its real sensors. The calibrated Stockholm test is queued.</li>'
         '<li><b>Nothing can run a real city at full demand without teleports.</b> Good runs use 60% demand and teleports. At full demand it still locks up, for reasons only partly explained, and on the map closest to the real register it\'s much worse.</li>'
         '<li><b>Almost nothing new is merged.</b> Physics, humans, D8, tiers, neural and route choice all sit on branches. Main is the old baseline.</li>'
         '<li><b>Contacts remain</b> on overloaded grids, in the tier smoke runs, and in city runs with the new drivers. "Zero" is your hard requirement and it isn\'t met outside single junctions.</li>'
         '<li><b>Measurements you asked for are missing:</b> every feature on and off, at every message loss and every share of automated cars, with energy. They depend on 2 and 3.</li>'
         '<li><b>Everything is simulation.</b> No real vehicle is involved in any AV result. Position and clock error, pedestrians and buses aren\'t modelled.</li>'
         '<li><b>GPU queue.</b> One card, many agents: jobs wait over an hour, which is why some results ran on the CPU or are stale.</li></ol>')
B.append('<p>Still needs you: Stockholm\'s signal plans, now the most valuable missing data. Also the Lastkajen and Trafikverket keys, tax passages per station from Transportstyrelsen, access to the regional demand models, and a Trafiklab key (all on your to-do list). And the choice of safety level for stalled cars.</p>')

# ---- Correct engine
B.append(head('Old SUMO copy: a regression check only', 'Not evidence of accuracy. SUMO is where we started, not the goal'))
B.append('<p class="answer">SUMO is not the target. The reference is real traffic and real car physics. This chapter only shows that the old compatibility mode runs as designed, flaws included, and it says nothing about reality.</p>')
B.append(chart('Mean trip duration in seconds, same inputs', 'Whole-city runs, SUMO 1.28 against cars on the GPU.', 'bars', ['Berlin|05:00-10:00', 'Mitte|24 h', 'Charlottenburg|24 h'], [('SUMO', 'old', [789.0, 414.3, 293.9]), ('cars', 'ours', [788.1, 414.3, 292.9])]))
B.append(facts(
    ('a', 'Road by road: vehicles per road match at r² 1.0000 in all three cities, mean speed at 0.986, 0.983 and 0.979.'),
    ('a', 'Berlin morning, SUMO then cars: 95th percentile trip 1,882 and 1,883 s. Waiting 67.6 and 66.4 s. Time lost 181.2 and 179.2 s.'),
    ('a', 'Thesis sweeps: speed error 0.08 to 0.80% on the ring, 0.19 to 0.36% on two signals, 0.25 to 2.78% on I-80, 2.98 to 7.34% on Bologna.'),
    ('r', 'Known misses: CACC on I-80 has a 22.9% time loss error. Isolated junction tests reach 84 to 100% worst-case error with Krauss drivers and 161% with IDM. A tightly packed ring inserts 22 of 260 cars where SUMO inserts 260.'),
    ('r', 'Berlin\'s evening departs from published SUMO after 17:00: 23,715 teleports over the day, against 2,090 published. Cause not found.'),
))
B.append(fig('report/figures/berlin_running.png', 'Vehicles on the road in Berlin: SUMO and cars lie on top of each other.'))
B.append(fig('report/figures/berlin_edges.png', 'Road by road, counts and speeds against SUMO.'))
B.append('<h3>Thirteen traffic phenomena appear by themselves</h3><p>All 13 scripted phenomena show up in both simulators, each by its own pass rule, without being programmed in. These are from the baseline drivers.</p>')
B.append(table(['Phenomenon', 'cars', 'SUMO'], [
    ['Phantom jam on a ring, cars stopped', '51.0%', '53.3%'],
    ['One smooth driver calms it, speed swing', '2.76 to 0.023 m/s', '2.73 to 0.0005 m/s'],
    ['One 20 s red, cars stopped', '15', '15'],
    ['Motorway capacity, peak flow', '2,737 cars/h', '2,757 cars/h'],
    ['Queue spillback blocks an exit', '1,680 s', '1,680 s'],
    ['Gridlock: arrivals, keep-clear rule off / on', '144 / 322', '153 / 309'],
    ['Grid loading, peak', '219 cars', '224 cars'],
]))
B.append(clip('phantom_jam', 'A phantom jam from nothing', 'A small disturbance grows into a stop-and-go wave circling a ring, with no obstacle anywhere.'))
B.append(clips('one_av', 'capacity_drop', 'brake_wave', 'spillback', 'gridlock', 'signal_discharge', 'onramp_merge', 'mfd', 'freeway_fd', 'thesis_ring', 'i80_day'))
B.append(note('Why this is not the goal', 'These drivers are wrong in ways only real data shows. The baseline jam wave moves at 7.2 km/h where a real ring gives about 20. Its queue leaves a green light every 1.20 s where real drivers need 2.0 s. The capacity drop only appears with deliberately weak drivers. That is why the next chapters exist.', True))

B.append('</div>')
BODY_MAIN = '\n'.join(B)


# ---------------------------------------------------------------- appendix: everything
def parse_sims():
    out = []
    for f in 'abc':
        lines = (OUT / f'facts/facts-{f}.md').read_text().splitlines()
        on = False
        for ln in lines:
            if ln.startswith('## '):
                on = ln.startswith('## Simulations run')
                continue
            if not on or '|' not in ln:
                continue
            c = [x.strip() for x in ln.strip().strip('|').split('|')]
            if len(c) < 6 or set(c[0]) <= set('-: ') or c[0].lower() == 'name':
                continue
            clean = [re.sub(r'[`*]', '', x) for x in c]
            out.append(clean[:7] + [''] * (7 - len(clean[:7])))
    return out


sims = parse_sims()
A = ['<div class="page">']
A.append(head('Everything', f'All {len(sims)} simulations, all videos, all figures'))
A.append('<details class="all"><summary>All simulations and experiments (' + str(len(sims)) + ')</summary><input class="q" type="search" placeholder="Filter, for example Stockholm or merge" aria-label="Filter simulations">')
for s in sims:
    A.append(f'<div class="sim"><b>{esc(s[0])}</b>. {esc(s[3])}: {esc(s[4])}<div>{esc(s[1])}. {esc(s[2])}. {esc(s[5])}. {esc(s[6])}</div></div>')
A.append('</details>')

kinds = [('all', 'All'), ('city', 'Cities'), ('junction', 'Junctions'), ('phenomenon', 'Phenomena'), ('av', 'Self-driving'), ('fault', 'Failures'), ('other', 'Other'), ('debug', 'Debug views')]
rest = [v for s, v in sorted(VIDEOS.items()) if s not in SKIP]
A.append(f'<h3>All {len(rest)} videos</h3><p class="small">Tap to play. Four duplicate clips and one broken clip are left out.</p>')
A.append('<div class="chips" data-for="#vg">' + ''.join(f'<button data-k="{k}" aria-pressed="{str(k == "all").lower()}">{esc(n)}</button>' for k, n in kinds) + '</div></div><div class="page wide" style="max-width:1040px"><div class="clips2" id="vg">')
for v in rest:
    k = 'debug' if v['slug'].endswith('-debug') or v['kind'] == 'qa' else ('fault' if v['kind'] == 'fault' else v['kind'])
    A.append(clip(v['slug'], data_k=k))
A.append('</div></div><div class="page">')
A.append(f'<h3>All {{FIGN}} figures</h3><div class="clips2" style="grid-template-columns:repeat(auto-fill,minmax(300px,1fr))">')
A.append('{{FIGS}}')
A.append('</div>')
for src, cap in [('report/figures/bench_realtime.png', 'A Berlin day runs 480 to 1,700 times real time.'), ('report/figures/bench_single.png', 'Throughput on the same PC by scenario, log axis.'), ('report/figures/bench_replicas.png', 'Throughput rising with vehicles up to about 400,000.'),
                 ('report/figures/berlin_trips.png', 'Berlin trip durations, SUMO and cars.'), ('report/figures/charlottenburg_running.png', 'Charlottenburg vehicles on the road, whole day.'),
                 ('report/figures/thesis_errors.png', 'Speed error against SUMO by scenario and model.'), ('report/figures/thesis_ring_speed.png', 'Ring speed against AV share. Matches SUMO, not reality.'), ('report/figures/thesis_bologna_speed.png', 'Bologna: cars runs a bit fast, a known error.'),
                 ('report/figures/thesis_glosa_two_signal_waiting_time.png', 'Two signals: waiting falls sharply with speed advice, in both simulators.'), ('report/figures/thesis_i80_vsl_speed.png', 'I-80: CACC splits from SUMO, a known gap.'),
                 ('results/phenomena/phantom_jam.png', 'Stop-and-go waves on a ring in both simulators. The wave speed isn\'t realistic.'), ('results/phenomena/one_av_comparison.png', 'One smooth driver stops the waves. Simulation only, weak drivers.'), ('results/phenomena/capacity_drop_detector.png', 'Flow falls after breakdown at a lane drop, only with deliberately weak drivers.'),
                 ('research/truth/fig/05v2-tournament.png', 'Each model\'s error predicting real drivers. The chosen one sits furthest left.'), ('research/truth/fig/05v2-junction-gap.png', 'Queue release, yellow stop-or-go, and gaps SUMO allows.'), ('research/truth/fig/14-letin-yield.png', 'Let-in by relative speed and gap, plus follower braking.'),
                 ('research/truth/fig/berlin-review-shape.png', 'Share of traffic per hour: real roads, simulation, a travel survey.'), ('research/truth/fig/berlin-review-sumo-vs-cars.png', 'Our simulator tracks published SUMO until 17:00, then stays jammed longer.'),
                 ('research/truth/fig/stockholm-gridlock.png', 'Old 60% run: cars climb to about 51,000, teleports to about 294,000.'), ('research/truth/fig/stockholm-hourly.png', 'Invented departure curves with a cliff at 06:00. Neither is observed.'), ('research/truth/fig/stockholm-lengths.png', 'Random-walk trips are mostly very short.'), ('research/truth/fig/demand-assignment.png', 'Toy model: rerouting everyone never settles, capped rerouting does.'),
                 ('research/truth/fig/maps07/s09_sveaplan_base.png', 'Sveaplan: 11 simulated controllers against 1 real installation.'), ('research/truth/fig/09b-capacity.png', 'Maximum flow by layout, Python model. Batch polling is a smarter signal.')]:
    fig(src, cap)
A.append('<footer><p>Built from the research reports and run logs in the cars repo, with sources listed per claim in <code>report/facts/</code>. Built with <code>scripts/report/build.py</code>.</p><p>Snapshot 1 November 2026, about 01:30 on 2 November. Agents are still running, so numbers on unmerged branches can move.</p></footer></div>')
fig_html = ''.join(f'<figure style="margin:0"><img loading="lazy" src="figures/{n}" {dims(OUT / "figures" / n)} alt="{esc(c)}"><figcaption>{esc(c)}</figcaption></figure>' for n, c in figs_all)
BODY_ALL = '\n'.join(A).replace('{{FIGN}}', str(len(figs_all))).replace('{{FIGS}}', fig_html)

hero = '''<section class="hero"><video autoplay muted loop playsinline poster="phone/hero.jpg" src="phone/hero.mp4"></video><div class="hero-in">
<h1>2.25 million trips. 148&nbsp;seconds.</h1>
<p>One graphics card simulates every car in the public Berlin scenario for a whole day. Then we checked it against real counters, and that scenario holds about half of Berlin's real traffic. This is what we built, what it proves, and what it doesn't prove yet.</p>
<p class="when">The cars simulator, report of 1 November 2026</p></div></section>'''
route = '<nav class="route" aria-label="Chapters"><div class="route-in"><button>Close</button><h3 style="margin:.2rem 0 .8rem">Route</h3>' + ''.join(f'<a href="#{i}"><b>Exit {n}</b>{esc(t)}</a>' for i, n, t in chapters) + '</div></nav>'
bar = '<div class="bar"><div class="bar-in"><div class="bar-title">The report</div><button>Route</button></div><div class="road"><div class="car"></div></div></div>'
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#23272b"><title>The cars simulator: the full report</title><link rel="icon" href="data:,"><style>{CSS}</style></head><body>
{bar}{route}{hero}{BODY_MAIN}{BODY_ALL}<script>{JS}</script></body></html>'''
(OUT / 'index.html').write_text(page)
print('wrote', OUT / 'index.html', len(page) // 1024, 'KB', 'chapters', len(chapters), 'sims', len(sims), 'videos', len(rest), 'figs', len(figs_all))
missing = [p for p in ['phone/hero.mp4', 'phone/hero.jpg', 'phone/berlin_day.mp4', 'phone/berlin_zoom.mp4', 'phone/stockholm_day.mp4'] if not (OUT / p).exists()]
print('missing media:', missing)
