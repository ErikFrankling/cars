//! A microscopic traffic simulator that runs on the GPU.

pub mod actuated;
pub mod bestlanes;
pub mod closeup;
pub mod coord;
pub mod demand;
pub mod gpu;
pub mod metrics;
pub mod net;
pub mod physics;
pub mod router;
pub mod sim;
pub mod topology;
pub mod world;
pub mod xml;

pub use gpu::{Checks, Gpu, GpuOptions};

pub mod render;
