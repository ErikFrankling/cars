//! The kernels must parse and validate without a GPU, so a typo does not wait in the queue for one.

const COMMON: &str = include_str!("../src/shaders/common.wgsl");
const ROUTE: &str = include_str!("../src/shaders/route.wgsl");
const STEP: &str = include_str!("../src/shaders/step.wgsl");
const LC: &str = include_str!("../src/shaders/lc.wgsl");
const DETECT: &str = include_str!("../src/shaders/detect.wgsl");
const CONTROL: &str = include_str!("../src/shaders/control.wgsl");
const SORT: &str = include_str!("../src/shaders/sort.wgsl");
const RENDER: &str = include_str!("../src/shaders/render.wgsl");

fn validate(name: &str, source: &str) {
    let module = naga::front::wgsl::parse_str(source).unwrap_or_else(|e| panic!("{name}: {}", e.emit_to_string(source)));
    naga::valid::Validator::new(naga::valid::ValidationFlags::all(), naga::valid::Capabilities::all())
        .validate(&module)
        .unwrap_or_else(|e| panic!("{name}: {}", e.emit_to_string(source)));
}

#[test]
fn main_kernels() {
    validate("step", &format!("{COMMON}\n{ROUTE}\n{STEP}\n{LC}\n{DETECT}"));
}

#[test]
fn control_and_sort() {
    validate("control", &format!("{COMMON}\n{CONTROL}"));
    validate("sort", &format!("{COMMON}\n{SORT}"));
}

#[test]
fn render() {
    validate("render", &format!("{COMMON}\n{RENDER}"));
}
