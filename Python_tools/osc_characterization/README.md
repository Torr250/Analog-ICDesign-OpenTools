# osc_characterization.py

Characterization of **oscillators** (typically differential, also single-ended) from **ngspice** transient simulations. It is based on `clock_jitter.py` (directional crossings, TIE from a linear fit, period and cycle-to-cycle jitter, eye folding), with one fundamental difference: the frequency of an oscillator is **not an input**, it is **measured** from the signal itself.

It covers a single simulation, tuning curves (sweep of a control parameter) and those same curves over several PVT corners. The results were checked against ngspice's own `.meas` (597.29 MHz for `CS_Pseudo_diff_N4.spice` and 628.56 MHz for `Ring_InvN3.spice` at nominal conditions).

---

## 1. Folder contents

```
osc_characterization/
├── osc_characterization.py        the script
├── README.md                      this document
├── CS_Pseudo_diff_N4.spice        4-stage differential oscillator with current load (example)
├── Ring_InvN3.spice               3-inverter ring, single output, no control (example)
├── CS_Pseudo_diff_N4.raw          already-run simulations, to try `analyze`
├── Ring_InvN3.raw
└── configs/
    ├── cs_diff_base.json          common settings of the differential oscillator (the others inherit from it)
    ├── cs_diff_nominal.json       ibias sweep, netlist conditions
    ├── cs_diff_worst3.json        ibias sweep over 3 PVT corners
    ├── cs_diff_pvt45.json         ibias sweep over the full PVT grid (45 corners)
    ├── cs_diff_mc.json            Monte Carlo (split) at one operating point
    ├── cs_diff_analyze.json       analyzes a .raw of the differential oscillator
    ├── ring_vdd.json              VDD sweep of the ring
    └── ring_analyze.json          analyzes a .raw of the ring
```

## 2. Requirements

- Python 3 and `ngspice` in the `PATH` (or give its location with `--ngspice /path/to/ngspice`).
- Python libraries:

```bash
pip install spicelib numpy scipy matplotlib --break-system-packages
```

The script only reads `.raw` files in ngspice format (through `spicelib`); it does not depend on any particular PDK.

## 3. Quick start

```bash
cd osc_characterization

# a) Analyze a simulation you already have (.raw)
python3 osc_characterization.py --config configs/cs_diff_analyze.json

# b) Sweep the bias current of the differential oscillator
python3 osc_characterization.py --config configs/cs_diff_nominal.json

# c) The same in the three PVT corners (ss/125 °C/3.0 V, typical/60 °C/3.3 V, ff/-40 °C/3.6 V)
python3 osc_characterization.py --config configs/cs_diff_worst3.json
```

Without a JSON file, the equivalent of (a) is:

```bash
python3 osc_characterization.py analyze CS_Pseudo_diff_N4.raw \
  --pos "v(n1)" --neg "v(n3)" --vdd 3.3 --isupply "i(v7)" --icore "i(v1)" --probe "v(vcs)" \
  --phase-ref "v(n13)" --phase-sig "v(n24)" --phase-expected -90
```

## 4. Subcommands and supported cases

| Subcommand | What it does | Needs |
|---|---|---|
| `analyze` | Characterizes **one** `.raw` (all the metrics of section 5) | the `.raw` |
| `sweep` | Runs ngspice varying **one line** of the netlist, analyzes each point and builds the tuning curve; optionally repeats the sweep over several PVT corners | the `.spice` netlist |
| `mc` | Monte Carlo (global variation and/or mismatch of the gf180mcuD PDK). **One** control value = MC at one point; **several** = per-sample tuning curves | the `.spice` netlist |
| `tuning` | Builds the tuning curve from `.raw` files you already have (does not run ngspice) | one `.raw` per point |

If you omit the subcommand and give a `.raw`, `analyze` is assumed (`python3 osc_characterization.py file.raw --pos ...`).

**Oscillator and signal types**

