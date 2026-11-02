use crate::{
    net::{Net, vclass_bit},
    router,
    xml::{attr, open},
};
use quick_xml::{
    Reader,
    events::{BytesStart, Event},
};
use rustc_hash::{FxHashMap, FxHasher};
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum CfModel {
    Krauss,
    Idm,
    Acc,
    Cacc,
    /// The automated car of research/truth/09, for coordinated junctions.
    Av,
    Eidm,
}
#[derive(Clone, Debug)]
pub struct VType {
    pub id: String,
    pub vclass: u32,
    pub model: CfModel,
    pub length: f32,
    /// Only for drawing: the engine has no vehicle width.
    pub width: f32,
    pub min_gap: f32,
    pub accel: f32,
    pub decel: f32,
    pub emergency_decel: f32,
    pub apparent_decel: f32,
    pub tau: f32,
    pub sigma: f32,
    pub speed_factor_mean: f32,
    pub speed_factor_dev: f32,
    pub speed_factor_min: f32,
    pub speed_factor_max: f32,
    pub max_speed: f32,
    pub impatience: f32,
    pub lc_strategic: f32,
    pub lc_cooperative: f32,
    pub lc_speed_gain: f32,
    pub lc_keep_right: f32,
    pub lc_assertive: f32,
    pub lc_lookahead_left: f32,
    pub lc_speed_gain_right: f32,
    pub jm_timegap_minor: f32,
    pub headway_time_acc: f32,
    pub glosa: bool,
    pub glosa_range: f32,
    pub params: FxHashMap<String, String>,
}

/// Swedish traffic by distance, 2025, Trafikanalys Korstrackor: cars, light trucks, heavy trucks, buses, motorcycles.
/// Sizes are design values (report 19 fix 16): spacing in a queue stays at 7.5 m.
const SWEDEN: [(&str, f64, f32, f32); 5] =
    [("passenger", 0.81, 4.5, 3.0), ("delivery", 0.12, 5.5, 2.5), ("truck", 0.05, 7.1, 2.5), ("bus", 0.01, 12.0, 2.5), ("motorcycle", 0.01, 2.2, 2.5)];

impl Demand {
    /// Replaces the demand's vTypes by the Swedish fleet, by a hash of the trip. Whatever accel, decel, sigma, tau or
    /// minGap the demand file carried goes with them: those came with no source. A route the class may not drive
    /// keeps a car. Returns trips per class.
    pub fn apply_sweden(&mut self, net: &crate::net::Net) -> Vec<(String, u64)> {
        let base = self.vtypes.len() as u32;
        for (name, _, length, gap) in SWEDEN {
            let mut a = Attrs::default();
            a.insert("id".into(), format!("sweden_{name}"));
            a.insert("vClass".into(), name.into());
            let mut t = VType::parse(&a);
            t.length = length;
            t.min_gap = gap;
            self.vtypes.push(t);
        }
        let mut counts = vec![0u64; SWEDEN.len()];
        for trip in &mut self.trips {
            let u = (u64::from(trip.id).wrapping_add(7).wrapping_mul(0x9E3779B97F4A7C15) >> 32) as f64 / 4294967296.0;
            let (mut k, mut sum) = (0, 0.0);
            for (i, row) in SWEDEN.iter().enumerate() {
                sum += row.1;
                k = i;
                if u < sum {
                    break;
                }
            }
            let bit = self.vtypes[base as usize + k].vclass;
            let passable = self.routes[trip.route as usize].iter().all(|&e| {
                let ed = &net.edges[e as usize];
                (ed.first_lane..ed.first_lane + ed.lane_count).any(|l| net.lanes[l as usize].allow & bit == bit)
            });
            if !passable {
                k = 0;
            }
            trip.vtype = base + k as u32;
            counts[k] += 1;
        }
        SWEDEN.iter().zip(counts).map(|(r, c)| (r.0.to_string(), c)).collect()
    }
}

