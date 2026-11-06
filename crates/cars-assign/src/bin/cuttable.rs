//! `cuts.rs` fed with the movement table instead of `nominal_capacity`. Rung 3's second falsifier: a cut below its demand can't be fixed by routing,
//! and a cut below real counted flow is a table error. No simulation.
//!
//!   cuttable NET DEMAND.tsv DISCHARGE.csv REAL.csv [CUTS.csv]
//! DEMAND: o_edge, d_edge, depart_s. DISCHARGE: edge, veh/s. REAL: edge, hour, flow (tuning sites only, one day each, largest kept).

use std::collections::HashMap;
use std::path::Path;

use cars_assign::costs::{NONE, Supply};
use cars_assign::cuts::{self, Discharge};
use cars_assign::population::{Population, Traveller};
use cars_core::demand::Demand;
use cars_core::net::Net;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    let net = Net::load(Path::new(&a[1]))?;
    let supply = Supply::new(&net, &[], std::iter::empty());
    let succ = cuts::successors(&net, &supply);
    let mut family = cuts::cluster_cuts(&supply, &succ);
    if let Some(p) = a.get(5) {
        family.extend(cuts::load_named_cuts(Path::new(p), &net, &supply, &succ)?);
    }
    let mut travellers = Vec::new();
    let mut unknown = 0u64;
    for line in std::fs::read_to_string(&a[2]).map_err(|e| e.to_string())?.lines().skip(1) {
        let v: Vec<&str> = line.split('\t').collect();
        let (Some(&o), Some(&d)) = (net.edge_index.get(v[0]), net.edge_index.get(v[1])) else {
            unknown += 1;
            continue;
        };
        if supply.dense[o as usize] == NONE || supply.dense[d as usize] == NONE {
            unknown += 1;
            continue;
        }
        travellers.push(Traveller { o_edge: o, d_edge: d, depart_s: v[2].parse().unwrap_or(0.0), ..Default::default() });
    }
    eprintln!("travellers {} unknown {unknown}", travellers.len());
    let pop = Population::new(Demand::default(), Vec::new(), travellers);
    let discharge = Discharge { measured: Discharge::load(Path::new(&a[3]), &net, &supply)?, observed: Vec::new() };
    let mut real: HashMap<u32, HashMap<u32, f64>> = HashMap::new();
    for line in std::fs::read_to_string(&a[4]).map_err(|e| e.to_string())?.lines().skip(1) {
        let v: Vec<&str> = line.split(',').collect();
        if let Some(&e) = net.edge_index.get(v[0]) {
            let m = real.entry(supply.dense[e as usize]).or_default().entry(v[1].parse().unwrap_or(0)).or_default();
            *m = m.max(v[2].parse().unwrap_or(0.0));
        }
    }
    println!("cut,dir,links,capacity,storage,must_cross,peak_1h,peak_start_h,shortfall_1h,violated,counted_sites,real_max_flow,real_over_cap");
    for c in &family {
        for r in cuts::check_cut(c, &pop, &supply, &discharge, 0.0, 93600.0) {
            let edges = if r.direction == "out" { &c.out_edges } else { &c.in_edges };
            let mut by_hour: HashMap<u32, f64> = HashMap::new();
            let mut sites = 0;
            for e in edges {
                if let Some(h) = real.get(e) {
                    sites += 1;
                    for (k, q) in h {
                        *by_hour.entry(*k).or_default() += q;
                    }
                }
            }
            let peak = by_hour.values().copied().fold(0.0, f64::max);
            println!("{},{},{},{:.0},{:.0},{},{},{:.2},{:.0},{},{},{:.0},{}", r.name, r.direction, r.links, r.capacity_veh_h, r.storage_veh, r.must_cross, r.peak_1h_crossing, r.peak_1h_start_s / 3600.0, r.shortfall_1h, r.violated, sites, peak, peak > r.capacity_veh_h);
        }
    }
    Ok(())
}