| Case | How to indicate it |
|---|---|
| Differential, with both nodes | `--pos "v(n1)" --neg "v(n3)"` (the script computes pos − neg and also the common mode) |
| Differential already built in the netlist (`E` source) | `--signal "v(n13)"` |
| **Single output** (ring, relaxation, etc.) | `--signal "v(n1)" --single-ended` |
| With a control parameter (current, control voltage...) | `sweep` with `--line-prefix`, `--template` and `--values` |
| **No** control parameter, free-running | `analyze`, or `sweep` over `VDD`/`TEMP` (see the ring example) |
| Several outputs with a phase relationship (I/Q, multiphase) | `--phase-ref` and `--phase-sig` |
| Transient noise included in the simulation | `--noisy` (removes the "numerical-only jitter" note) |

## 5. Analyses performed

All metrics are computed **in steady state** (section 5.2). In the report (`osc_summary.txt`) they appear in this order.

### 5.1 Check that the simulation is adequate
Before measuring, the script checks that the `.tran` is sufficient and issues warnings:

- **Points per period** in the worst case (threshold `--min-ppp`, 20). If the step is too coarse, the frequency, jitter and harmonics degrade.
- **Steady-state cycles** (threshold `--min-cycles`, 10). With few cycles the statistics are not reliable.
- **Steady state reached**: warns if it was not clearly detected.
- **Signal that looks single-ended** (large DC offset relative to the swing): suggests `--single-ended`.

When something does not comply, it **suggests a ready-to-paste `.tran`**: step ≈ T/200 rounded to 1-2-5 and stop time = start of steady state + `--target-cycles` (50) periods. The warnings appear at the top of the report, in `osc_metrics.json` (`warnings`; the `suggested_tran` key exists only when there is something to fix) and, in sweeps, as a warning-count column.

### 5.2 Steady-state detection
The amplitude and period of **each cycle** are measured; the final value is the median of the last quarter of the simulation. Steady state starts at the first cycle from which the amplitude stays within ±2 % (`--amp-tol`) and the period within ±0.5 % (`--freq-tol`) of that final value, plus 2 cycles of margin. If it does not settle with at least 6 cycles of margin, the second half of the simulation is used and a warning is issued. You can force the start with `--t-start`.

### 5.3 Frequency and period
Linear fit of the rising crossings of the threshold (by default, the mid level of the signal; change it with `--threshold`). It reports frequency, period and their spread. `--freq` is optional and only serves to show the deviation from an expected value.

### 5.4 Amplitude and common mode
Differential amplitude (peak, peak-to-peak, rms), extremes, offset and asymmetry between peaks; for each node, its range and mean value; common mode (mean value and ripple, which normally appears at 2·f0). `--probe` adds extra nodes (mean and ripple), for example the tail voltage.

### 5.5 Start-up
Times at 10 % and 90 % of the final amplitude, exponential growth rate and amplitude and frequency settling times. If the first cycle is already close to the final amplitude (because of a very aggressive `.ic`), the script says so and the times are reported as "already reached". With `.ic`/`uic` the start-up begins from an imposed imbalance, not from noise, so it is useful to **compare** designs or corners, not as an absolute value.

### 5.6 Power and energy
Mean current over whole periods → power and energy per cycle. `--isupply` is the **total** current of the supply; `--icore` is the **core** current (without reference or bias branches), and they are reported separately. The voltage is taken from `--vdd` or, if it varies, from a trace (`--vsupply "v(vdd)"`).

