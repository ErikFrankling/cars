//! A microscopic traffic simulator that runs on the GPU.

pub mod demand;
pub mod gpu;
pub mod metrics;
pub mod net;
pub mod router;
pub mod sim;
pub mod topology;
pub mod world;
pub mod xml;

pub use gpu::{Checks, Gpu, GpuOptions};
