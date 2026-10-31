//! Small helpers around quick-xml for SUMO's attribute-heavy files.

use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use flate2::read::MultiGzDecoder;
use quick_xml::events::BytesStart;

/// Open a possibly gzipped XML file for streaming.
pub fn open(path: &Path) -> Result<Box<dyn BufRead>, String> {
    let file = File::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let gz = path.extension().is_some_and(|e| e == "gz");
    Ok(if gz {
        Box::new(BufReader::with_capacity(1 << 20, MultiGzDecoder::new(file)))
    } else {
        Box::new(BufReader::with_capacity(1 << 20, file))
    })
}

/// An attribute by name, unescaped.
pub fn attr(e: &BytesStart, name: &str) -> Option<String> {
    for a in e.attributes().with_checks(false).flatten() {
        if a.key.as_ref() == name.as_bytes() {
            return Some(
                a.unescape_value()
                    .map(|v| v.into_owned())
                    .unwrap_or_else(|_| String::from_utf8_lossy(&a.value).into_owned()),
            );
        }
    }
    None
}

pub fn attr_f64(e: &BytesStart, name: &str) -> Option<f64> {
    attr(e, name)?.trim().parse().ok()
}

pub fn attr_f32(e: &BytesStart, name: &str) -> Option<f32> {
    attr(e, name)?.trim().parse().ok()
}

/// Parse "x,y x,y ..." and ignore a z coordinate if present.
pub fn parse_shape(s: &str) -> Vec<[f32; 2]> {
    s.split_ascii_whitespace()
        .filter_map(|p| {
            let mut it = p.split(',');
            let x: f32 = it.next()?.parse().ok()?;
            let y: f32 = it.next()?.parse().ok()?;
            Some([x, y])
        })
        .collect()
}
