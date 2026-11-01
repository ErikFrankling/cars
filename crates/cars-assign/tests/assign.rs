use std::path::PathBuf;

use cars_assign::calibrate::{self, Assignment, CountRow, Counts, Role};
use cars_assign::costs::{BIN_S, CostTable, DayCounts, Supply};
use cars_assign::cuts::{self, Cut, Discharge};
use cars_assign::day::Engine;
use cars_assign::driver;
use cars_assign::ledger::{Ledger, Verdict, VerdictInput, verdict};
use cars_assign::population::{Population, Procedures, Traveller};
use cars_assign::route::{Graph, Work};
use cars_assign::scenario::Scenario;
use cars_assign::update::{self, Graphs, Rule, Schedule};
use cars_assign::{mix, unit};
use cars_core::demand::Demand;
use cars_core::net::Net;

fn net_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/grid5.net.xml")
}

const PASSENGER: u32 = 1 << 6;

fn empty_demand(net: &Net) -> Demand {
    Demand::load(net, &[], &[], 1, None).unwrap()
}

/// `n` travellers between edges picked by a hash, free-flow routed.
fn population(net: &Net, supply: &Supply, n: usize) -> (Population, Graphs) {
    let demand = empty_demand(net);
    let tv: Vec<Traveller> = (0..n)
        .map(|i| {
            let (a, b) = (mix(1, i as u64) as usize % supply.n(), mix(2, i as u64) as usize % supply.n());
            Traveller {
                id: i as u32,
                o_edge: supply.normal[a],
                d_edge: supply.normal[b],
                depart_s: (i as f32 * 3600.0) / n as f32,
                desired_arrival_s: f32::NAN,
                earliest_s: 0.0,
                latest_s: 7200.0,
                tour: i as u32,
                ..Default::default()
            }
        })
        .filter(|t| t.o_edge != t.d_edge)
        .collect();
    let mut pop = Population::new(demand, vec![Procedures::default()], tv);
    let graphs = Graphs::new(net, supply, &pop, 8);
    let (_, dropped) = update::route_free_flow(&mut pop, &graphs, supply, 2);
    assert_eq!(dropped, 0);
    (pop, graphs)
}

fn setup() -> (Net, Supply) {
    let net = Net::load(&net_path()).unwrap();
    let supply = Supply::new(&net, &[], std::iter::empty());
    (net, supply)
}

fn congested(supply: &Supply, n_bins: usize, seed: u64) -> CostTable {
    let mut c = CostTable::free_flow(supply, n_bins);
    for e in 0..c.n_edges {
        for b in 0..n_bins {
            c.c[e * n_bins + b] = supply.ff[e] * (1.0 + 3.0 * unit(seed, (e * n_bins + b) as u64) as f32);
        }
    }
    c.enforce_fifo();
    c
}

#[test]
fn queue_estimator_charges_a_queue_and_nothing_else() {
    let (_, supply) = setup();
    let (n_bins, e) = (6, 3usize);
    let mut day = DayCounts::new(supply.n(), n_bins, 1);
    // 60 arrive in the first bin, 20 leave per bin: a queue that clears after three.
    day.n_in[e * n_bins] = 60;
    for b in 0..3 {
        day.left[e * n_bins + b] = 20;
    }
    day.end_bin = n_bins;
    let c = CostTable::from_day(&supply, &day);
    let ff = supply.ff[e];
    assert!((c.c[e * n_bins + 1] - (ff + 30.0 / (20.0 / BIN_S))).abs() < 1.0, "{}", c.c[e * n_bins + 1]);
    assert!((c.c[e * n_bins + 5] - ff).abs() < 1e-3, "cleared");
    // An edge with no traffic costs free flow.
    assert_eq!(c.c[(e + 1) * n_bins], supply.ff[e + 1]);
}

#[test]
fn vehicles_still_on_the_network_stay_in_the_queue_when_a_day_stops_early() {
    let (_, supply) = setup();
    let (n_bins, e) = (10, 2usize);
    let mut day = DayCounts::new(supply.n(), n_bins, 1);
    day.n_in[e * n_bins] = 100;
    day.left[e * n_bins] = 10;
    day.end_bin = 3;
    let c = CostTable::from_day(&supply, &day);
    assert!(c.c[e * n_bins + 2] > supply.ff[e] + 1000.0, "{}", c.c[e * n_bins + 2]);
    assert_eq!(c.c[e * n_bins + 9], c.c[e * n_bins + 2], "the last bin stands for the rest of the day");
}

