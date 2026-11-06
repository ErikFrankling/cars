//! Recorded tracks for replay with recorded boundaries, research/truth/replay/README.md.
//!
//! A `.rpl` file, little endian, written by scripts/replay/rpl.py:
//! `RPL1`, u32 lanes, per lane (u16 length, id bytes), u32 tracks, per track (u16 length, trip id bytes,
//! f32 t0, f32 key_dt, f32 release (seconds, as --begin), u32 keys, per key (u32 lane in the list above, f32 pos, f32 speed)).
//! A track with no keys only forces its trip's insertion; it is simulated from its depart on.

use crate::demand::Demand;
use crate::net::Net;
use crate::world::{GpuReplayCfg, GpuReplayKey, GpuReplayTrack, ReplayWorld, World};
use rustc_hash::FxHashMap;

/// `Trip::depart_speed_mode` of a replayed trip: recorded speed, inserted without any check.
pub const DEPART_REPLAY: u32 = 7;
const NONE: u32 = u32::MAX;

struct Reader<'a> {
    b: &'a [u8],
    at: usize,
}

impl Reader<'_> {
    fn take(&mut self, n: usize) -> Result<&[u8], String> {
        let s = self.b.get(self.at..self.at + n).ok_or("replay file ends early")?;
        self.at += n;
        Ok(s)
    }
    fn u16(&mut self) -> Result<u16, String> {
        Ok(u16::from_le_bytes(self.take(2)?.try_into().unwrap()))
    }
    fn u32(&mut self) -> Result<u32, String> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn f32(&mut self) -> Result<f32, String> {
        Ok(f32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn str(&mut self) -> Result<String, String> {
        let n = self.u16()? as usize;
        String::from_utf8(self.take(n)?.to_vec()).map_err(|e| e.to_string())
    }
}

pub struct Attached {
    pub tracks: usize,
    pub keys: usize,
    pub missing_trips: usize,
    pub forced: usize,
}

/// Reads `path` and puts its tracks on `world`: replayed trips insert unchecked and get their own queues.
pub fn attach(world: &mut World, net: &Net, demand: &Demand, path: &std::path::Path, begin: f32) -> Result<Attached, String> {
    if world.replica_edge_start.len() > 1 {
        return Err("replay needs a world with one replica".into());
    }
    let bytes = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut r = Reader { b: &bytes, at: 0 };
    if r.take(4)? != b"RPL1" {
        return Err("not a replay file".into());
    }
    let n_lanes = r.u32()? as usize;
    let mut lane_of = Vec::with_capacity(n_lanes);
    for _ in 0..n_lanes {
        let id = r.str()?;
        lane_of.push(*net.lane_index.get(&id).ok_or_else(|| format!("replay lane {id} is not in the net"))?);
    }
    let mut trip_of_name: FxHashMap<&str, u32> = FxHashMap::default();
    for (wt, &src) in world.trip_source.iter().enumerate() {
        trip_of_name.insert(demand.ids[demand.trips[src as usize].id as usize].as_str(), wt as u32);
    }
    let mut rw = ReplayWorld { trip_track: vec![NONE; world.trips.len()], ..Default::default() };
    let mut missing = 0;
    let n_tracks = r.u32()?;
    for _ in 0..n_tracks {
        let name = r.str()?;
        let (t0, key_dt, release, n) = (r.f32()?, r.f32()?, r.f32()?, r.u32()?);
        let first = rw.keys.len() as u32;
        let wt = trip_of_name.get(name.as_str()).copied();
        let (route_start, route_end) = wt.map_or((0, 0), |t| (world.trips[t as usize].route_start, world.trips[t as usize].route_end));
        let mut at = route_start;
        for _ in 0..n {
            let (l, pos, speed) = (r.u32()?, r.f32()?, r.f32()?);
            let lane = *lane_of.get(l as usize).ok_or("replay key names a lane past the list")?;
            if wt.is_some() && world.lanes[lane as usize].flags & 1 == 0 {
                let edge = world.lanes[lane as usize].edge;
                match (at..route_end).find(|&k| world.routes[k as usize] == edge) {
                    Some(k) => at = k,
                    None => return Err(format!("trip {name}: lane {} is not on its route", net.lanes[lane as usize].id)),
                }
            }
            rw.keys.push(GpuReplayKey { lane, pos, speed, route_i: at });
        }
        let Some(wt) = wt else {
            missing += 1;
            rw.keys.truncate(first as usize);
            continue;
        };
        rw.trip_track[wt as usize] = rw.tracks.len() as u32;
        let rel = |t: f32| if t >= 1e37 { t } else { (t as f64 - begin as f64) as f32 };
        rw.tracks.push(GpuReplayTrack { first, n, t0: rel(t0), key_dt: key_dt.max(1e-3), release: rel(release), pad: [0; 3] });
        world.trips[wt as usize].depart_speed_mode = DEPART_REPLAY;
    }
    // Replayed trips get queues of their own, so a blocked simulated entry never holds one back.
    let (old_q, old_t) = (std::mem::take(&mut world.queues), std::mem::take(&mut world.queue_trips));
    for q in old_q {
        let list = &old_t[q.next as usize..q.end as usize];
        for forced in [true, false] {
            let part: Vec<u32> = list.iter().copied().filter(|&t| (rw.trip_track[t as usize] != NONE) == forced).collect();
            if part.is_empty() {
                continue;
            }
            let next = world.queue_trips.len() as u32;
            world.queue_trips.extend_from_slice(&part);
            world.queues.push(crate::world::GpuQueue { edge: q.edge, next, end: world.queue_trips.len() as u32, pad: 0 });
        }
    }
    world.params.n_queues = world.queues.len() as u32;
    rw.cfg = GpuReplayCfg { begin, n_tracks: rw.tracks.len() as u32, n_trips: world.trips.len() as u32, pad: 0 };
    let out = Attached { tracks: rw.tracks.len(), keys: rw.keys.len(), missing_trips: missing, forced: rw.tracks.len() };
    world.replay = Some(rw);
    Ok(out)
}