impl VType {
    fn parse(a: &Attrs) -> Self {
        let class = get(a, "vClass", "passenger");
        let (length, accel, decel, emergency, speed, dev, gap, sigma): (
            f32,
            f32,
            f32,
            f32,
            f32,
            f32,
            f32,
            f32,
        ) = match class {
            "pedestrian" => (0.215, 1.5, 2., 5., 37.58 / 3.6, 0.1, 0.25, 0.5),
            "bicycle" => (1.6, 1.2, 3., 7., 50. / 3.6, 0.1, 0.5, 0.5),
            "scooter" => (1.2, 1.2, 3., 7., 25. / 3.6, 0.1, 0.5, 0.5),
            "moped" => (2.1, 1.1, 7., 10., 60. / 3.6, 0.1, 2.5, 0.5),
            "motorcycle" => (2.2, 6., 10., 10., 200. / 3.6, 0.1, 2.5, 0.5),
            "truck" => (7.1, 1.3, 4., 7., 130. / 3.6, 0.05, 2.5, 0.5),
            "trailer" => (16.5, 1.1, 4., 7., 130. / 3.6, 0.05, 2.5, 0.5),
            "bus" => (12., 1.2, 4., 7., 100. / 3.6, 0., 2.5, 0.5),
            "coach" => (14., 2., 4., 7., 100. / 3.6, 0.05, 2.5, 0.5),
            "tram" => (22., 1., 3., 7., 80. / 3.6, 0., 2.5, 0.),
            "rail_urban" => (109.5, 1., 3., 7., 100. / 3.6, 0., 5., 0.),
            "subway" => (109.5, 2.6, 4.5, 9., 100. / 3.6, 0., 5., 0.5),
            "rail" => (135., 0.25, 1.3, 5., 160. / 3.6, 0., 5., 0.),
            "rail_electric" => (200., 0.5, 1.3, 5., 220. / 3.6, 0., 5., 0.),
            "rail_fast" => (200., 0.5, 1.3, 5., 330. / 3.6, 0., 5., 0.),
            "delivery" => (6.5, 2.6, 4.5, 9., 200. / 3.6, 0.05, 2.5, 0.5),
            "emergency" => (6.5, 2.6, 4.5, 9., 200. / 3.6, 0., 2.5, 0.5),
            "taxi" => (5., 2.6, 4.5, 9., 200. / 3.6, 0.05, 2.5, 0.5),
            "ship" => (17., 0.1, 0.15, 1., 8. / 1.94, 0.1, 2.5, 0.),
            "container" => (6.096, 2.6, 4.5, 9., 200. / 3.6, 0., 2.5, 0.5),
            "drone" => (0.5, 2.6, 4.5, 9., 200. / 3.6, 0., 2.5, 0.5),
            "aircraft" => (72.7, 2.6, 4.5, 9., 200. / 3.6, 0., 2.5, 0.5),
            "authority" | "army" | "cable_car" => (5., 2.6, 4.5, 9., 200. / 3.6, 0., 2.5, 0.5),
            _ => (5., 2.6, 4.5, 9., 200. / 3.6, 0.1, 2.5, 0.5),
        };
        let model = match get(a, "carFollowModel", "Krauss") {
            "IDM" => CfModel::Idm,
            "ACC" => CfModel::Acc,
            "CACC" => CfModel::Cacc,
            "EIDM" => CfModel::Eidm,
            "CarsAV" => CfModel::Av,
            _ => CfModel::Krauss,
        };
        let decel = num(a, "decel", decel);
        let mut t = Self {
            id: get(a, "id", "DEFAULT_VEHTYPE").into(),
            vclass: vclass_bit(class),
            model,
            length,
            width: num(a, "width", match class {
                "pedestrian" => 0.478,
                "bicycle" | "scooter" => 0.65,
                "moped" => 0.78,
                "motorcycle" => 0.9,
                "delivery" | "emergency" => 2.16,
                "truck" | "tram" => 2.4,
                "trailer" | "bus" | "coach" | "subway" | "rail_urban" | "rail" | "rail_electric" | "rail_fast" => 2.55,
                _ => 1.8,
            }),
            min_gap: gap,
            accel,
            decel,
            emergency_decel: num(a, "emergencyDecel", emergency.max(decel)),
            apparent_decel: decel,
            tau: 1.,
            sigma,
            speed_factor_mean: 1.,
            speed_factor_dev: dev,
            speed_factor_min: 0.2,
            speed_factor_max: 2.,
            max_speed: speed,
            impatience: 0.,
            lc_strategic: 1.,
            lc_cooperative: 1.,
            lc_speed_gain: 1.,
            lc_keep_right: 1.,
            lc_assertive: 1.,
            lc_lookahead_left: 2.,
            lc_speed_gain_right: 0.1,
            jm_timegap_minor: 1.,
            headway_time_acc: 1.,
            glosa: false,
            glosa_range: 100.,
            params: FxHashMap::default(),
        };
        t.length = num(a, "length", t.length);
        t.min_gap = num(a, "minGap", t.min_gap);
        t.accel = num(a, "accel", t.accel);
        t.decel = num(a, "decel", t.decel);
        t.emergency_decel = num(a, "emergencyDecel", t.emergency_decel);
        t.apparent_decel = num(a, "apparentDecel", t.apparent_decel);
        t.tau = num(a, "tau", t.tau);
        t.sigma = num(a, "sigma", t.sigma);
        t.speed_factor_mean = num(a, "speedFactorMean", t.speed_factor_mean);
        t.speed_factor_dev = num(a, "speedDev", t.speed_factor_dev);
        t.speed_factor_min = num(a, "speedFactorMin", t.speed_factor_min);
        t.speed_factor_max = num(a, "speedFactorMax", t.speed_factor_max);
        t.max_speed = num(a, "maxSpeed", t.max_speed);
        t.impatience = num(a, "impatience", t.impatience);
        t.lc_strategic = num(a, "lcStrategic", t.lc_strategic);
        t.lc_cooperative = num(a, "lcCooperative", t.lc_cooperative);
        t.lc_speed_gain = num(a, "lcSpeedGain", t.lc_speed_gain);
        t.lc_keep_right = num(a, "lcKeepRight", t.lc_keep_right);
        t.lc_assertive = num(a, "lcAssertive", t.lc_assertive);
        t.lc_lookahead_left = num(a, "lcLookaheadLeft", t.lc_lookahead_left);
        t.lc_speed_gain_right = num(a, "lcSpeedGainRight", t.lc_speed_gain_right);
        t.jm_timegap_minor = num(a, "jmTimegapMinor", t.jm_timegap_minor);
        t.headway_time_acc = num(a, "headwayTimeACC", t.headway_time_acc);
        if let Some(v) = a.get("speedFactor") {
            if let Ok(v) = v.parse() {
                t.speed_factor_mean = v;
            } else if let Some((kind, args)) = v.split_once('(') {
                let values: Vec<f32> = args
                    .trim_end_matches(')')
                    .split(',')
                    .filter_map(|v| v.trim().parse().ok())
                    .collect();
                if values.len() >= 2 {
                    t.speed_factor_mean = values[0];
                    t.speed_factor_dev = values[1];
                }
                if kind == "normc" && values.len() == 4 {
                    t.speed_factor_min = values[2];
                    t.speed_factor_max = values[3];
                }
                if kind == "norm" {
                    t.speed_factor_min = f32::NEG_INFINITY;
                    t.speed_factor_max = f32::INFINITY;
                }
            }
        }
        t.speed_factor_dev = num(a, "speedDev", t.speed_factor_dev);
        t
    }
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum DepartLane {
    First,
    Index(u32),
    Random,
    Free,
    Allowed,
    Best,
    BestProb,
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum DepartPos {
    Base,
    Value(f32),
    Random,
    RandomFree,
    Free,
    Last,
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum DepartSpeed {
    Avg,
    Zero,
    Value(f32),
    Random,
    Max,
    Desired,
    SpeedLimit,
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum ArrivalPos {
    Max,
    Value(f32),
    Random,
}
#[derive(Clone, Debug)]
pub struct Trip {
    pub id: u32,
    pub depart: f64,
    pub route: u32,
    pub vtype: u32,
    pub depart_lane: DepartLane,
    pub depart_pos: DepartPos,
    pub depart_speed: DepartSpeed,
    pub arrival_pos: ArrivalPos,
}
#[derive(Default, Debug)]
pub struct DropCounts {
    pub unknown_edge: u64,
    pub unconnected: u64,
    /// Connected only by connections or lanes the vehicle's class may not use.
    pub banned_connection: u64,
    pub unknown_route: u64,
    pub unknown_vtype: u64,
    pub taz: u64,
    pub after_end: u64,
    pub unsupported_depart: u64,
}
#[derive(Default)]
pub struct Demand {
    pub vtypes: Vec<VType>,
    pub vtype_index: FxHashMap<String, u32>,
    pub routes: Vec<Vec<u32>>,
    pub trips: Vec<Trip>,
    pub ids: Vec<String>,
    pub dropped: DropCounts,
    pub stops_ignored: u64,
    pub persons_ignored: u64,
}
type Attrs = FxHashMap<String, String>;
fn attrs(e: &BytesStart) -> Attrs {
    e.attributes()
        .with_checks(false)
        .flatten()
        .filter_map(|a| {
            let k = std::str::from_utf8(a.key.as_ref()).ok()?.to_string();
            Some((k.clone(), attr(e, &k)?))
        })
        .collect()
}
fn get<'a>(a: &'a Attrs, k: &str, d: &'a str) -> &'a str {
    a.get(k).map(String::as_str).unwrap_or(d)
}
fn num<T: std::str::FromStr>(a: &Attrs, k: &str, d: T) -> T {
    a.get(k).and_then(|v| v.parse().ok()).unwrap_or(d)
}
fn millis(t: f64) -> f64 {
    (t * 1000.).round() / 1000.
}
struct Rng(u64);
impl Rng {
    fn draw(&mut self) -> f64 {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
        ((z ^ (z >> 31)) >> 11) as f64 / (1u64 << 53) as f64
    }
}
#[derive(Clone)]
enum Spec {
    Route(u32),
    Ref(String),
    Od(Vec<u32>),
    Bad(bool),
}
#[derive(Default)]
struct Definitions {
    routes: FxHashMap<String, Spec>,
    rd: FxHashMap<String, Vec<(Spec, f64)>>,
    td: FxHashMap<String, Vec<(String, f64)>>,
    hashes: FxHashMap<u64, Vec<u32>>,
}
impl Definitions {
    fn intern(&mut self, d: &mut Demand, edges: Vec<u32>) -> u32 {
        let mut h = FxHasher::default();
        edges.hash(&mut h);
        let bucket = self.hashes.entry(h.finish()).or_default();
        if let Some(&i) = bucket.iter().find(|&&i| d.routes[i as usize] == edges) {
            return i;
        }
        let i = d.routes.len() as u32;
        d.routes.push(edges);
        bucket.push(i);
        i
    }
    fn resolve(&self, s: &Spec, rng: &mut Rng, depth: usize) -> Option<Spec> {
        if depth > 32 {
            return None;
        }
        match s {
            Spec::Ref(id) => {
                if let Some(v) = self.rd.get(id) {
                    self.resolve(&choose(v, rng)?.0, rng, depth + 1)
                } else {
                    self.resolve(self.routes.get(id)?, rng, depth + 1)
                }
            }
            _ => Some(s.clone()),
        }
    }
    fn type_id(&self, id: &str, rng: &mut Rng, depth: usize) -> Option<String> {
        if depth > 32 {
            return None;
        }
        if let Some(v) = self.td.get(id) {
            self.type_id(&choose(v, rng)?.0, rng, depth + 1)
        } else {
            Some(id.into())
        }
    }
}
fn choose<'a, T>(v: &'a [(T, f64)], rng: &mut Rng) -> Option<&'a (T, f64)> {
    let total: f64 = v.iter().map(|x| x.1.max(0.)).sum();
    if total <= 0. {
        return None;
    }
    let mut r = rng.draw() * total;
    for x in v {
        r -= x.1.max(0.);
        if r < 0. {
            return Some(x);
        }
    }
    v.last()
}
struct Pending {
    a: Attrs,
    spec: Spec,
    flow: bool,
}
impl Demand {
    pub fn summary(&self) -> String {
        format!(
            "{} trips, {} routes, {} vTypes; dropped {:?}; {} stops and {} persons ignored",
            self.trips.len(),
            self.routes.len(),
            self.vtypes.len(),
            self.dropped,
            self.stops_ignored,
            self.persons_ignored
        )
    }
    pub fn load(
        net: &Net,
        files: &[PathBuf],
        additional_vtype_files: &[PathBuf],
        seed: u64,
        end_time: Option<f64>,
    ) -> Result<Self, String> {
        let mut d = Self::default();
        let mut defs = Definitions::default();
        let mut pending = Vec::new();
        d.add_type(VType::parse(&Attrs::default()));
        for p in additional_vtype_files.iter().chain(files) {
            d.parse(net, p, &mut defs, &mut pending)?;
        }
        let mut rng = Rng(seed);
        let mut requests = Vec::new();
        let mut request_trips = Vec::new();
        let mut request_index = FxHashMap::default();
        for p in pending {
            let times = departures(&p.a, p.flow, &mut rng)?;
            for (i, time) in times.into_iter().enumerate() {
                if end_time.is_some_and(|end| time > end) {
                    d.dropped.after_end += 1;
                    continue;
                }
                let Some(tid) = defs.type_id(get(&p.a, "type", "DEFAULT_VEHTYPE"), &mut rng, 0)
                else {
                    d.dropped.unknown_vtype += 1;
                    continue;
                };
                let Some(&vtype) = d.vtype_index.get(&tid) else {
                    d.dropped.unknown_vtype += 1;
                    continue;
                };
                let Some(spec) = defs.resolve(&p.spec, &mut rng, 0) else {
                    d.dropped.unknown_route += 1;
                    continue;
                };
                let route = match spec {
                    Spec::Route(r) => r,
                    Spec::Od(ref w) if w.len() >= 2 => {
                        let key = (
                            w[0],
                            *w.last().unwrap(),
                            w[1..w.len() - 1].to_vec(),
                            d.vtypes[vtype as usize].vclass,
                        );
                        let request = *request_index.entry(key.clone()).or_insert_with(|| {
                            let i = requests.len();
                            requests.push(key);
                            i
                        });
                        request_trips.push((d.trips.len(), request));
                        u32::MAX
                    }
                    Spec::Bad(true) => {
                        d.dropped.unknown_edge += 1;
                        continue;
                    }
                    Spec::Bad(false) => {
                        d.dropped.taz += 1;
                        continue;
                    }
                    _ => {
                        d.dropped.unknown_route += 1;
                        continue;
                    }
                };
                let id = get(&p.a, "id", "");
                let id = if p.flow {
                    format!("{id}.{i}")
                } else {
                    id.into()
                };
                let mut t = procedures(&p.a)?;
                t.id = d.ids.len() as u32;
                t.depart = time;
                t.route = route;
                t.vtype = vtype;
                d.ids.push(id);
                d.trips.push(t);
            }
        }
        let routed: Vec<_> = router::route_many(net, &requests)
            .into_iter()
            .map(|r| r.map(|r| defs.intern(&mut d, r)).unwrap_or(u32::MAX))
            .collect();
        for (index, request) in request_trips {
            d.trips[index].route = routed[request];
        }
        let mut conns: FxHashMap<(u32, u32), u32> = FxHashMap::default();
        for c in &net.conns {
            *conns.entry((c.from_edge, c.to_edge)).or_default() |= net.conn_allow(c);
        }
        let valid: Vec<_> = d
            .routes
            .iter()
            .map(|r| !r.is_empty() && r.windows(2).all(|w| conns.contains_key(&(w[0], w[1]))))
            .collect();
        let mut legal = FxHashMap::default();
        d.trips.retain(|t| {
            if t.route == u32::MAX || !valid[t.route as usize] {
                d.dropped.unconnected += 1;
                return false;
            }
            let class = d.vtypes[t.vtype as usize].vclass;
            let ok = *legal.entry((t.route, class)).or_insert_with(|| {
                d.routes[t.route as usize].windows(2).all(|w| conns[&(w[0], w[1])] & class == class)
            });
            if !ok {
                d.dropped.banned_connection += 1;
            }
            ok
        });
        d.trips.sort_by(|a, b| a.depart.total_cmp(&b.depart));
        Ok(d)
    }
    fn add_type(&mut self, t: VType) {
        if let Some(&i) = self.vtype_index.get(&t.id) {
            self.vtypes[i as usize] = t;
        } else {
            self.vtype_index
                .insert(t.id.clone(), self.vtypes.len() as u32);
            self.vtypes.push(t);
        }
    }
    fn parse(
        &mut self,
        net: &Net,
        path: &Path,
        defs: &mut Definitions,
        pending: &mut Vec<Pending>,
    ) -> Result<(), String> {
        let mut reader = Reader::from_reader(open(path)?);
        let mut buf = Vec::new();
        let mut vehicle: Option<Pending> = None;
        let mut vt: Option<Attrs> = None;
        let mut params = Attrs::default();
        let mut rd: Option<(String, Vec<(Spec, f64)>)> = None;
        let mut td: Option<(String, Vec<(String, f64)>)> = None;
        let mut person_depth = 0u32;
        loop {
            let ev = reader
                .read_event_into(&mut buf)
                .map_err(|e| format!("{}: {e}", path.display()))?;
            match &ev {
                Event::Start(e) | Event::Empty(e) => {
                    let tag = e.local_name();
                    let tag = tag.as_ref();
                    let empty = matches!(ev, Event::Empty(_));
                    if tag == b"person" || tag == b"personFlow" {
                        self.persons_ignored += 1;
                        if !empty {
                            person_depth += 1;
                        }
                    } else if person_depth > 0 {
                        if tag == b"stop" {
                            self.stops_ignored += 1;
                        }
                    } else {
                        let a = attrs(e);
                        match tag {
                            b"vehicle" | b"trip" | b"flow" => {
                                let spec = if let Some(r) = a.get("route") {
                                    Spec::Ref(r.clone())
                                } else {
                                    waypoints(net, &a)
                                };
                                let p = Pending {
                                    a,
                                    spec,
                                    flow: tag == b"flow",
                                };
                                if empty {
                                    pending.push(p)
                                } else {
                                    vehicle = Some(p)
                                }
                            }
                            b"vType" => {
                                if let Some((_, v)) = &mut td {
                                    v.push((get(&a, "id", "").into(), num(&a, "probability", 1.)));
                                }
                                if empty {
                                    self.add_type(VType::parse(&a));
                                } else {
                                    vt = Some(a);
                                    params.clear();
                                }
                            }
                            b"vTypeDistribution" => {
                                let names = get(&a, "vTypes", "").split_whitespace();
                                let weights: Vec<f64> = get(&a, "probabilities", "")
                                    .split_whitespace()
                                    .filter_map(|x| x.parse().ok())
                                    .collect();
                                let v = names
                                    .enumerate()
                                    .map(|(i, n)| (n.into(), weights.get(i).copied().unwrap_or(1.)))
                                    .collect();
                                let id: String = get(&a, "id", "").into();
                                if empty {
                                    defs.td.insert(id, v);
                                } else {
                                    td = Some((id, v));
                                }
                            }
                            b"routeDistribution" => {
                                let id: String = a
                                    .get("id")
                                    .cloned()
                                    .unwrap_or_else(|| format!("@distribution:{}", defs.rd.len()));
                                let weights: Vec<f64> = get(&a, "probabilities", "")
                                    .split_whitespace()
                                    .filter_map(|x| x.parse().ok())
                                    .collect();
                                let v = get(&a, "routes", "")
                                    .split_whitespace()
                                    .enumerate()
                                    .map(|(i, n)| {
                                        (Spec::Ref(n.into()), weights.get(i).copied().unwrap_or(1.))
                                    })
                                    .collect();
                                if let Some(p) = &mut vehicle {
                                    p.spec = Spec::Ref(id.clone());
                                }
                                if empty {
                                    defs.rd.insert(id, v);
                                } else {
                                    rd = Some((id, v));
                                }
                            }
                            b"route" => {
                                let spec = if let Some(r) = a.get("refId") {
                                    Spec::Ref(r.clone())
                                } else {
                                    let edges: Option<Vec<u32>> = get(&a, "edges", "")
                                        .split_whitespace()
                                        .map(|s| net.edge_index.get(s).copied())
                                        .collect();
                                    match edges {
                                        Some(e) => {
                                            let n = num(&a, "repeat", 0usize)
                                                .checked_add(1)
                                                .ok_or("route repeat overflow")?;
                                            Spec::Route(defs.intern(self, e.repeat(n)))
                                        }
                                        None => Spec::Bad(true),
                                    }
                                };
                                if let Some((_, v)) = &mut rd {
                                    v.push((spec, num(&a, "probability", 1.)));
                                } else if let Some(p) = &mut vehicle {
                                    p.spec = spec;
                                } else if let Some(id) = a.get("id") {
                                    defs.routes.insert(id.clone(), spec);
                                }
                            }
                            b"stop" => self.stops_ignored += 1,
                            b"param" => {
                                if vt.is_some() {
                                    params.insert(
                                        get(&a, "key", "").into(),
                                        get(&a, "value", "").into(),
                                    );
                                }
                            }
                            _ => {
                                if tag.starts_with(b"carFollowing-") {
                                    if let Some(v) = &mut vt {
                                        v.extend(a);
                                        v.insert(
                                            "carFollowModel".into(),
                                            String::from_utf8_lossy(&tag[13..]).into(),
                                        );
                                    }
                                }
                            }
                        }
                    }
                }
                Event::End(e) => match e.local_name().as_ref() {
                    b"person" | b"personFlow" => person_depth = person_depth.saturating_sub(1),
                    b"vehicle" | b"trip" | b"flow" if person_depth == 0 => {
                        if let Some(v) = vehicle.take() {
                            pending.push(v);
                        }
                    }
                    b"vType" => {
                        if let Some(a) = vt.take() {
                            let mut t = VType::parse(&a);
                            t.glosa =
                                matches!(get(&params, "has.glosa.device", "false"), "true" | "1");
                            t.glosa_range = num(&params, "device.glosa.range", 100.);
                            t.params = std::mem::take(&mut params);
                            self.add_type(t);
                        }
                    }
                    b"routeDistribution" => {
                        if let Some((id, v)) = rd.take() {
                            defs.rd.insert(id, v);
                        }
                    }
                    b"vTypeDistribution" => {
                        if let Some((id, v)) = td.take() {
                            defs.td.insert(id, v);
                        }
                    }
                    _ => {}
                },
                Event::Eof => break,
                _ => {}
            }
            buf.clear();
        }
        Ok(())
    }
}
fn waypoints(net: &Net, a: &Attrs) -> Spec {
    if a.contains_key("fromTaz") || a.contains_key("toTaz") {
        return Spec::Bad(false);
    }
    let names = std::iter::once(get(a, "from", ""))
        .chain(get(a, "via", "").split_whitespace())
        .chain(std::iter::once(get(a, "to", "")));
    match names
        .map(|n| net.edge_index.get(n).copied())
        .collect::<Option<Vec<_>>>()
    {
        Some(v) => Spec::Od(v),
        None => Spec::Bad(true),
    }
}
fn departures(a: &Attrs, flow: bool, rng: &mut Rng) -> Result<Vec<f64>, String> {
    if !flow {
        return Ok(vec![millis(
            get(a, "depart", "0")
                .parse()
                .map_err(|_| "unsupported departure time")?,
        )]);
    }
    let begin = num(a, "begin", 0.);
    let end = num(a, "end", begin + 86400.);
    let number = num(a, "number", usize::MAX);
    if number == 0 {
        return Ok(Vec::new());
    }
    let prob = num(a, "probability", -1.);
    let period = get(a, "period", "");
    let exp = period
        .strip_prefix("exp(")
        .and_then(|s| s.strip_suffix(')'))
        .and_then(|s| s.parse::<f64>().ok());
    let rate = num(a, "vehsPerHour", num(a, "perHour", 0.));
    let step = millis(if rate > 0. {
        3600. / rate
    } else {
        period
            .parse()
            .unwrap_or(((millis(end) - millis(begin)) * 1000. / number as f64).floor() / 1000.)
    });
    if !begin.is_finite()
        || !end.is_finite()
        || end < begin
        || (a.contains_key("probability") && !(0. ..=1.).contains(&prob))
        || exp.is_some_and(|r| !r.is_finite() || r <= 0.)
        || (prob < 0. && exp.is_none() && step <= 0.)
    {
        return Err("invalid flow timing".into());
    }
    let mut times = Vec::new();
    let mut t = millis(begin);
    while times.len() < number
        && (t < end || (prob < 0. && a.contains_key("number") && !a.contains_key("end")))
    {
        if prob < 0. || rng.draw() < prob {
            times.push(t);
        }
        t = millis(
            t + if prob >= 0. {
                1.
            } else if let Some(rate) = exp {
                if rate <= 0. {
                    return Err("invalid exponential rate".into());
                }
                millis(-(1. - rng.draw()).ln() / rate)
            } else {
                step
            },
        );
    }
    Ok(times)
}
fn procedures(a: &Attrs) -> Result<Trip, String> {
    let lane = match get(a, "departLane", "best_prob") {
        "first" => DepartLane::First,
        "random" => DepartLane::Random,
        "free" => DepartLane::Free,
        "allowed" => DepartLane::Allowed,
        "best" => DepartLane::Best,
        "best_prob" => DepartLane::BestProb,
        v => DepartLane::Index(v.parse().map_err(|_| "invalid departLane")?),
    };
    let pos = match get(a, "departPos", "base") {
        "base" => DepartPos::Base,
        "random" => DepartPos::Random,
        "random_free" => DepartPos::RandomFree,
        "free" => DepartPos::Free,
        "last" => DepartPos::Last,
        v => DepartPos::Value(v.parse().map_err(|_| "invalid departPos")?),
    };
    let speed = match get(a, "departSpeed", "avg") {
        "avg" => DepartSpeed::Avg,
        "0" => DepartSpeed::Zero,
        "random" => DepartSpeed::Random,
        "max" => DepartSpeed::Max,
        "desired" => DepartSpeed::Desired,
        "speedLimit" => DepartSpeed::SpeedLimit,
        v => DepartSpeed::Value(v.parse().map_err(|_| "invalid departSpeed")?),
    };
    let arrival = match get(a, "arrivalPos", "max") {
        "max" => ArrivalPos::Max,
        "random" => ArrivalPos::Random,
        v => ArrivalPos::Value(v.parse().map_err(|_| "invalid arrivalPos")?),
    };
    Ok(Trip {
        id: 0,
        depart: 0.,
        route: 0,
        vtype: 0,
        depart_lane: lane,
        depart_pos: pos,
        depart_speed: speed,
        arrival_pos: arrival,
    })
}
