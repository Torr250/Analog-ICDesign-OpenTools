# pll_characterization.py

Time-domain characterization of a **PLL** from **ngspice** transient simulations: final frequency, **lock time** (several criteria), overshoot, static phase error, control-voltage behaviour, clock jitter and supply power. It can analyze one `.raw`, or **simulate and compare several cases** (PVT corners, each one with its own parameter values).

The script is **self-contained**: it does not import `osc_characterization.py`. Its few shared helpers (reading the `.raw`, threshold crossings, linear fit) were adapted from it, and `selftest` checks that they still agree with it.

---

## 1. Folder contents

```
pll_characterization/
├── pll_characterization.py              the script
├── README.md                            this document
├── TB_gf180_cyc_pll_pfd_cp_div.spice    example testbench: 25 MHz x 20 = 500 MHz, ideal VCO, Young charge pump
└── configs/
    ├── pll_base.json                    common settings (inherited by the others)
    ├── pll_ss125.json                   one case: ss / 125 C / 3.0 V
    └── pll_worst3.json                  ss/125C/3.0V, typical/60C/3.3V, ff/-40C/3.6V
```

The testbench is the author's netlist with **parameters exposed** so that every case can change them: `ICP` (charge-pump bias current), `RZ`, `CZ` (loop filter), `F0`, `KVCO`, `VC0` (ideal VCO), and the VCO supply now follows `VDD` (`vdd={VDD}`). The default values are the original ones. A second `write` with an absolute path was removed. The netlist keeps the paths of the author's environment (`/foss/designs/...`); on another machine redirect them with `path_sub` (see `configs/pll_base.json`).

## 2. Requirements

```bash
pip install spicelib numpy scipy matplotlib prettytable --break-system-packages
```
and `ngspice` in the `PATH` (or `--ngspice /path/to/ngspice`). `prettytable` >= 3.12 is required (it provides `TableStyle`). Tested with ngspice 42.

## 3. Quick start

```bash
cd pll_characterization

# 0) check the helpers against osc_characterization (597.29 MHz on its example .raw)
python3 pll_characterization.py selftest

# a) analyze a simulation you already have
python3 pll_characterization.py analyze TB_gf180_cyc_pll_pfd_cp_div.raw \
  --fref 25meg --n-div 20 --vdd 3.0 --isupply "i(v7)" --outdir pll_analysis

# b) simulate and analyze one case (ss / 125 C / 3.0 V)
python3 pll_characterization.py --config configs/pll_ss125.json

# c) the three worst corners
python3 pll_characterization.py --config configs/pll_worst3.json --jobs 3
```

Command-line options take priority over the JSON. Signals default to `v(clk) v(ref) v(fb) v(vctrl)` (change with `--clk --ref --fb --vctrl`).

## 4. What it measures

The console report starts with a **summary table** (key figures) and then the numbered sections; the lock-time matrix, the harmonics and the reference spurs are tables too. `run` ends with a **case-comparison table**. The same text is saved in `pll_summary.txt` and `cases_summary.txt`.

All "final" values use the last 20 % of the simulation (`--final-frac`, or `--t-final`).

| Section | Metrics |
|---|---|
| Frequency | `f_clk`, `f_fb`, error in ppm against `N*fref` and `fref` (`fref` and `N` are measured if not given); steady-state ripple of the instantaneous frequency (fb, clk over N cycles, clk per cycle) |
| Lock time | for each tolerance (default 0.5 %, 0.1 %, 100 ppm, 10 ppm): instantaneous frequency of **fb** (one ref period), of **clk averaged over N cycles**, and of **clk per cycle**; plus a **phase** criterion |
| Transient | initial frequency error, peak overshoot, undershoot after the peak, damping estimate (when two peaks exist) |
| Phase error | static value, ripple and rms of the ref -> fb error (positive = fb lags) |
| vctrl | final value, ripple, minimum and maximum (rail headroom) |
| Clock quality (locked window) | jitter of `clk` (rising and falling TIE, period, cycle-to-cycle, duty cycle); eye diagram (amplitude, height, width, 10-90 % rise/fall); coherent spectrum (fundamental, harmonics in dBc, THD); **reference spurs** at `f_clk +- m*fref`; spectrum of `vctrl` at `m*fref` and the spur predicted from it |
| Power | mean supply current and power (`--isupply`, `--vdd`) |

