use cars_core::{Checks, Gpu, GpuOptions, sortbench};

fn main() {
    let gpu = pollster::block_on(Gpu::headless(GpuOptions { adapter_name: Some("7900".into()), checks: Checks::Trusted })).expect("gpu");
    eprintln!("{} limits: storage per stage {}, max binding {} MB", gpu.name(), gpu.limits().max_storage_buffers_per_shader_stage, gpu.limits().max_storage_buffer_binding_size >> 20);
    for &(n, key_bits, digit, block) in &[
        (10_000u32, 16u32, 8u32, 64u32), (100_000, 22, 8, 256), (100_000, 22, 11, 256), (300_000, 24, 8, 256),
        (1_000_000, 24, 8, 256), (1_000_000, 24, 8, 1024), (1_000_000, 24, 6, 256), (1_000_000, 22, 11, 1024), (1_000_000, 32, 8, 256),
        (3_000_000, 24, 8, 1024),
    ] {
        let repeat = (4_000_000 / n).clamp(1, 50);
        let ms = sortbench::bench(&gpu, n, key_bits, digit, block, repeat);
        println!("n={n:>8} key_bits={key_bits} digit={digit} block={block}: {ms:.3} ms/sort  ({:.0} Mkeys/s)", n as f64 / ms / 1000.0);
    }
}