#[test]
fn replica_counters_are_averaged() {
    let (_, supply) = setup();
    let (n_bins, e) = (4, 1usize);
    let mut one = DayCounts::new(supply.n(), n_bins, 1);
    let mut two = DayCounts::new(supply.n(), n_bins, 2);
    for (d, f) in [(&mut one, 1u16), (&mut two, 2u16)] {
        d.n_in[e * n_bins] = 40 * f;
        d.left[e * n_bins] = 10 * f;
        d.left[e * n_bins + 1] = 10 * f;
        d.end_bin = n_bins;
    }
    let (a, b) = (CostTable::from_day(&supply, &one), CostTable::from_day(&supply, &two));
    assert_eq!(a.c[e * n_bins + 1], b.c[e * n_bins + 1]);
}

#[test]
fn memory_and_fifo() {
    let (_, supply) = setup();
    let mut a = CostTable::free_flow(&supply, 3);
    let mut b = CostTable::free_flow(&supply, 3);
    b.c[0] = 1000.0;
    a.blend(&b, 0.3);
    // 0.7 ff + 0.3 * 1000, then capped by a bin length plus the next bin's cost.
    let ff = supply.ff[0];
    assert!((a.c[0] - (ff + BIN_S).min(0.7 * ff + 300.0)).abs() < 1e-3);
    assert!(a.c[0] <= BIN_S + a.c[1]);
}

#[test]
fn alt_matches_dijkstra_on_a_time_dependent_table() {
    let (net, supply) = setup();
    let g = Graph::new(&net, &supply, PASSENGER, 8);
    let costs = congested(&supply, 24, 5);
    let (mut wa, mut wd) = (Work::new(supply.n()), Work::new(supply.n()));
    let mut n = 0;
    for i in 0..2000u64 {
        let (o, d) = ((mix(3, i) as usize % supply.n()) as u32, (mix(4, i) as usize % supply.n()) as u32);
        let t = (mix(5, i) % 7200) as f32;
        let (a, b) = (g.path(&costs, &mut wa, o, d, t, true), g.path(&costs, &mut wd, o, d, t, false));
        match (a, b) {
            (Some(a), Some(b)) => {
                assert!((a.1 - b.1).abs() < 0.2, "{} vs {} for {o}->{d}", a.1, b.1);
                assert!((costs.evaluate(&a.0, t) - a.1).abs() < 10.5, "evaluate agrees up to a turnaround penalty");
                n += 1;
            }
            (None, None) => {}
            _ => panic!("reachability differs for {o}->{d}"),
        }
    }
    assert!(n > 1500);
    assert!(wa.settled < wd.settled, "the bound must help");
}

#[test]
fn a_reversal_is_only_taken_when_nothing_else_works() {
    let (net, supply) = setup();
    let g = Graph::new(&net, &supply, PASSENGER, 8);
    let costs = CostTable::free_flow(&supply, 2);
    let mut w = Work::new(supply.n());
    let mut reversals = 0;
    for i in 0..500u64 {
        let (o, d) = ((mix(6, i) as usize % supply.n()) as u32, (mix(7, i) as usize % supply.n()) as u32);
        if let Some((p, _)) = g.path(&costs, &mut w, o, d, 0.0, true) {
            reversals += u32::from(g.has_reversal(&p));
        }
    }
    assert_eq!(reversals, 0, "--no-turnarounds grid has none to take");
}