### 4.1 Lock criteria

- **Lock time = the last moment the signal is outside the band** (not the first time it enters), so the swings of the overshoot are not counted. If the simulation ends outside the band the result is `not locked`.
- **fb frequency (1 ref period)**: `1/(t_k - t_{k-1})` of consecutive fb edges. It is free of the charge-pump ripple, so it is the cleanest option; its resolution is one ref period.
- **clk over N cycles**: the same idea measured on the VCO output, averaged over the N cycles of one ref period. It agrees with fb within about one ref period.
- **clk per cycle**: contains the ripple of `vctrl` (about 600 ppm pp in the example), so it is only reliable for loose tolerances (the script warns when a tolerance is below the steady-state ripple of fb).
- **Phase**: `|phase error - final value| < --phase-tol * Tref` (default 0.5 % of Tref).

Frequency lock does not imply phase lock: the frequency can be inside a band while the phase error is still moving.

### 4.2 Clock quality in the locked window

Computed on the same final window (check that it starts after the lock time you care about; the script warns otherwise).

- **Eye**: the waveform is folded on the ideal grid (fitted period) over 2 UI. Height = lowest "high" minus highest "low" at the centre of each half period; width = time at mid-level during which every cycle is on the same side (it shrinks with jitter and duty-cycle error).
- **Spectrum**: coherent sampling (an integer number of clk cycles that is also an integer number of ref periods), resampled with a cubic spline to 64 points per period, rectangular window: no leakage, harmonics and spurs fall exactly on a bin. The resolution is `f_clk / cycles`, so a longer locked window resolves smaller offsets.
- **Reference spur**: `vctrl` is analyzed over the same window. With `--kvco` the spur is predicted as `20*log10(beta/2)`, `beta = Kvco*A(fref)/fref` (narrow-band FM), and compared with the measured sideband. In the example both agree within 0.2 dB (-66.1 vs -66.3 dBc), which is a good check of the whole chain. In `run`, `KVCO` given in a case's `params` is used for that case.
- **A simulation without transient noise shows only deterministic jitter**: it is periodic with `fref` (the TIE plot is a sawtooth every ref period) and is the time-domain image of the reference spur, on top of a numerical floor. Thermal and flicker noise are not included; for them use a noisy VCO model (`vco_ideal_noisy`) or `isfpn`. In the same way the eye is a single trace when there is no noise.
- Options: `--kvco`, `--nharm` (default 11), `--no-clock` to skip it.

### 4.3 Details worth knowing

- The first fb intervals (divider start-up from its initial state) are not settled periods; overshoot and ringing ignore the first `--skip-ref` ref periods (default 2).
- With `.ic v(vctrl)=...` and `uic`, the acquisition starts from that imposed value, so lock times are good for **comparing** corners or designs, not as an absolute figure.
- If the acquisition is slew-limited (large initial error, charge-pump pulses saturating `vctrl`), the response is not a linear step response and the damping estimate does not apply; it appears as `n/a` when fewer than two peaks are found.
- `i(v7)` is the current of the supply that feeds the PFD, charge pump and dividers. An **ideal behavioral VCO has no supply pin**, so the VCO power is not included.

## 5. Cases: corners with their own parameters

The `run` subcommand changes the netlist for each case and runs ngspice in its own folder (`<outdir>/<case>/`). A case can be a corner, a set of parameter values, or both.

```json
{
  "extends": "pll_base.json",
  "command": "run",
  "preset": ["worst3"],
  "common_params": {"ICP": "400u", "KVCO": "35meg"},
  "overrides": {
    "ss_125C_3V":       {"params": {"ICP": "450u"}},
    "ff_-40C_3.6V":     {"params": {"ICP": "350u", "KVCO": "30meg"},
                         "subs": [["sharp=8", "sharp=10"]]}
  }
}
```

- **Corners**: `--preset worst3 | process5 | temp3 | vdd3`, and/or `--corner process:temp:vdd` (repeatable). `worst3` = `ss:125:3.0`, `typical:60:3.3`, `ff:-40:3.6`. The case name is `<process>_<temp>C_<vdd>V` (for example `ss_125C_3V`).
- **Explicit cases** (JSON key `cases`): a list of objects such as `{"corner": "ss:125:3.0", "name": "ss_icp300", "params": {"ICP": "300u"}}`.
- **Per-case values** (in `cases` or in `overrides`, which is keyed by the case name):

