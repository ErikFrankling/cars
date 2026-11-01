//! Reads SUMO `.net.xml` files (and `tlLogic` overrides from additional files).

use std::path::Path;

use quick_xml::Reader;
use quick_xml::events::{BytesStart, Event};
use rustc_hash::FxHashMap;

use crate::xml::{attr, attr_f32, attr_f64, open, parse_shape};

/// Bit per vehicle class, in SUMO's naming. Lanes store a mask of allowed classes.
pub const VCLASSES: &[&str] = &[
    "private", "emergency", "authority", "army", "vip", "pedestrian", "passenger", "hov", "taxi",
    "bus", "coach", "delivery", "truck", "trailer", "motorcycle", "moped", "bicycle", "evehicle",
    "tram", "rail_urban", "rail", "rail_electric", "rail_fast", "ship", "custom1", "custom2",
    "scooter", "drone", "container", "cable_car", "subway", "aircraft",
];

pub fn vclass_bit(name: &str) -> u32 {
    // Old style names look like "passenger/van".
    let base = name.split('/').next().unwrap_or(name);
    VCLASSES
        .iter()
        .position(|c| *c == base)
        .map(|i| 1u32 << i)
        .unwrap_or(0)
}

pub fn vclass_mask(list: &str) -> u32 {
    let mut mask = 0;
    for name in list.split_ascii_whitespace() {
        if name == "all" {
            return u32::MAX;
        }
        mask |= vclass_bit(name);
    }
    mask
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EdgeFunc {
    Normal,
    Internal,
    Connector,
    /// Crossing and walking areas. Kept out of the vehicle network.
    Pedestrian,
}

#[derive(Clone, Debug)]
pub struct Edge {
    pub id: String,
    pub func: EdgeFunc,
    pub from: String,
    pub to: String,
    pub first_lane: u32,
    pub lane_count: u32,
}

#[derive(Clone, Debug)]
pub struct Lane {
    pub id: String,
    pub edge: u32,
    pub index: u32,
    pub speed: f32,
    pub length: f32,
    pub width: f32,
    pub allow: u32,
    pub change_left: u32,
    pub change_right: u32,
    pub shape: Vec<[f32; 2]>,
    /// Height gained from start to end, where the net has heights.
    pub z_rise: f32,
}

#[derive(Clone, Debug)]
pub struct Conn {
    pub from_edge: u32,
    pub from_lane: u32,
    pub to_edge: u32,
    pub to_lane: u32,
    /// Internal lane through the junction, if the net has them.
    pub via: Option<u32>,
    pub tl: Option<u32>,
    pub link_index: i32,
    pub dir: u8,
    pub state: u8,
    pub keep_clear: bool,
    pub visibility: f32,
}

#[derive(Clone, Debug)]
pub struct Request {
    pub index: u32,
    /// SUMO prints the bits with the highest link index first.
    pub response: Vec<bool>,
    pub foes: Vec<bool>,
    pub cont: bool,
}

#[derive(Clone, Debug)]
pub struct Junction {
    pub id: String,
    pub jtype: String,
    pub x: f32,
    pub y: f32,
    pub inc_lanes: Vec<String>,
    pub int_lanes: Vec<String>,
    pub requests: Vec<Request>,
    pub shape: Vec<[f32; 2]>,
}

#[derive(Clone, Debug)]
pub struct Phase {
    pub duration: f32,
    pub min_dur: f32,
    pub max_dur: f32,
    pub state: Vec<u8>,
}

#[derive(Clone, Debug)]
pub struct TlsLogic {
    pub id: String,
    pub tl_type: String,
    pub program: String,
    pub offset: f32,
    pub phases: Vec<Phase>,
    pub params: FxHashMap<String, String>,
}

#[derive(Default)]
pub struct Net {
    pub edges: Vec<Edge>,
    pub lanes: Vec<Lane>,
    pub conns: Vec<Conn>,
    pub junctions: Vec<Junction>,
    pub tls: Vec<TlsLogic>,
    pub edge_index: FxHashMap<String, u32>,
    pub lane_index: FxHashMap<String, u32>,
    pub tls_index: FxHashMap<String, u32>,
    pub junction_index: FxHashMap<String, u32>,
    pub bounds: [f32; 4],
    pub roundabout_edges: Vec<u32>,
}

fn bits(s: &str) -> Vec<bool> {
    // Reversed so that bits[i] talks about link index i.
    s.bytes().rev().map(|b| b == b'1').collect()
}

impl Net {
    pub fn load(path: &Path) -> Result<Self, String> {
        let mut net = Net::default();
        let mut pending_conns: Vec<PendingConn> = Vec::new();
        net.parse(path, &mut pending_conns)?;
        for c in pending_conns {
            net.add_conn(c);
        }
        net.compute_bounds();
        Ok(net)
    }

    /// Load `tlLogic` programs from an additional file. A later program replaces an earlier one,
    /// which is what SUMO does when it switches to the last program loaded.
    pub fn load_additional(&mut self, path: &Path) -> Result<(), String> {
        let mut pending = Vec::new();
        self.parse(path, &mut pending)
    }

    fn parse(&mut self, path: &Path, conns: &mut Vec<PendingConn>) -> Result<(), String> {
        let mut reader = Reader::from_reader(open(path)?);
        let mut buf = Vec::with_capacity(1 << 16);
        let mut current_edge: Option<u32> = None;
        let mut current_junction: Option<usize> = None;
        let mut current_tls: Option<TlsLogic> = None;
        loop {
            let ev = reader
                .read_event_into(&mut buf)
                .map_err(|e| format!("{}: {e}", path.display()))?;
            match &ev {
                Event::Start(e) | Event::Empty(e) => match e.local_name().as_ref() {
                    b"edge" => current_edge = self.start_edge(e),
                    b"lane" => {
                        if let Some(edge) = current_edge {
                            self.add_lane(e, edge);
                        }
                    }
                    b"junction" => current_junction = self.add_junction(e),
                    b"request" => {
                        if let Some(j) = current_junction {
                            self.junctions[j].requests.push(Request {
                                index: attr(e, "index").and_then(|v| v.parse().ok()).unwrap_or(0),
                                response: bits(&attr(e, "response").unwrap_or_default()),
                                foes: bits(&attr(e, "foes").unwrap_or_default()),
                                cont: attr(e, "cont").is_some_and(|c| c == "1"),
                            });
                        }
                    }
                    b"roundabout" => {
                        if let Some(list) = attr(e, "edges") {
                            for id in list.split_ascii_whitespace() {
                                if let Some(&ei) = self.edge_index.get(id) {
                                    self.roundabout_edges.push(ei);
                                }
                            }
                        }
                    }
                    b"connection" => {
                        if let Some(c) = PendingConn::from(e) {
                            conns.push(c);
                        }
                    }
                    b"tlLogic" => {
                        current_tls = Some(TlsLogic {
                            id: attr(e, "id").unwrap_or_default(),
                            tl_type: attr(e, "type").unwrap_or_else(|| "static".into()),
                            program: attr(e, "programID").unwrap_or_default(),
                            offset: attr_f32(e, "offset").unwrap_or(0.0),
                            phases: Vec::new(),
                            params: FxHashMap::default(),
                        });
                    }
                    b"phase" => {
                        if let Some(t) = &mut current_tls {
                            let duration = attr_f32(e, "duration").unwrap_or(0.0);
                            t.phases.push(Phase {
                                duration,
                                min_dur: attr_f32(e, "minDur").unwrap_or(duration),
                                max_dur: attr_f32(e, "maxDur").unwrap_or(duration),
                                state: attr(e, "state").unwrap_or_default().into_bytes(),
                            });
                        }
                    }
                    b"param" => {
                        if let Some(t) = &mut current_tls
                            && let (Some(k), Some(v)) = (attr(e, "key"), attr(e, "value"))
                        {
                            t.params.insert(k, v);
                        }
                    }
                    _ => {}
                },
                Event::End(e) => match e.local_name().as_ref() {
                    b"edge" => current_edge = None,
                    b"junction" => current_junction = None,
                    b"tlLogic" => {
                        if let Some(t) = current_tls.take() {
                            self.add_tls(t);
                        }
                    }
                    _ => {}
                },
                Event::Eof => break,
                _ => {}
            }
            // A self-closed tlLogic has no phases and no effect.
            buf.clear();
        }
        Ok(())
    }

    fn start_edge(&mut self, e: &BytesStart) -> Option<u32> {
        let id = attr(e, "id")?;
        let func = match attr(e, "function").as_deref() {
            Some("internal") => EdgeFunc::Internal,
            Some("connector") => EdgeFunc::Connector,
            Some("crossing") | Some("walkingarea") => EdgeFunc::Pedestrian,
            _ => EdgeFunc::Normal,
        };
        let index = self.edges.len() as u32;
        self.edge_index.insert(id.clone(), index);
        self.edges.push(Edge {
            id,
            func,
            from: attr(e, "from").unwrap_or_default(),
            to: attr(e, "to").unwrap_or_default(),
            first_lane: self.lanes.len() as u32,
            lane_count: 0,
        });
        Some(index)
    }

    fn add_lane(&mut self, e: &BytesStart, edge: u32) {
        let Some(id) = attr(e, "id") else { return };
        let allow = match (attr(e, "allow"), attr(e, "disallow")) {
            (Some(a), _) => vclass_mask(&a),
            (None, Some(d)) => !vclass_mask(&d),
            (None, None) => u32::MAX,
        };
        let index = self.lanes.len() as u32;
        self.lane_index.insert(id.clone(), index);
        self.lanes.push(Lane {
            id,
            edge,
            index: attr(e, "index").and_then(|v| v.parse().ok()).unwrap_or(0),
            speed: attr_f32(e, "speed").unwrap_or(13.89),
            length: attr_f32(e, "length").unwrap_or(0.1),
            width: attr_f32(e, "width").unwrap_or(3.2),
            allow,
            change_left: attr(e, "changeLeft").map(|s| vclass_mask(&s)).unwrap_or(u32::MAX),
            change_right: attr(e, "changeRight").map(|s| vclass_mask(&s)).unwrap_or(u32::MAX),
            z_rise: attr(e, "shape").map(|s| crate::xml::shape_rise(&s)).unwrap_or(0.0),
            shape: attr(e, "shape").map(|s| parse_shape(&s)).unwrap_or_default(),
        });
        self.edges[edge as usize].lane_count += 1;
    }

    fn add_junction(&mut self, e: &BytesStart) -> Option<usize> {
        let split = |s: Option<String>| -> Vec<String> {
            s.map(|v| v.split_ascii_whitespace().map(String::from).collect())
                .unwrap_or_default()
        };
        let id = attr(e, "id")?;
        self.junction_index
            .insert(id.clone(), self.junctions.len() as u32);
        self.junctions.push(Junction {
            id,
            jtype: attr(e, "type").unwrap_or_default(),
            x: attr_f64(e, "x").unwrap_or(0.0) as f32,
            y: attr_f64(e, "y").unwrap_or(0.0) as f32,
            inc_lanes: split(attr(e, "incLanes")),
            int_lanes: split(attr(e, "intLanes")),
            requests: Vec::new(),
            shape: attr(e, "shape").map(|s| parse_shape(&s)).unwrap_or_default(),
        });
        Some(self.junctions.len() - 1)
    }

    fn add_tls(&mut self, logic: TlsLogic) {
        if logic.phases.is_empty() {
            return;
        }
        match self.tls_index.get(&logic.id) {
            Some(&i) => self.tls[i as usize] = logic,
            None => {
                self.tls_index
                    .insert(logic.id.clone(), self.tls.len() as u32);
                self.tls.push(logic);
            }
        }
    }

    fn add_conn(&mut self, c: PendingConn) {
        let (Some(&from_edge), Some(&to_edge)) =
            (self.edge_index.get(&c.from), self.edge_index.get(&c.to))
        else {
            return;
        };
        if self.edges[from_edge as usize].func == EdgeFunc::Pedestrian
            || self.edges[to_edge as usize].func == EdgeFunc::Pedestrian
        {
            return;
        }
        let via = c.via.as_ref().and_then(|v| self.lane_index.get(v).copied());
        let tl = c.tl.as_ref().and_then(|t| self.tls_index.get(t).copied());
        self.conns.push(Conn {
            from_edge,
            from_lane: c.from_lane,
            to_edge,
            to_lane: c.to_lane,
            via,
            tl,
            link_index: c.link_index,
            dir: c.dir,
            state: c.state,
            keep_clear: c.keep_clear,
            visibility: c.visibility,
        });
    }

    fn compute_bounds(&mut self) {
        let mut b = [f32::MAX, f32::MAX, f32::MIN, f32::MIN];
        for l in &self.lanes {
            for p in &l.shape {
                b[0] = b[0].min(p[0]);
                b[1] = b[1].min(p[1]);
                b[2] = b[2].max(p[0]);
                b[3] = b[3].max(p[1]);
            }
        }
        self.bounds = b;
    }

    pub fn is_internal_lane(&self, lane: u32) -> bool {
        let e = self.lanes[lane as usize].edge;
        self.edges[e as usize].func == EdgeFunc::Internal
    }

    /// Lane by edge and the lane index inside that edge.
    pub fn lane_of(&self, edge: u32, index: u32) -> Option<u32> {
        let e = &self.edges[edge as usize];
        (index < e.lane_count).then_some(e.first_lane + index)
    }
}

struct PendingConn {
    from: String,
    to: String,
    from_lane: u32,
    to_lane: u32,
    via: Option<String>,
    tl: Option<String>,
    link_index: i32,
    dir: u8,
    state: u8,
    keep_clear: bool,
    visibility: f32,
}

impl PendingConn {
    fn from(e: &BytesStart) -> Option<Self> {
        Some(Self {
            from: attr(e, "from")?,
            to: attr(e, "to")?,
            from_lane: attr(e, "fromLane")?.parse().ok()?,
            to_lane: attr(e, "toLane")?.parse().ok()?,
            via: attr(e, "via"),
            tl: attr(e, "tl"),
            link_index: attr(e, "linkIndex").and_then(|v| v.parse().ok()).unwrap_or(-1),
            dir: attr(e, "dir").and_then(|d| d.bytes().next()).unwrap_or(b's'),
            state: attr(e, "state").and_then(|d| d.bytes().next()).unwrap_or(b'M'),
            keep_clear: attr(e, "keepClear").is_none_or(|k| k != "0" && k != "false"),
            visibility: attr_f32(e, "visibility").unwrap_or(4.5),
        })
    }
}