#[test]
fn capped_share_only_routes_its_sample_and_switches_no_more() {
    let (net, supply) = setup();
    let (mut pop, graphs) = population(&net, &supply, 4000);
    let costs = congested(&supply, 24, 9);
    let n = pop.travellers.len() as f64;
    let s = update::update_routes(&mut pop, &graphs, &supply, &costs, Rule::Capped { share: 0.15 }, 42);
    assert!((s.sampled as f64 / n - 0.15).abs() < 0.03);
    assert!(s.switched <= s.sampled);
    assert!(s.gap > 0.0 && s.gap < 1.0);
    let before: Vec<u32> = pop.travellers.iter().map(|t| t.route()).collect();
    let (mut pop2, _) = population(&net, &supply, 4000);
    let s2 = update::update_routes(&mut pop2, &graphs, &supply, &costs, Rule::Capped { share: 0.15 }, 42);
    assert_eq!(s.switched, s2.switched, "same seed, same switches");
    let _ = before;
    let (mut pop3, _) = population(&net, &supply, 4000);
    let e = update::update_routes(&mut pop3, &graphs, &supply, &costs, Rule::Everyone, 42);
    assert_eq!(e.sampled as f64, n);
    assert!(e.switched as f64 > s.switched as f64 * 2.0);
}

#[test]
fn gap_is_zero_for_routes_already_best() {
    let (net, supply) = setup();
    let (mut pop, graphs) = population(&net, &supply, 1000);
    let costs = congested(&supply, 24, 11);
    let n = pop.travellers.len();
    update::update_routes(&mut pop, &graphs, &supply, &costs, Rule::Everyone, 1);
    let g = update::gap_only(&pop, &graphs, &supply, &costs, 1.0, 2);
    assert_eq!(g.sampled as usize, n);
    assert!(g.gap < 0.001, "{}", g.gap);
}

#[test]
fn fixed_class_is_never_rerouted() {
    let (net, supply) = setup();
    let (mut pop, graphs) = population(&net, &supply, 500);
    for t in &mut pop.travellers {
        t.class = cars_assign::population::CLASS_FIXED;
    }
    let costs = congested(&supply, 24, 3);
    let s = update::update_routes(&mut pop, &graphs, &supply, &costs, Rule::Everyone, 3);
    assert_eq!(s.sampled, 0);
}

#[test]
fn arena_interns_and_compacts_and_keeps_plans_valid() {
    let (net, supply) = setup();
    let demand = empty_demand(&net);
    let mut t = Traveller::default();
    let mut pop = Population::new(demand, vec![Procedures::default()], vec![]);
    let (a, b) = (pop.intern(vec![1, 2, 3]), pop.intern(vec![4, 5]));
    assert_eq!(pop.intern(vec![1, 2, 3]), a);
    t.add_route(b);
    t.add_route(a);
    assert_eq!(t.route(), a);
    t.add_route(b);
    assert_eq!(t.n_plan, 2, "remembered routes are not added twice");
    for i in 0..6 {
        let r = pop.intern(vec![10 + i]);
        t.add_route(r);
    }
    assert_eq!(t.n_plan, 5);
    let keep = pop.demand.routes[t.route() as usize].clone();
    pop.travellers.push(t);
    let dropped = pop.compact();
    assert_eq!(dropped, 8 - 5);
    assert_eq!(pop.demand.routes[pop.travellers[0].route() as usize], keep);
    assert_eq!(pop.intern(keep), pop.travellers[0].route());
    let _ = supply;
}

