//! Which junctions are worth looking at: busiest of each kind, with ids and coordinates.
use cars_core::net::{EdgeFunc, Net};
use clap::Parser;
use std::{collections::HashMap, path::PathBuf};

#[derive(Parser)]
pub struct Args {
    #[arg(long)]
    net: PathBuf,
    /// `cars run --edge-csv` output. Ranks by vehicles entering; without it, by incoming lanes.
    #[arg(long)]
    edge_csv: Option<PathBuf>,
    /// Count only edge data from intervals starting in this range, seconds: from,to.
    #[arg(long, value_delimiter = ',', num_args = 2)]
    window: Vec<f64>,
    /// signal, priority, roundabout, zipper, ramp, allway or rbl. Every kind by default.
    #[arg(long = "type", value_delimiter = ',')]
    types: Vec<String>,
    /// How many of each kind.
    #[arg(long, default_value_t = 10)]
    limit: usize,
    #[arg(long)]
    json: bool,
}

struct Row {
    kind: &'static str,
    id: String,
    x: f32,
    y: f32,
    lanes: usize,
    links: usize,
    score: f64,
}

fn edge_weights(a: &Args) -> Result<HashMap<String, f64>, String> {
    let mut out = HashMap::new();
    let Some(path) = &a.edge_csv else {
        return Ok(out);
    };
    let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut lines = text.lines();
    let header: Vec<&str> = lines.next().unwrap_or("").split(',').collect();
    let column = |name: &str| header.iter().position(|h| *h == name);
    let (begin, edge) = (column("begin").ok_or("no begin column")?, column("edge").ok_or("no edge column")?);
    let weight = column("entered").or(column("samples")).ok_or("no entered or samples column")?;
    for line in lines {
        let f: Vec<&str> = line.split(',').collect();
        if f.len() <= weight {
            continue;
        }
        let t: f64 = f[begin].parse().unwrap_or(0.0);
        if a.window.len() == 2 && (t < a.window[0] || t >= a.window[1]) {
            continue;
        }
        *out.entry(f[edge].to_string()).or_insert(0.0) += f[weight].parse::<f64>().unwrap_or(0.0);
    }
    Ok(out)
}

pub fn run(a: Args) -> Result<(), String> {
    let net = Net::load(&a.net)?;
    let weights = edge_weights(&a)?;
    let mut incoming: HashMap<&str, Vec<u32>> = HashMap::new();
    let mut outgoing: HashMap<&str, Vec<u32>> = HashMap::new();
    for (i, e) in net.edges.iter().enumerate() {
        if e.func == EdgeFunc::Normal {
            incoming.entry(e.to.as_str()).or_default().push(i as u32);
            outgoing.entry(e.from.as_str()).or_default().push(i as u32);
        }
    }
    let mut rows = Vec::new();
    for j in &net.junctions {
        let empty = Vec::new();
        let inc = incoming.get(j.id.as_str()).unwrap_or(&empty);
        let out = outgoing.get(j.id.as_str()).unwrap_or(&empty);
        if inc.is_empty() || j.jtype == "internal" || j.jtype == "dead_end" {
            continue;
        }
        let speed = inc
            .iter()
            .chain(out)
            .map(|&e| net.lanes[net.edges[e as usize].first_lane as usize].speed)
            .fold(0.0, f32::max);
        let contested = j.requests.iter().any(|r| r.foes.iter().any(|f| *f));
        let kind = if inc.iter().any(|e| net.roundabout_edges.contains(e)) {
            "roundabout"
        } else if j.jtype.starts_with("traffic_light") {
            "signal"
        } else if j.jtype == "zipper" {
            "zipper"
        } else if speed >= 19.4 && ((inc.len() >= 2 && out.len() == 1) || (inc.len() == 1 && out.len() >= 2)) {
            "ramp"
        } else if j.jtype == "allway_stop" {
            "allway"
        } else if j.jtype.starts_with("right_before_left") {
            "rbl"
        } else if j.jtype.starts_with("priority") && contested {
            "priority"
        } else {
            continue;
        };
        let lanes: usize = inc.iter().map(|&e| net.edges[e as usize].lane_count as usize).sum();
        let score = if a.edge_csv.is_some() {
            inc.iter().map(|&e| weights.get(&net.edges[e as usize].id).copied().unwrap_or(0.0)).sum()
        } else {
            lanes as f64
        };
        rows.push(Row { kind, id: j.id.clone(), x: j.x, y: j.y, lanes, links: j.requests.len(), score });
    }
    rows.sort_by(|p, q| q.score.total_cmp(&p.score).then_with(|| p.id.cmp(&q.id)));
    let mut seen: HashMap<&str, usize> = HashMap::new();
    let keep: Vec<&Row> = rows
        .iter()
        .filter(|r| a.types.is_empty() || a.types.iter().any(|t| t == r.kind))
        .filter(|r| {
            let n = seen.entry(r.kind).or_insert(0);
            *n += 1;
            *n <= a.limit
        })
        .collect();
    if a.json {
        let list: Vec<_> = keep
            .iter()
            .map(|r| serde_json::json!({"id": r.id, "type": r.kind, "x": r.x, "y": r.y, "lanes": r.lanes, "links": r.links, "score": r.score}))
            .collect();
        println!("{}", serde_json::to_string_pretty(&list).unwrap_or_default());
        return Ok(());
    }
    let label = if a.edge_csv.is_some() { "entering" } else { "in-lanes" };
    println!("{:<11} {:>10} {:>10} {:>6} {:>6} {:>9}  id", "type", "x", "y", "lanes", "links", label);
    let mut kinds: Vec<&str> = keep.iter().map(|r| r.kind).collect();
    kinds.sort();
    kinds.dedup();
    for kind in kinds {
        for r in keep.iter().filter(|r| r.kind == kind) {
            println!("{:<11} {:>10.1} {:>10.1} {:>6} {:>6} {:>9.0}  {}", r.kind, r.x, r.y, r.lanes, r.links, r.score, r.id);
        }
    }
    Ok(())
}
