# mc — Monte Carlo

Monte Carlo runs with ngspice and statistical analysis of the results.

| File | Purpose |
|---|---|
| `mc_runner.py` | Runs the `TB_not` testbench (CMOS inverter, gf180mcuD) N times with Monte Carlo enabled (`sw_stat_global=1`, `sw_stat_mismatch=1`). Collects the `.meas` results (`trise`, `tfall`, `tplh`, `tphl`, `tpd_avg`, `ivdd_rms`, `effy`) in a CSV and keeps one `.raw` per run. |
| `analyze_mc.py` | Statistics per metric (mean, sigma, min, max, median, CV, ±3σ), optional **yield** against specs, and one histogram per metric. |
| `mc_runner_latest.py` | Newer, general runner for **sky130A**: global process variation drawn once per sample in Python (so all devices of a run share the process draw, while mismatch stays independent per instance), reproducible via `--seed`. Takes any netlist as argument; see its docstring and `--help`. |

`mc_runner.py` does not substitute anything in the netlist between runs: each `ngspice -b` call starts with its own random seed, so **individual runs cannot be reproduced**. Use `mc_runner_latest.py` if you need reproducibility.

## Requirements

```
pip install spicelib numpy pandas matplotlib --break-system-packages
```
and `ngspice` in the `PATH`.

## Netlist template (not included)

`mc_runner.py` expects a template named `TB_not_mc_template.spice` in the working directory, whose `.control` block writes `TB_not.raw` and whose `.meas` statements use the names listed above. The template is **not part of this folder**; supply your own testbench with those names.

## Usage

```bash
# 1) Monte Carlo sweep -> mc_results.csv + mc_raws/mc_run_XXXX.raw
python3 mc_runner.py sweep                    # 200 runs, sequential
python3 mc_runner.py sweep --n 500 --jobs 8   # 500 runs, 8 in parallel

# 2) Overlay waveforms of several runs -> mc_analysis/mc_overlay_*.png
python3 mc_runner.py plot --n-overlay 30
python3 mc_runner.py plot --n-overlay 30 --mode first --signals "v(outb)" "v(in)"

# 3) Statistics and yield -> mc_analysis/hist_<metric>.png + mc_summary.csv
python3 analyze_mc.py mc_results.csv
python3 analyze_mc.py mc_results.csv --spec tpd_avg:gt:9e-11 --spec tpd_avg:lt:1.3e-10
```

`--spec metric:op:value` is repeatable; `op` is one of `lt`, `le`, `gt`, `ge`, and `value` is in **base units** (seconds, amperes, mW/GHz). A metric with both limits needs two `--spec`.
