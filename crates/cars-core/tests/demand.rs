use cars_core::{demand::Demand, net::Net};
use std::path::{Path, PathBuf};
const BASE: &str = "/home/erikf/projects/personal/thesis-src/bachelor/config";
fn scenario(net: &str, route: &str) -> Demand {
    let root = Path::new(BASE);
    let net = Net::load(&root.join(net)).unwrap();
    Demand::load(
        &net,
        &[root.join(route)],
        &[root.join("vtypes.xml")],
        42,
        None,
    )
    .unwrap()
}
#[test]
fn ring() {
    if !Path::new(BASE).exists() {
        return;
    }
    let d = scenario("networks/ring.net.xml", "demand/ring.rou.xml");
    assert_eq!(d.trips.len(), 200, "{}", d.summary());
    assert!(d.routes.iter().all(|r| r.len() == 6480));
    assert_eq!(d.routes.len(), 80);
}
#[test]
fn bologna() {
    if !Path::new(BASE).exists() {
        return;
    }
    let d = scenario(
        "scenarios/bologna/joined_buslanes.net.xml",
        "scenarios/bologna/bologna_cars.rou.xml",
    );
    assert_eq!(d.trips.len(), 10069, "{}", d.summary());
}
#[test]
fn i80() {
    if !Path::new(BASE).exists() {
        return;
    }
    let d = scenario("networks/i80_vsl.net.xml", "demand/i80_vsl.rou.xml");
    assert!(!d.trips.is_empty());
    println!("{}", d.summary());
}
#[test]
fn glosa() {
    if !Path::new(BASE).exists() {
        return;
    }
    let d = scenario(
        "networks/glosa_two_signal.net.xml",
        "demand/glosa_two_signal.rou.xml",
    );
    assert_eq!(d.trips.len(), 955, "{}", d.summary());
    let times: Vec<_> = d
        .trips
        .iter()
        .filter(|t| d.ids[t.id as usize].starts_with("west_east."))
        .map(|t| t.depart)
        .collect();
    assert_eq!(times.len(), 434);
    assert_eq!(times[1], 5.538);
    assert_eq!(times[2], 11.076);
}
#[test]
#[ignore]
fn dublin() {
    let p =
        PathBuf::from("/home/erikf/projects/personal/thesis-src/kex/config/scenarios/dublin_urban");
    let start = std::time::Instant::now();
    let net = Net::load(&p.join("DCC.net.xml")).unwrap();
    let types = std::env::temp_dir().join(format!("cars-dublin-types-{}.xml", std::process::id()));
    std::fs::write(&types, r#"<routes><vType id="PKW"/></routes>"#).unwrap();
    let d = Demand::load(
        &net,
        &[p.join("DCC_routes.rou.xml"), p.join("DCC_emitters.emi.xml")],
        &[types.clone()],
        42,
        None,
    )
    .unwrap();
    std::fs::remove_file(types).unwrap();
    println!("{:?}: {}", start.elapsed(), d.summary());
    assert_eq!(d.trips.len(), 418078);
}

#[test]
fn distributions_routing_and_defaults() {
    use cars_core::demand::{CfModel, DepartLane, DepartSpeed};
    use std::io::Write;
    let dir = std::env::temp_dir().join(format!("cars-demand-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let np = dir.join("net.xml");
    std::fs::write(
        &np,
        r#"<net>
      <edge id="a"><lane id="a_0" index="0" speed="10" length="100"/></edge>
      <edge id="b"><lane id="b_0" index="0" speed="10" length="100" allow="passenger"/></edge>
      <edge id="c"><lane id="c_0" index="0" speed="10" length="100"/></edge>
      <connection from="a" to="b" fromLane="0" toLane="0"/>
      <connection from="b" to="c" fromLane="0" toLane="0"/>
    </net>"#,
    )
    .unwrap();
    let rp = dir.join("routes.xml.gz");
    let mut gz = flate2::write::GzEncoder::new(
        std::fs::File::create(&rp).unwrap(),
        flate2::Compression::fast(),
    );
    gz.write_all(br#"<routes>
      <flow id="f" type="types" route="choices" begin="1" end="11" number="4" departLane="best_prob" departSpeed="desired"/>
      <trip id="od" from="a" to="c" depart="0"/>
      <trip id="forbidden" type="bus" from="a" to="c" depart="0"/>
      <vehicle id="bad" depart="0"><route edges="a missing"/></vehicle>
      <vehicle id="disconnected" depart="0"><route edges="a c"/></vehicle>
      <vehicle id="embedded" depart="0"><routeDistribution><route edges="a b c" probability="1"/></routeDistribution></vehicle>
      <routeDistribution id="choices"><route refId="r" probability="1"/></routeDistribution>
      <route id="r" edges="a b c"/>
      <vTypeDistribution id="types" vTypes="car"/>
      <vType id="car" speedFactor="normc(1.1,0.2,0.5,1.5)"><carFollowing-IDM tau="1.7"/><param key="has.glosa.device" value="true"/></vType>
      <vType id="bus" vClass="bus"/>
      <person id="p"><walk edges="a"/></person><stop/>
    </routes>"#).unwrap();
    gz.finish().unwrap();
    let net = Net::load(&np).unwrap();
    let d = Demand::load(&net, &[rp.clone()], &[], 7, None).unwrap();
    assert_eq!(d.trips.len(), 6, "{}", d.summary());
    assert_eq!(d.routes.len(), 2);
    assert_eq!(d.dropped.unknown_edge, 1);
    assert_eq!(d.dropped.unconnected, 2);
    assert_eq!(d.stops_ignored, 1);
    assert_eq!(d.persons_ignored, 1);
    let car = &d.vtypes[d.vtype_index["car"] as usize];
    assert_eq!(car.model, CfModel::Idm);
    assert_eq!(car.tau, 1.7);
    assert!(car.glosa);
    assert_eq!(car.speed_factor_dev, 0.2);
    let bus = &d.vtypes[d.vtype_index["bus"] as usize];
    assert_eq!(bus.decel, 4.);
    assert_eq!(bus.emergency_decel, 7.);
    assert_eq!(bus.speed_factor_dev, 0.);
    let flow: Vec<_> = d
        .trips
        .iter()
        .filter(|t| d.ids[t.id as usize].starts_with("f."))
        .collect();
    assert_eq!(
        flow.iter().map(|t| t.depart).collect::<Vec<_>>(),
        vec![1., 3.5, 6., 8.5]
    );
    assert_eq!(flow[0].depart_lane, DepartLane::BestProb);
    assert_eq!(flow[0].depart_speed, DepartSpeed::Desired);
    let cut = Demand::load(&net, &[rp], &[], 7, Some(3.5)).unwrap();
    assert_eq!(cut.dropped.after_end, 2);
    std::fs::remove_dir_all(dir).unwrap();
}