#[test]
fn state_round_trips() {
    let (net, supply) = setup();
    let (pop, _) = population(&net, &supply, 300);
    let dir = std::env::temp_dir().join(format!("assign-state-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let f = dir.join("s.bin");
    pop.save_state(&f).unwrap();
    let mut other = Population::new(empty_demand(&net), vec![Procedures::default()], vec![]);
    other.load_state(&f).unwrap();
    assert_eq!(other.travellers.len(), pop.travellers.len());
    assert_eq!(other.demand.routes, pop.demand.routes);
    assert_eq!(other.travellers[7].depart_s, pop.travellers[7].depart_s);
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn trips_are_sorted_with_the_traveller_in_the_id() {
    let (net, supply) = setup();
    let (mut pop, _) = population(&net, &supply, 200);
    pop.travellers[3].depart_s = 9000.0;
    pop.fill_trips();
    assert!(pop.demand.trips.windows(2).all(|w| w[0].depart <= w[1].depart));
    assert_eq!(pop.demand.trips.last().unwrap().id, 3);
}

#[test]
fn ledger_and_ladder() {
    let l = Ledger { requested: 100, arrived: 90, active: 5, waiting_to_insert: 3, not_yet_due: 2, ..Default::default() };
    assert!(l.balanced());
    assert!(!l.clean());
    assert!(!Ledger { requested: 100, arrived: 90, ..Default::default() }.balanced());
    assert!(!Ledger { requested: 100, arrived: 100, imbalance: 1, ..Default::default() }.balanced());
    let clean = Ledger { requested: 10000, arrived: 9995, active: 5, ..Default::default() };
    assert!(clean.clean());
    assert!(!Ledger { teleports: 1, ..clean.clone() }.clean());
    let base = VerdictInput { converged: true, ledger_clean: true, delay_ratio: 1.1, ..Default::default() };
    assert_eq!(verdict(&base), Verdict::Converged);
    assert_eq!(verdict(&VerdictInput { delay_ratio: 3.0, ..base.clone() }), Verdict::FeasibleButCongested);
    assert_eq!(verdict(&VerdictInput { converged: false, ..base.clone() }), Verdict::UnstableOrUnconverged);
    assert_eq!(verdict(&VerdictInput { cuts_violated: 1, converged: false, ..base.clone() }), Verdict::DemandExceedsCut);
    assert_eq!(verdict(&VerdictInput { stalled_at_load: Some(0.4), cuts_violated: 1, ..base.clone() }), Verdict::NetworkSuspect, "the network comes first");
    assert_eq!(verdict(&VerdictInput { stalled_at_load: Some(0.9), ..base.clone() }), Verdict::Converged);
    assert_eq!(verdict(&VerdictInput { observations_conflict: true, ..base }), Verdict::IncompatibleWithObservations);
}

fn split_cut(supply: &Supply, succ: &[Vec<u32>]) -> Cut {
    let label = cuts::bisect(supply, 1);
    Cut::from_set("half".into(), label.iter().map(|&l| l == 0).collect(), succ)
}

#[test]
fn directional_bound_flags_one_way_overload_that_cancels_undirected() {
    let (net, supply) = setup();
    let succ = cuts::successors(&net, &supply);
    let cut = split_cut(&supply, &succ);
    assert!(!cut.out_edges.is_empty() && !cut.in_edges.is_empty());
    let side0: Vec<u32> = (0..supply.n() as u32).filter(|&e| cut.side[e as usize]).collect();
    let side1: Vec<u32> = (0..supply.n() as u32).filter(|&e| !cut.side[e as usize]).collect();
    let d = Discharge { observed: vec![0.1; supply.n()], ..Default::default() };
    let cap_in: f32 = cut.in_edges.iter().map(|&e| d.rate(&supply, e)).sum();
    // Many more want in during an hour than can get in; as many want out, and that direction is the same.
    let n = (cap_in * 3600.0 * 2.0) as usize;
    let mut tv = Vec::new();
    for i in 0..n {
        tv.push(Traveller { o_edge: supply.normal[side1[i % side1.len()] as usize], d_edge: supply.normal[side0[i % side0.len()] as usize], depart_s: (i as f32) * 3000.0 / n as f32, ..Default::default() });
    }
    let pop = Population::new(empty_demand(&net), vec![Procedures::default()], tv);
    let reports = cuts::check_cut(&cut, &pop, &supply, &d, 0.0, 14400.0);
    let inbound = reports.iter().find(|r| r.direction == "in").unwrap();
    let outbound = reports.iter().find(|r| r.direction == "out").unwrap();
    assert!(inbound.violated, "{inbound:?}");
    assert!(inbound.shortfall_1h > 0.0);
    assert_eq!(outbound.must_cross, 0);
    assert!(!outbound.violated);
    assert!(inbound.min_unmet <= inbound.shortfall_1h + 1.0, "a longer horizon can only help");
}

#[test]
fn no_false_alarm_within_capacity() {
    let (net, supply) = setup();
    let succ = cuts::successors(&net, &supply);
    let cut = split_cut(&supply, &succ);
    let side0: Vec<u32> = (0..supply.n() as u32).filter(|&e| cut.side[e as usize]).collect();
    let side1: Vec<u32> = (0..supply.n() as u32).filter(|&e| !cut.side[e as usize]).collect();
    let d = Discharge { observed: vec![0.1; supply.n()], ..Default::default() };
    let tv: Vec<Traveller> = (0..50).map(|i| Traveller { o_edge: supply.normal[side1[i % side1.len()] as usize], d_edge: supply.normal[side0[i % side0.len()] as usize], ..Default::default() }).collect();
    let pop = Population::new(empty_demand(&net), vec![Procedures::default()], tv);
    assert!(cuts::check_cut(&cut, &pop, &supply, &d, 0.0, 3600.0).iter().all(|r| !r.violated));
}

#[test]
fn named_cut_finds_its_sides_from_the_removed_edges() {
    let (net, supply) = setup();
    let succ = cuts::successors(&net, &supply);
    // The middle row of a 5 by 5 grid: remove every link between rows 1 and 2, in both directions.
    let dir = std::env::temp_dir().join(format!("assign-cuts-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let f = dir.join("cuts.csv");
    let mut text = String::from("cut,edge,dir\n");
    for c in ["A", "B", "C", "D", "E"] {
        text.push_str(&format!("river,{c}1{c}2,a\nriver,{c}2{c}1,b\n"));
    }
    std::fs::write(&f, text).unwrap();
    let cs = cuts::load_named_cuts(&f, &net, &supply, &succ).unwrap();
    assert_eq!(cs.len(), 1, "two sides make one cut");
    assert_eq!(cs[0].out_edges.len(), 5);
    assert_eq!(cs[0].in_edges.len(), 5);
    let a = net.edge_index["A0A1"];
    let b = net.edge_index["A3A4"];
    let (x, y) = (cs[0].side[supply.dense[a as usize] as usize], cs[0].side[supply.dense[b as usize] as usize]);
    assert_ne!(x, y, "rows either side of the river are on different sides");
    std::fs::remove_dir_all(&dir).ok();
}

fn rows_for(roles: &[Role]) -> Vec<CountRow> {
    roles.iter().enumerate().map(|(i, &role)| CountRow { site: i as u32, edge: i as u32, t0: 0.0, t1: 3600.0, y: 100.0, role, corridor: i as u32 }).collect()
}

fn toy_assignment() -> Assignment {
    // Rows 0-2: each counts one cell. Row 3 is held out and sees the same cell as row 0.
    let entries = vec![(0, 0, 1.0), (1, 1, 1.0), (2, 2, 1.0), (3, 0, 1.0)];
    Assignment { entries, cells: vec![0, 1, 2], q: vec![50.0, 100.0, 200.0], of_traveller: vec![] }
}

#[test]
fn prior_pull_decides_how_far_a_cell_moves() {
    let a = toy_assignment();
    let rows = rows_for(&[Role::Train, Role::Train, Role::Train, Role::Test]);
    let q0 = vec![50.0, 100.0, 200.0];
    let loose = calibrate::cell_fit(&a, &rows, &q0, 0.01, 200);
    let tight = calibrate::cell_fit(&a, &rows, &q0, 50.0, 200);
    assert!((loose[0] - 100.0).abs() < 3.0, "{loose:?}");
    assert!(tight[0] < 60.0, "{tight:?}");
    assert!(tight[0] > 50.0);
    assert!((loose[1] - 100.0).abs() < 1e-6, "already right");
}

#[test]
fn test_rows_never_reach_the_fit() {
    let a = toy_assignment();
    let mut rows = rows_for(&[Role::Train, Role::Train, Role::Train, Role::Test]);
    let q0 = vec![50.0, 100.0, 200.0];
    let before = calibrate::cell_fit(&a, &rows, &q0, 0.5, 200);
    rows[3].y = 1e6;
    let after = calibrate::cell_fit(&a, &rows, &q0, 0.5, 200);
    assert_eq!(before, after);
    // A cell no training row sees stays at its prior.
    let mut rows = rows_for(&[Role::Selection, Role::Train, Role::Train, Role::Test]);
    rows[0].y = 1e6;
    let fit = calibrate::cell_fit(&a, &rows, &q0, 0.5, 200);
    assert!((fit[0] - 50.0).abs() < 1e-9);
}

#[test]
fn guards_pass_a_small_change_and_fail_a_scale_error() {
    let cells: Vec<u64> = (0..64u64).map(|i| ((i % 8) << 32) | (((i / 8) % 8) << 16)).collect();
    let q0: Vec<f64> = (0..64).map(|i| 10.0 + (i * 7 % 13) as f64).collect();
    let len = vec![3000.0; 64];
    let g = calibrate::guards(&cells, &q0, &q0, &len);
    assert!(g.pass, "{g:?}");
    let scaled: Vec<f64> = q0.iter().map(|x| x * 1.3).collect();
    let g = calibrate::guards(&cells, &q0, &scaled, &len);
    assert!(!g.pass);
    assert!((g.total_ratio - 1.3).abs() < 1e-9);
    assert!((g.cell_slope - 1.3).abs() < 1e-9);
}

#[test]
fn structural_zeros_stay_zero_and_change_is_sampled() {
    let (net, supply) = setup();
    let (mut pop, _) = population(&net, &supply, 3000);
    let zone = calibrate::zones(&supply, 4);
    let costs = CostTable::free_flow(&supply, 24);
    let a = calibrate::build_assignment(&pop, &supply, &costs, &zone, &[]);
    let n0 = pop.travellers.len() as f64;
    let target: Vec<f64> = a.q.iter().map(|q| q * 1.2).collect();
    let (added, removed) = calibrate::apply_cells(&mut pop, &a, &target, 5);
    assert_eq!(removed, 0);
    assert!((added as f64 / n0 - 0.2).abs() < 0.05, "{added} of {n0}");
    let b = calibrate::build_assignment(&pop, &supply, &costs, &zone, &[]);
    let keys: std::collections::HashSet<u64> = a.cells.iter().map(|c| c >> 16).collect();
    assert!(b.cells.iter().all(|c| keys.contains(&(c >> 16))), "no new zone pair appears");
    assert!(pop.travellers.iter().all(|t| t.n_plan >= 1), "clones keep the plan");
}

#[test]
fn split_keeps_clusters_and_corridors_whole() {
    let (net, supply) = setup();
    let mut c = Counts::default();
    let n = supply.n();
    for i in 0..n {
        c.sites.push(format!("s{i}"));
        for h in 0..24 {
            c.rows.push(CountRow { site: i as u32, edge: i as u32, t0: h as f32 * 3600.0, t1: (h + 1) as f32 * 3600.0, y: 10.0, role: Role::Train, corridor: (i / 3) as u32 });
        }
    }
    c.split(&net, &supply, 150.0, (0.6, 0.2), (15.0 * 3600.0, 18.0 * 3600.0), 3);
    let mut role_of = vec![None; n];
    for r in &c.rows {
        let base = if r.role == Role::HeldPeak { Role::Train } else { r.role };
        assert!(role_of[r.site as usize].is_none_or(|x| x == base), "a site has one role");
        role_of[r.site as usize] = Some(base);
    }
    let mut by_corridor = std::collections::HashMap::new();
    for r in &c.rows {
        let base = role_of[r.site as usize].unwrap();
        assert_eq!(*by_corridor.entry(r.corridor).or_insert(base), base, "a corridor stays together");
    }
    assert!(c.rows.iter().any(|r| r.role == Role::HeldPeak), "a peak is held out");
}

#[test]
fn counts_refuse_what_the_spec_refuses() {
    let (net, supply) = setup();
    let dir = std::env::temp_dir().join(format!("assign-counts-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let f = dir.join("counts.csv");
    let good = net.edges[supply.normal[0] as usize].id.clone();
    let rows = format!(
        "site,edge,dir,t0_s,t1_s,day_type,vehicles,class,source,role,corridor\n\
         a,{good},measured,0,3600,weekday,10,all,measured,train,c\n\
         b,{good},halved,0,3600,weekday,10,all,measured,train,c\n\
         c,{good},split_assumed,0,3600,weekday,10,all,measured,train,c\n\
         d,{good},measured,0,3600,,10,all,annual,train,c\n\
         e,{good},measured,0,3600,weekday,10,all,estimated,test,c\n\
         f,nope,measured,0,3600,weekday,10,all,measured,train,c\n"
    );
    std::fs::write(&f, rows).unwrap();
    let c = Counts::load(&f, &net, &supply).unwrap();
    assert_eq!(c.rows.len(), 2, "{:?}", c.rejected);
    assert_eq!(c.rejected["direction_halved"], 1);
    assert_eq!(c.rejected["no_day_type"], 1);
    assert_eq!(c.rejected["estimated_as_validation"], 1);
    assert_eq!(c.rejected["unknown_edge"], 1);
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn count_error_and_geh() {
    let rows = rows_for(&[Role::Test, Role::Test]);
    let e = calibrate::count_error(&rows, Role::Test, |r| if r.site == 0 { 100.0 } else { 200.0 });
    assert!((e.wape - 0.5).abs() < 1e-9);
    assert_eq!(e.geh5, 0.5, "GEH of 100 against 200 is over 5");
}

#[test]
fn departures_move_only_for_a_saving_and_stay_in_the_window() {
    let (net, supply) = setup();
    let (mut pop, _) = population(&net, &supply, 2000);
    update::default_schedule(&mut pop, &supply);
    // An expensive first hour, so that a move out of it pays.
    let n_bins = 24;
    let mut c = CostTable::free_flow(&supply, n_bins);
    for e in 0..c.n_edges {
        for b in 0..12 {
            c.c[e * n_bins + b] = supply.ff[e] + 120.0;
        }
    }
    let windows: Vec<(f32, f32)> = pop.travellers.iter().map(|t| (t.earliest_s, t.latest_s)).collect();
    let before: Vec<f32> = pop.travellers.iter().map(|t| t.depart_s).collect();
    let st = update::update_departures(&mut pop, &supply, &c, Schedule { early: 0.5, late: 2.0 }, 1.0, 9);
    assert!(st.moved > 0);
    for (i, t) in pop.travellers.iter().enumerate() {
        assert!(t.depart_s >= windows[i].0 - 1e-3 && t.depart_s <= windows[i].1 + 1e-3);
        assert!((t.depart_s - before[i]).abs() == 0.0 || ((t.depart_s - before[i]).abs() - 300.0).abs() < 1e-2);
    }
    // Free flow everywhere: nobody saves 30 s, so nobody moves.
    let flat = CostTable::free_flow(&supply, n_bins);
    let (mut pop2, _) = population(&net, &supply, 2000);
    update::default_schedule(&mut pop2, &supply);
    let st = update::update_departures(&mut pop2, &supply, &flat, Schedule { early: 0.5, late: 2.0 }, 1.0, 9);
    assert_eq!(st.moved, 0, "{st:?}");
}

#[test]
fn convergence_needs_all_three() {
    let flat: Vec<(f64, Vec<f64>)> = (0..6).map(|_| (100.0, vec![1000.0])).collect();
    assert!(driver::convergence(&flat, 0.01, true, 0.02).converged);
    assert!(!driver::convergence(&flat, 0.03, true, 0.02).converged, "gap");
    assert!(!driver::convergence(&flat, 0.01, false, 0.02).converged, "ledger");
    let moving: Vec<(f64, Vec<f64>)> = (0..6).map(|i| (100.0 + i as f64 * 5.0, vec![1000.0])).collect();
    assert!(!driver::convergence(&moving, 0.01, true, 0.02).converged, "cost");
    let churn: Vec<(f64, Vec<f64>)> = (0..6).map(|i| (100.0, vec![1000.0 + i as f64 * 50.0])).collect();
    assert!(!driver::convergence(&churn, 0.01, true, 0.02).converged, "flows");
    assert!(!driver::convergence(&flat[..3], 0.01, true, 0.02).converged, "five iterations first");
}

fn gpu_scenario() -> (Scenario, Net, Supply) {
    let (net, supply) = setup();
    let s = Scenario {
        name: "t".into(),
        net: net_path(),
        routes: vec![],
        additional: vec![],
        travellers: None,
        fixed_prefixes: vec![],
        fixed_vtypes: vec![],
        counts: None,
        cuts: None,
        discharge: None,
        begin: 0.0,
        end: 3600.0,
        horizon: 7200.0,
        dt: 1.0,
        seed: 3,
        capacity: 3000,
        time_to_teleport: 0.0,
        ignore_blocker: None,
        share: 0.15,
        memory: 0.3,
        landmarks: 8,
        turnaround_s: 10.0,
        init: String::new(),
        zones: None,
        trusted: false,
    };
    (s, net, supply)
}

fn signature(d: &cars_assign::day::DayResult) -> (Vec<u16>, Vec<u16>, Vec<u16>, u64, f64) {
    (d.counts.n_in.clone(), d.counts.left.clone(), d.counts.inserted.clone(), d.ledgers[0].arrived, d.stats[0].mean_travel_s)
}

/// Milestone 0. Needs the GPU: `flock /tmp/cars-gpu.lock cargo test -p cars-assign --release -- --ignored`.
#[test]
#[ignore]
fn reset_reproduces_a_fresh_world_and_the_ledger_balances() {
    let (s, net, supply) = gpu_scenario();
    let (mut pop, _) = population(&net, &supply, 2500);
    pop.travellers.retain(|t| t.depart_s < 3600.0);
    let mut fresh = Engine::new(&net, &mut pop, &s, &[s.seed]).unwrap();
    let a = cars_assign::day::run_day(&mut fresh, &supply, &pop, &s, &mut cars_assign::day::NoPause);
    assert!(a.ledgers[0].balanced(), "{:?}", a.ledgers[0]);
    assert_eq!(a.ledgers[0].teleports, 0);
    assert_eq!(a.ledgers[0].imbalance, 0);
    assert_eq!(a.ledgers[0].arrived + a.ledgers[0].active + a.ledgers[0].waiting_to_insert + a.ledgers[0].not_yet_due, pop.travellers.len() as u64);
    // The same demand and seed in the same world, after a reset.
    fresh.load_day(&net, &mut pop, &[s.seed]).unwrap();
    let b = cars_assign::day::run_day(&mut fresh, &supply, &pop, &s, &mut cars_assign::day::NoPause);
    assert_eq!(signature(&a), signature(&b), "reset must give identical counters");
    // And in a world built from nothing.
    drop(fresh);
    let mut other = Engine::new(&net, &mut pop, &s, &[s.seed]).unwrap();
    let c = cars_assign::day::run_day(&mut other, &supply, &pop, &s, &mut cars_assign::day::NoPause);
    assert_eq!(signature(&a), signature(&c), "fresh build must match");
    // In a counted run, what enters an edge leaves it.
    if a.ledgers[0].active == 0 {
        let (i, l): (u64, u64) = (a.counts.n_in.iter().map(|&x| x as u64).sum(), a.counts.left.iter().map(|&x| x as u64).sum());
        assert_eq!(i, l);
    }
}

#[test]
#[ignore]
fn replicas_balance_per_replica() {
    let (s, net, supply) = gpu_scenario();
    let (mut pop, _) = population(&net, &supply, 1500);
    pop.travellers.retain(|t| t.depart_s < 3600.0);
    let mut e = Engine::new(&net, &mut pop, &s, &[1, 2, 3]).unwrap();
    let a = cars_assign::day::run_day(&mut e, &supply, &pop, &s, &mut cars_assign::day::NoPause);
    assert_eq!(a.ledgers.len(), 3);
    for l in &a.ledgers {
        assert!(l.balanced(), "{l:?}");
        assert_eq!(l.requested, pop.travellers.len() as u64);
    }
    assert_ne!(a.stats[0].mean_travel_s, a.stats[1].mean_travel_s, "different seeds differ");
}

#[test]
#[ignore]
fn a_patched_route_is_followed() {
    use cars_assign::enroute::Enroute;
    let (mut s, net, supply) = gpu_scenario();
    s.end = 1200.0;
    let (mut pop, graphs) = population(&net, &supply, 600);
    pop.travellers.retain(|t| t.depart_s < 1200.0);
    let mut e = Engine::new(&net, &mut pop, &s, &[1]).unwrap();
    let mut live = Enroute::new(&net, &supply, &graphs, &pop, 1.0, None, 1);
    let a = cars_assign::day::run_day(&mut e, &supply, &pop, &s, &mut live);
    assert!(a.ledgers[0].balanced(), "{:?}", a.ledgers[0]);
    assert_eq!(a.ledgers[0].collisions, 0);
    assert!(live.stats.epochs > 0);
}