### 5.7 Jitter
TIE (time interval error) relative to the ideal grid fitted by least squares, period jitter and cycle-to-cycle jitter, for rising and falling edges. **Without transient noise**, this jitter is only numerical (the simulator's integration error) and serves as a reference floor; the real phase noise is estimated separately (for example with `isfpn.py`).

### 5.8 Eye diagram
The waveforms are folded onto the ideal grid (window of `--ui-window` periods, `--oversample` points per period) to obtain the eye, duty cycle, slew rate and 10–90 % rise/fall times.

### 5.9 Spectrum (coherent FFT)
An **integer** number of periods is taken and resampled with a cubic spline to `--ppp` points per period, so the harmonics fall exactly on a bin and there is no spectral leakage (`--window rect`; `hann` is optional). It reports the fundamental, `--nharm` harmonics in dBc and the **THD**. If there are few points per period, it warns from which harmonic onward the result is not reliable.

### 5.10 Phase between outputs
Phase of each `--phase-sig` signal with respect to `--phase-ref`, measured from the FFT fundamental and from zero crossings (both must agree). **Convention: positive = the signal LAGS the reference**; for example, in the differential oscillator `v(n24)` leads `v(n13)` by 90°, so the expected phase is −90. With `--phase-expected` (one per signal, in the same order) it reports the error. It also accepts expressions such as `v(n1)-v(n3)`.

### 5.11 Tuning curve (`sweep` / `tuning`)
For each control point it obtains frequency, differential amplitude, common mode, current, power, energy per cycle, THD, time to 90 %, phase and number of warnings. **Kvco = df/dctrl** is computed by numerical gradient, in Hz per axis unit (if you use `--ctrl-scale 1e-6`, it is Hz per µA). With only 2 valid points it is the slope between them; with 1 point it cannot be computed (`nan` in the CSV and a note in the plot instead of an empty panel).

### 5.12 PVT corners
With `--corner` / `--corners`, the whole sweep is repeated in each corner and a comparison is generated: overlaid curves, frequency range per corner, **range reachable in all corners at once** and (with `--target-f`) the control value needed in each corner for a given frequency, by linear interpolation.

## 6. Netlist requirements

The script **does not need a special netlist**, but it expects the following (your example netlist already complies):

- A `.control` block with `tran ... ` and `write file.raw`, and `save all` (or at least the signals you analyze). In `sweep` the script changes the name of the `.raw` automatically.
- For PVT corners:
  - a `.lib <file> <section>` line with the section `typical`, `ff`, `ss`, `fs` or `sf`;
  - `VDD=` and `TEMP=` inside a `.param` line (for example `.param VDD=3.3 TEMP=60`), and the rest of the netlist using `{VDD}` and `{TEMP}` (for example `.temp {TEMP}`). If there is no `TEMP=`, a `.temp 60` with a literal number is accepted.
- To vary a parameter: an element on **a single line** (for example `I0 VBP 0 500u`).

The PDK paths can be changed without touching the netlist with `--path-sub /old/path=/new/path` (repeatable).

## 7. Sweeps

### 7.1 Sweep of a control parameter
```bash
python3 osc_characterization.py sweep \
  --netlist CS_Pseudo_diff_N4.spice \
  --line-prefix I0 --template "I0 VBP 0 {v}" \
  --values 300u 400u 500u 600u 700u \
  --ctrl-label "I_bias (uA)" --ctrl-scale 1e-6 \
  --pos "v(n1)" --neg "v(n3)" --vdd 3.3 --isupply "i(v7)" --icore "i(v1)" \
  --outdir osc_sweep
```

- `--line-prefix`: name of the element (or directive) whose line is replaced; the **first** line that starts with that name is substituted.
- `--template`: the new line; `{v}` is replaced by each value.
- `--values`: accepts SPICE suffixes (`300u`, `1.2`, `2meg`).
- `--ctrl-scale`: divides the value for display (1e-6 → µA); it affects labels, tables, CSV and Kvco.

### 7.2 VDD or TEMP sweep (no control parameter)
The `.param` line is rewritten; the template must repeat the other parameters of that line:

```bash
python3 osc_characterization.py sweep \
  --netlist Ring_InvN3.spice \
  --line-prefix .param --template ".param VDD={v} TEMP=60" \
  --values 2.4 2.7 3.0 3.3 3.6 --ctrl-label "VDD (V)" \
  --signal "v(n1)" --single-ended --vsupply "v(vdd)" --isupply "i(v7)" \
  --outdir ring_vdd
```
(Since VDD changes, the power uses `--vsupply` instead of `--vdd`.)

### 7.3 Control sweep over PVT corners
```bash
python3 osc_characterization.py sweep \
  --netlist CS_Pseudo_diff_N4.spice \
  --line-prefix I0 --template "I0 VBP 0 {v}" \
  --values 300u 400u 500u 600u 700u --ctrl-label "I_bias (uA)" --ctrl-scale 1e-6 \
  --corners worst3 --target-f 600meg \
  --pos "v(n1)" --neg "v(n3)" --isupply "i(v7)" --icore "i(v1)" \
  --outdir sweep_pvt
```

- **Presets** (`--corners`, repeatable; they can be combined with each other and with `--corner`):

| Preset | Corners |
|---|---|
| `worst3` | `ss:125:3.0`, `typical:60:3.3`, `ff:-40:3.6` |
| `process5` | the 5 process corners (typical, ff, ss, fs, sf) at 60 °C and 3.3 V |
| `pvt45` | full grid: 5 processes × {-40, 27, 125 °C} × {3.0, 3.3, 3.6 V} (the same as in `pvt_runner.py`) |
| `pvt27` | the same with 3 processes (typical, ff, ss) |
| `temp3` | temperature only: typical, 3.3 V, -40/27/125 °C |
| `vdd3` | supply only: typical, 27 °C, 3.0/3.3/3.6 V |

  More presets are added by editing the `PRESETS` dictionary of the script (a list of `"process:temp:vdd"` strings). Mind the cost: the number of simulations is corners × control values (`pvt45` with 5 values = 225 runs), so it is advisable to use `--jobs`. With more than 6 corners, the comparison figure uses color = process, line style = VDD and opacity = temperature (lighter = colder), the same as `pvt_runner.py compare-all`.
- **Individual corners** (`--corner NAME:TEMP:VDD`, repeatable): `--corner ss:125:3.0 --corner typical:27:3.3`. `NAME` can be `typical` (or `tt`), `ff`, `ss`, `fs`, `sf`.
- The control values are the same in all corners.
- On screen, **one line per corner** is shown (frequency range, number of warnings and failed points) and, at the end, the comparison; the detail of each corner is left in `<corner>/analysis.log`. With `--verbose` (`"verbose": true` in the JSON) everything is printed on screen as before.
- Do not use `--vdd` in this mode: the power is computed with the VDD of each corner.

### 7.4 Tuning curve from already-simulated `.raw` files
```bash
python3 osc_characterization.py tuning \
  --run 300u:a.raw --run 400u:b.raw --run 500u:c.raw \
  --ctrl-label "I_bias (uA)" --ctrl-scale 1e-6 \
  --pos "v(n1)" --neg "v(n3)" --vdd 3.3 --isupply "i(v7)"
```

## 7b. Monte Carlo (`mc`)

A single subcommand; the number of control values defines the case:

- **One value** (or none, the netlist as is): MC at one operating point (histogram, σ, yield).
- **Several values**: each sample (seed) is simulated at all the values; you get the per-sample tuning curve, the per-sample Kvco and the range covered by ~90 % of the samples ([p95 of fmin, p5 of fmax]).

Modes (`--mc-mode`):

| Mode | What varies | Allowed corners |
|---|---|---|
| `mismatch` | only mismatch between transistors (`sw_stat_mismatch=1`) | **any** (`--corner`/`--corners`: ss, ff, fs, sf, typical, presets) |
| `global` | only global process variation (`sw_stat_global=1`) | typical only |
| `both` | global + mismatch | typical only |
| `split` | runs the three and reports the variance split (σ²_both vs σ²_g+σ²_m) | mismatch in all; global/both only in typical (with a warning) |

Reason: the `statistical` section of the PDK is centered on typical and replaces the corner section, so global/both make no sense in ss/ff. Mismatch (`fets_mm`) does work on any deterministic corner.

```bash
python3 osc_characterization.py mc --netlist CS_Pseudo_diff_N4.spice \
  --line-prefix I0 --template "I0 VBP 0 {v}" --values 500u \
  --ctrl-scale 1e-6 --pos "v(n1)" --neg "v(n3)" --isupply "i(v7)" --vdd 3.3 \
  --corners worst3 --mc-mode split --mc-n 100 --spec f:560meg:640meg \
  --jobs 4 --threads 1 --outdir results/mc
# or with JSON: python3 osc_characterization.py --config configs/cs_diff_mc.json
```

Options: `--mc-n` (samples, default 100), `--mc-seed` (master seed; the same list of seeds is used in all cases, modes and control values), `--mc-skew` (3 = 1σ of the PDK), `--spec METRIC:MIN:MAX` (repeatable, for the yield), `--min-amp` (fraction of VDD below which the sample is considered "not oscillating" and counts as a failure, default 0.05), `--keep-raw`, `--no-mc-plots`.

Outputs: `mc_samples.csv` (one row per simulation), `mc_summary.csv`, `mc_report.txt`, `mc_split.csv`, `mc_hist*.png`, `mc_tuning.png`, `mc_split.png`, `mc_corners.png`; folders `<corner>/<mode>/runs/`.

Cost = cases × values × (1 nominal + modes × N). Standard error of σ ≈ σ/√(2(N−1)): N=100 → ~7 %, N=200 → ~5 %. Samples that do not oscillate (or have no measurable frequency) are marked as failures and lower the yield; they do not enter the mean/σ.

## 8. Output files

**`analyze`** (`--outdir` folder, `osc_analysis/` by default)

| File | Contents |
|---|---|
| `osc_summary.txt` | full report (the same one that is printed) |
| `osc_metrics.json` | all metrics, warnings and suggested `.tran`, to process them with other scripts |
| `osc_overview.png`, `osc_eye.png`, `osc_jitter.png`, `osc_spectrum.png` | waveforms and start-up, eye, jitter, spectrum |
| `config_used.json` | effective options with which the analysis was made |

**`sweep` / `tuning`** (`--outdir` folder, `osc_sweep/` and `osc_tuning/` by default)

| File | Contents |
|---|---|
| `tuning.csv` | `ctrl, f, amp, vcm, idd, power, energy, t90, thd, kvco, phase, phase_err, nwarn, ok` (`ctrl` in scaled units; `f` in Hz; `power` in W; `energy` in J; `kvco` in Hz per unit of `ctrl`; `ok=0` if that point failed) |
| `osc_tuning.png` | f, Kvco, amplitude and common mode, power and energy per cycle (and phase and THD if `--phase-*` is given) |
| `runs/` | for each point: the modified netlist (`.spice`), the ngspice `.log` and the `.raw` |
| `run_<value>/` | report and metrics of that point |
| `analysis.log` | only with corners: the detail of the analysis of that corner (what used to be printed on screen) |
| `config_used.json` | effective options |

**With corners**, in addition: one subfolder per corner (`ss_125C_3V/`, `typical_60C_3.3V/`, `ff_-40C_3.6V/`, each with the above) and, in the main folder:

| File | Contents |
|---|---|
| `corners_tuning.png` | the curves of all corners overlaid (f, Kvco, amplitude, power, energy, THD or phase), with the total range shaded and the range common to all |
| `corners_summary.csv` | per corner: fmin, fmax, tuning range (%), mean Kvco, minimum and maximum power |
| `corners_tuning.csv` | frequency of each corner for each control value |

## 9. JSON configuration files

Everything that is passed on the command line can live in a JSON file, with the same name as the option (with hyphen or underscore). Example (`configs/cs_diff_worst3.json` inherits from `cs_diff_base.json`):

```json
{
  "_note": "ibias sweep at ss/125C/3.0V, typical/60C/3.3V and ff/-40C/3.6V; 600 MHz target",
  "extends": "cs_diff_base.json",
  "command": "sweep",
  "corners": ["worst3"],
  "target_f": "600meg",
  "jobs": 5,
  "outdir": "results/cs_diff_worst3"
}
```

- `command`: `analyze`, `tuning` or `sweep`. With that, `python3 osc_characterization.py --config file.json` is enough.
- `extends`: inherits another JSON (one or several); what is in the child file takes priority.
- **Command-line options take priority** over the JSON: `--config cs_diff_worst3.json --jobs 1 --outdir test`.
- The paths of input files (`netlist`, `raw_path`, `run` files) are **relative to the JSON**; `outdir` is relative to where you run.
- Lists are written as lists (`"values": ["300u", "400u"]`); switch options (`single_ended`, `noisy`) are `true`/`false`; `path_sub` accepts a list of `"OLD=NEW"` or an object `{"old": "new"}`.
- Whole-line comments starting with `//` and keys starting with `_` are allowed.
- An unknown key gives an error with a suggestion (`did you mean ['netlist']?`).
- **`--save-config file.json`** turns a command that already worked for you into a JSON (it writes the file and exits, it does not simulate).
- Every run leaves a `config_used.json` in its output folder, reusable with `--config` to repeat it.

## 10. Performance and parallelism

| Option | Default | Purpose |
|---|---|---|
| `--jobs N` | 1 | parallel ngspice simulations |
| `--threads N` | 1 | threads per ngspice process (`set num_threads=N` is forced in the `.control` of each run; `0` = leave untouched) |
| `--omp-wait` | `auto` | `OMP_WAIT_POLICY` policy: untouched in serial; with `jobs>1` only `passive` if `--threads 0` or `jobs × threads` exceeds the CPUs |
| `--timeout S` | 300 | maximum time per run; a stuck run is marked `FAILED` and the sweep continues (0 = no limit) |

Recommendations (measured with another tool in the repo, `isfpn.py`, on a machine with 16 physical cores):

- **Several single-thread processes beat a few processes with several threads**; that is why `--threads 1` is the default.
- Raise `--jobs` up to the number of **physical** cores at most.
- The total time is "rounds × time per run": with 15 runs, `--jobs 5` gives exactly 3 rounds; `--jobs 4` gives 4. The script warns at the start if with fewer jobs you would get the same number of rounds.
- If ngspice in your environment uses many threads per process (a `set num_threads=8` in `.spiceinit`, for example), `--threads 1` overrides it.
- The results are identical for any `--jobs`.
- If a run fails (does not converge, timeout), the sweep continues; the script exits with an error only if **all** of them fail.

## 11. Use as a library

```python
from osc_characterization import characterize, default_config

cfg = default_config(pos="v(n1)", neg="v(n3)", vdd=3.3, isupply="i(v7)")
res, report = characterize("run.raw", cfg, outdir="out", plots=False)
res["freq"]["f"], res["amplitude"]["diff"]["amp"], res["warnings"], res.get("suggested_tran")  # only exists if there is something to fix
```

Intended to be reused from future PVT and Monte Carlo scripts.

## 12. Limitations and notes

- **Monte Carlo** and **phase noise** (Hajimiri's ISF) are not yet integrated; phase noise is estimated with `Python_tools/isfpn/isfpn.py`.
- `sweep` varies **one** control parameter at a time, and the same values are used in all corners.
- The line to be replaced must be on **a single line** (`+` continuations are not handled). With `--line-prefix .param` only the **first** `.param` line is rewritten, which is why the template must repeat the other parameters.
- In PVT corners, `VDD` and `TEMP` must be parameters (`.param`); if VDD appears as a fixed number in a source, the script cannot change it.
- With `.ic` and `uic` the start-up is by imposed imbalance, not by noise: the start-up times are useful for comparison, not as an absolute value.
- Simulations without noise give only numerical jitter (the simulator floor).
- For simulations in which the oscillator does not start (for example, in a slow corner), the point is reported with warnings or as `ok=0`, and the sweep continues.

## 13. Troubleshooting

| Symptom | Cause and solution |
|---|---|
| `The line to replace was not found` | `--line-prefix` does not match the start of any netlist line |
| `The netlist has no 'write file.raw' line` | `write file.raw` is missing inside `.control` |
| `No '.lib <file> <section>' line ...` | with corners, the netlist needs a `.lib` with the section `typical`, `ff`, `ss`, `fs` or `sf` |
| `No 'VDD=' found in a .param line` | with corners, `VDD=` and `TEMP=` must be in a `.param` |
| `file dialect is not specified` / error reading the `.raw` | a `.raw` that is not from ngspice, or an outdated `spicelib` |
| `ngspice did not produce ...raw` | check the `.log` of that run in `runs/` (PDK path, convergence) |
| `ngspice timed out` | stuck run; raise `--timeout` or check the `.log` |
| Warnings about few points per period or few cycles | use the `.tran` suggested in the report |
| The system becomes slow with a high `--jobs` | lower `--jobs`; keep `--threads 1` |
| `Error: unknown key ... in config.json` | misspelled key in the JSON |