| Key | Effect |
|---|---|
| `params` | `{"NAME": "value"}` rewrites `NAME=` in the `.param` lines (it is added if missing). This is the recommended way |
| `bus` | `{"DV": "1111110"}` sets `DV6..DV0` (leftmost character = highest index; `"bus_lsb_first": true` flips it) to 0/1 in the `.param` lines, for digital words such as a thermometer-coded VCO selector. The netlist must define `DV0..DV6` and use them (e.g. `VDVCO0 dvco0 0 {DV0*VDD}`) |
| `edits` | `{"I0": "I0 VDD net2 300u"}` replaces the whole line whose first word is that name |
| `subs` | `[["old text", "new text"]]` literal replacement in the whole netlist (error if not found) |

- **Applied automatically**: the `.lib <file> <section>` section (`typical`, `ff`, `ss`, `fs`, `sf`) and `VDD=` / `TEMP=` in a `.param` line. `--tstop` and `--tstep` change the `.tran`.
- Errors in a case (unknown parameter line, ngspice failure, timeout) mark that case as failed and the rest continue.

### Outputs

| File | Contents |
|---|---|
| `cases_summary.txt` | the case-comparison table printed at the end of `run` (one column per case) |
| `cases_summary.csv` | one row per case: frequency, lock times, overshoot, phase error, vctrl, jitter, eye, THD, reference spur, power |
| `cases_comparison.png` | f_fb deviation, vctrl and phase error of all cases overlaid |
| `cases_metrics.json` | all the metrics of all the cases |
| `<case>/pll_summary.txt`, `pll_metrics.json`, `pll_overview.png`, `pll_eye.png`, `pll_jitter.png`, `pll_spectrum.png`, `pll_supply.png` | report, metrics and plots of that case (eye diagram; jitter histograms + TIE; clk and vctrl spectra; supply current). Curves are coloured by process: ff blue, typical green, ss red |
| `<case>/pll_case.spice`, `ngspice.log` | the netlist actually simulated and the ngspice log |

The `.raw` is deleted after the analysis (it weighs about 200 MB for 3 us at 10 ps); keep it with `--keep-raw`. `--save "v(ref)" "v(fb)" ...` replaces `save all` by a list of vectors.

## 6. Cost and parallelism

The example (3 us, step 10 ps, transistor-level PFD/CP/dividers) takes about 100 s per case. `--jobs N` runs cases in parallel (use at most the number of physical cores); `--threads 1` (default) keeps one thread per ngspice process, as in `osc_characterization`.

## 7. Netlist requirements

- A `.control` block with `tran ...` and a `write file.raw` line (the script rewrites the name) and `save all` (or at least `ref`, `fb`, `clk`, `vctrl` and the supply current).
- For corners: a `.lib <file> <section>` line with a process section, and `VDD=`, `TEMP=` in a `.param` line (the rest of the netlist should use `{VDD}` and `{TEMP}`, including the VCO supply).
- For `params`: the parameter must be used in the netlist as `{NAME}`.
- Path changes without touching the netlist: `--path-sub /old/path=/new/path` (repeatable) or `path_sub` in the JSON. **Use absolute paths for the new side**: a relative one in a JSON is relative to the JSON file, not to the repository. Before running ngspice the script checks that every absolute `.include` / `.lib` path of the netlist exists and, if not, reports the missing files instead of an ngspice error. If the netlist already has valid paths (as in the author's environment) no `path_sub` is needed.

## 8. Use as a library

```python
from pll_characterization import analyze_pll
cfg = dict(clk="v(clk)", ref="v(ref)", fb="v(fb)", vctrl="v(vctrl)", fref="25meg", n_div=20)
res = analyze_pll("run.raw", cfg)
res["final"]["f_clk"], res["lock_freq"][0]["fb"], res["phase"]["static_s"]
```

## 9. Limitations

- Single clock domain, one `ref`/`fb`/`clk` triplet. A fractional-N divider (average N) is not handled: give `--n-div` and use the N-cycle or fb criteria with care.
- The jitter is deterministic only (see 4.2); phase noise is not computed; use `Python_tools/isfpn/isfpn.py` for an oscillator and a noisy VCO (`vco_ideal_noisy`) in the loop for closed-loop jitter.
- Monte Carlo is not integrated.
