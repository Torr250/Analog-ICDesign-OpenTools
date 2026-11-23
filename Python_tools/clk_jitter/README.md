# clk_jitter

`clock_jitter.py` analyzes jitter and builds the eye diagram of a **periodic clock** from an ngspice transient simulation (`.raw` file). For random PRBS data use [`../eye_diagram/`](../eye_diagram/) instead.

It is also the base of [`../osc_characterization/`](../osc_characterization/), which additionally *measures* the oscillation frequency instead of taking it as an input.

## Requirements

```
pip install spicelib numpy matplotlib --break-system-packages
```

## Usage

```bash
python3 clock_jitter.py clock.raw --freq 1e9 --signal "v(clk)"
python3 clock_jitter.py clock.raw --freq 1e9 --signal "v(clk)" --vdd 1.8
```

| Option | Meaning |
|---|---|
| `--freq` | **Nominal** clock frequency in Hz (required). |
| `--signal` | Signal to analyze (default `v(clk)`). |
| `--vdd` / `--center-voltage` | Initial threshold (VDD/2 or explicit). Default: (max+min)/2. |
| `--no-refine-threshold` | Disable the minimum-jitter threshold search. |
| `--ui-window`, `--skip-ui`, `--oversample` | Fold window (UI), start-up UI to discard, points per UI. |
| `--outdir` | Output directory (default `clock_analysis`). |

## What it computes

- Measured vs. nominal frequency, and **measured** duty cycle (not assumed to be 50%).
- Rising and falling **TIE** with respect to an ideal grid fitted by linear regression, so a small mismatch between the real and the nominal frequency does not appear as a spurious drift.
- **Period jitter** and **cycle-to-cycle jitter** (immune to that mismatch by construction).
- Voltage noise at the high and low levels, sampled at the middle of each pulse according to the measured duty cycle.
- Eye diagram folded and centered on the rising edge.

## Outputs (in `clock_analysis/`)

`clock_eye.png`, `hist_tie_rising.png`, `hist_tie_falling.png`, `hist_period_rising.png`, `hist_cycle_to_cycle_rising.png`, `hist_noise_high.png`, `hist_noise_low.png`.
