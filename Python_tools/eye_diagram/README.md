# eye_diagram

Eye-diagram analysis of **random (PRBS) data** from an ngspice transient simulation (`.raw` file). Two scripts that work in sequence:

| Script | Purpose |
|---|---|
| `eye_diagram.py` | Reads the `.raw`, finds the decision threshold and the eye center automatically, folds the waveform into windows of N·UI and plots the eye. |
| `eye_metrics.py` | Reads the folded data and computes jitter, voltage noise, eye height/width, a statistical eye mask at a target BER and a bathtub curve. |

For a **periodic clock** (instead of PRBS data) use [`../clk_jitter/clock_jitter.py`](../clk_jitter/).

## Requirements

```
pip install spicelib numpy scipy matplotlib --break-system-packages
```

## Usage

```bash
# 1) Fold the eye (writes eye_analysis/eye_folded_data.npz + eye_<signal>.png)
python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9
python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9 --signal "v(out)" --skip-ui 5 --ui-window 2

# 2) Compute the metrics from the folded data
python3 eye_metrics.py
python3 eye_metrics.py --npz eye_analysis/eye_folded_data.npz --ber 1e-12
```

### Main options of `eye_diagram.py`

| Option | Meaning |
|---|---|
| `--freq` | Bit frequency in Hz (**required**); UI = 1/freq. |
| `--signal` | Signal to plot (default `v(out)`). |
| `--vdd` / `--center-voltage` | Initial threshold: VDD/2, or an explicit voltage (use this for differential signals). If both are omitted, (max+min)/2 of the data is used. |
| `--no-refine-threshold` | Skip the threshold search and use the initial threshold as is. |
| `--ui-window`, `--skip-ui`, `--oversample` | Window width in UI (default 2), start-up UI to discard (default 2), points per UI (default 200). |
| `--outdir` | Output directory (default `eye_analysis`). |

## How it works

- **Optimal threshold.** Instead of assuming VDD/2, the script sweeps candidate voltages and keeps the one that minimizes the jitter of the crossings. This matters for drivers with asymmetric rising/falling edges.
- **Automatic eye centering.** The mean phase of all the crossings with respect to the ideal bit grid is measured (circular average), so the total propagation delay of the circuit is taken from the data, not assumed. The eye center is placed at 0 UI and the ideal crossings at ±0.5 UI.
- **Jitter by position.** `eye_metrics.py` reports left (−0.5 UI) and right (+0.5 UI) jitter, not rising/falling, which is the usual convention of eye-diagram instruments for random data.
- **Gaussian extrapolation.** The eye mask and bathtub curve assume Gaussian jitter/noise. If the jitter is mostly deterministic (ISI, no noise sources enabled), the extrapolation to very low BER is only an approximation.

## Outputs (in `eye_analysis/`)

| File | Produced by | Content |
|---|---|---|
| `eye_<signal>.png` | `eye_diagram.py` | Centered eye diagram |
| `eye_folded_data.npz` | `eye_diagram.py` | Folded data (interface between the two scripts, also read by `../channel_model/channel_pulse_analysis.py` for `--overlay-eye-npz`) |
| `eye_with_metrics.png` | `eye_metrics.py` | Eye with the detected crossings |
| `hist_jitter_left.png`, `hist_jitter_right.png` | `eye_metrics.py` | TIE histograms (left / right crossing) |
| `hist_noise_top.png`, `hist_noise_bottom.png` | `eye_metrics.py` | Voltage-noise histograms (high / low level) |
| `eye_mask_ber<BER>.png` | `eye_metrics.py` | Statistical eye mask (diamond) at the target BER |
| `bathtub_curve.png` | `eye_metrics.py` | Bathtub curve |

Keys stored in the `.npz`: `grid_in_ui`, `matrix`, `ui`, `signal`, `threshold`, `threshold_initial`, `threshold_offset`, `threshold_refined`, `center_phase`, `mean_phase`.
