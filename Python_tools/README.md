# Python_tools

Python scripts and helper netlists for analyzing analog / mixed-signal / SerDes simulations (mostly ngspice) and for characterizing circuits. Each subfolder has its own README.

| Folder | What it does |
|---|---|
| [`channel_model/`](channel_model/) | Loss-only channel model generator (SPICE subcircuit) and pulse-response / worst-case eye-height analysis. |
| [`clk_jitter/`](clk_jitter/) | Jitter analysis and eye diagram of a periodic clock (TIE, period and cycle-to-cycle jitter, duty cycle). |
| [`eye_diagram/`](eye_diagram/) | Eye diagram and metrics (jitter, noise, eye mask, bathtub) for random PRBS data. |
| [`isfpn/`](isfpn/) | Phase-noise estimation of oscillators with the impulse sensitivity function (ISF), without PSS+PNOISE. |
| [`mc/`](mc/) | Monte Carlo runners (gf180mcuD inverter testbench; general sky130A runner) and statistics / yield analysis. |
| [`osc_characterization/`](osc_characterization/) | Oscillator characterization: measured frequency, jitter, tuning curves and PVT corners from JSON configs. |
| [`pvt/`](pvt/) | Process / voltage / temperature sweeps and worst/best-case analysis. |
| [`vco_ideal/`](vco_ideal/) | Behavioral ideal VCO models (with and without phase noise) for system-level simulations. |

## Typical flows

- **Data eye:** `eye_diagram.py` → `eye_metrics.py`; the folded `.npz` can be overlaid on the channel worst-case eye with `channel_pulse_analysis.py --overlay-eye-npz`.
- **Clock / oscillator:** `clock_jitter.py` (known frequency) or `osc_characterization.py` (frequency measured from the signal).
- **Corners and statistics:** `pvt_runner.py` → `analyze_pvt.py`, and `mc_runner.py` → `analyze_mc.py`.

## Common requirements

```
pip install spicelib numpy scipy pandas matplotlib --break-system-packages
```
and `ngspice` in the `PATH` for the runners and netlist examples.

## Notes

- `pvt/pvt_runner.py` and `mc/mc_runner.py` need testbench templates (`TB_not_template.spice`, `TB_not_mc_template.spice`) that are not included in the repository; see the README of each folder.
- `mc/mc_runner.py` (gf180mcuD, unseeded runs) and `mc/mc_runner_latest.py` (sky130A, global-process draw, reproducible seed) are different tools, not two versions of the same one.
- The `.sp` files produced by `channel_model_generator.py` carry their parameters in a comment header that `channel_pulse_analysis.py` parses; see `channel_model/README.md`.
