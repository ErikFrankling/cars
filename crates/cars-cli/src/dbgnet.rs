//! The net as the debugging tools read it, in the numbering of a trace and a `.why` file. Also hands
//! `cars why` and its siblings to scripts/cars_debug.py, where the analysis lives.
use cars_core::{
    demand::Demand,
    net::{EdgeFunc, Net},
    world::{SimConfig, World},
};
use clap::Parser;
use serde::Serialize;
use std::{
    io::{BufRead, Write},
    path::{Path, PathBuf},
};

#[derive(Parser)]
pub struct Args {
    #[arg(long)]
    net: PathBuf,
    #[arg(long, value_delimiter = ',')]
    additional: Vec<PathBuf>,
    #[arg(long)]
    out: PathBuf,
}

#[derive(Parser)]
#[command(disable_help_flag = true)]
pub struct Forward {
    #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
    args: Vec<String>,
}

pub fn forward(tool: &str, a: Forward) {
    let script = std::env::var("CARS_SCRIPTS").map(PathBuf::from).unwrap_or_else(|_| Path::new(env!("CARGO_MANIFEST_DIR")).join("../../scripts")).join("cars_debug.py");
    let status = std::process::Command::new("python3").arg(script).arg(tool).args(&a.args).status();
    match status {
        Ok(s) => std::process::exit(s.code().unwrap_or(1)),
        Err(e) => {
            eprintln!("python3: {e}");
            std::process::exit(1);
        }
    }
}

#[derive(Serialize, Default)]
struct Lanes<'a> {
    id: Vec<&'a str>,
    edge: Vec<u32>,
    index: Vec<u32>,
    length: Vec<f32>,
    speed: Vec<f32>,
    internal: Vec<u8>,
    links_start: Vec<u32>,
    links_count: Vec<u32>,
    x0: Vec<f32>,
    y0: Vec<f32>,
    x1: Vec<f32>,
    y1: Vec<f32>,
}
#[derive(Serialize, Default)]
struct Edges<'a> {
    id: Vec<&'a str>,
    func: Vec<&'static str>,
    from: Vec<&'a str>,
    to: Vec<&'a str>,
    first_lane: Vec<u32>,
    lane_count: Vec<u32>,
    road: Vec<String>,
}
#[derive(Serialize, Default)]
struct Links {
    from_lane: Vec<u32>,
    next_lane: Vec<u32>,
    to_lane: Vec<u32>,
    to_edge: Vec<u32>,
    flags: Vec<u32>,
    tl: Vec<u32>,
    tl_index: Vec<u32>,
    state: Vec<u32>,
    length: Vec<f32>,
}
#[derive(Serialize, Default)]
struct Junctions<'a> {
    id: Vec<&'a str>,
    jtype: Vec<&'a str>,
    x: Vec<f32>,
    y: Vec<f32>,
}
#[derive(Serialize)]
struct Doc<'a> {
    lanes: Lanes<'a>,
    edges: Edges<'a>,
    links: Links,
    junctions: Junctions<'a>,
    tls: Vec<&'a str>,
}

/// `type` of each edge, read straight from the file because the simulation does not need it.
fn road_types(path: &Path) -> Result<std::collections::HashMap<String, String>, String> {
    let mut out = std::collections::HashMap::new();
    let reader = cars_core::xml::open(path)?;
    for line in reader.lines() {
        let line = line.map_err(|e| e.to_string())?;
        let t = line.trim_start();
        if !t.starts_with("<edge ") {
            continue;
        }
        let value = |name: &str| t.split_once(&format!(" {name}=\"")).and_then(|(_, r)| r.split_once('"')).map(|(v, _)| v.to_string());
        if let (Some(id), Some(ty)) = (value("id"), value("type")) {
            out.insert(id, ty);
        }
    }
    Ok(out)
}

pub fn write(out: &Path, net_path: &Path, net: &Net, world: &World) -> Result<(), String> {
    let roads = road_types(net_path)?;
    let mut lanes = Lanes::default();
    for (i, l) in net.lanes.iter().enumerate() {
        let g = &world.lanes[i];
        lanes.id.push(&l.id);
        lanes.edge.push(l.edge);
        lanes.index.push(l.index);
        lanes.length.push(l.length);
        lanes.speed.push(l.speed);
        lanes.internal.push((g.flags & 1) as u8);
        lanes.links_start.push(g.links_start);
        lanes.links_count.push(g.links_count);
        let (a, b) = (l.shape.first().copied().unwrap_or([0.0, 0.0]), l.shape.last().copied().unwrap_or([0.0, 0.0]));
        lanes.x0.push(a[0]);
        lanes.y0.push(a[1]);
        lanes.x1.push(b[0]);
        lanes.y1.push(b[1]);
    }
    let mut edges = Edges::default();
    for e in &net.edges {
        edges.id.push(&e.id);
        edges.func.push(match e.func {
            EdgeFunc::Normal => "normal",
            EdgeFunc::Internal => "internal",
            EdgeFunc::Connector => "connector",
            EdgeFunc::Pedestrian => "pedestrian",
        });
        edges.from.push(&e.from);
        edges.to.push(&e.to);
        edges.first_lane.push(e.first_lane);
        edges.lane_count.push(e.lane_count);
        edges.road.push(roads.get(&e.id).cloned().unwrap_or_default());
    }
    let mut links = Links::default();
    for k in &world.links {
        links.from_lane.push(k.from_lane);
        links.next_lane.push(k.next_lane);
        links.to_lane.push(k.to_lane);
        links.to_edge.push(k.to_edge);
        links.flags.push(k.flags);
        links.tl.push(k.tl);
        links.tl_index.push(k.tl_index);
        links.state.push(k.state);
        links.length.push(k.length);
    }
    let mut junctions = Junctions::default();
    for j in &net.junctions {
        junctions.id.push(&j.id);
        junctions.jtype.push(&j.jtype);
        junctions.x.push(j.x);
        junctions.y.push(j.y);
    }
    let doc = Doc { lanes, edges, links, junctions, tls: net.tls.iter().map(|t| t.id.as_str()).collect() };
    let file = std::fs::File::create(out).map_err(|e| format!("{}: {e}", out.display()))?;
    let mut w = std::io::BufWriter::with_capacity(1 << 20, file);
    serde_json::to_writer(&mut w, &doc).map_err(|e| e.to_string())?;
    w.flush().map_err(|e| e.to_string())
}

pub fn run(a: Args) -> Result<(), String> {
    let mut net = Net::load(&a.net)?;
    for f in &a.additional {
        net.load_additional(f)?;
    }
    let demand = Demand::load(&net, &[], &a.additional, 0, Some(0.0))?;
    let world = World::build(&net, &demand, &SimConfig { dt: 1.0, end_seconds: 1.0, ..Default::default() }, &[]);
    write(&a.out, &a.net, &net, &world)
}
