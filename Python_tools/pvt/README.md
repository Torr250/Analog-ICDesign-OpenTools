# pvt — Process / Voltage / Temperature sweeps

| File | Purpose |
|---|---|
| `pvt_runner.py` | Full PVT sweep of the `TB_not` testbench (CMOS inverter, gf180mcuD): corner × temperature × VDD. Generates one netlist per combination from a template, runs ngspice, collects the `.meas` results in a CSV and keeps one `.raw` per combination. Also compares waveforms between corners. |
| `analyze_pvt.py` | Worst/best-case summary per metric, grouped by physical quantity (time, current, efficiency), with plots (worst/best per corner, heatmaps, boxplots). |

Default sweep (edit `CORNERS`, `TEMPS`, `VDDS` at the top of `pvt_runner.py`): corners `typical, ff, ss, fs, sf`; temperatures `-40, 27, 125` °C; VDD `3.0, 3.3, 3.6` V.

## Requirements

```
pip install spicelib numpy pandas matplotlib --break-system-packages
```
and `ngspice` in the `PATH`.

## Netlist template (not included)

`pvt_runner.py` expects `TB_not_template.spice` in the working directory, whose `.control` block writes `TB_not.raw`. The runner substitutes corner, `TEMP` and `VDD`, and redirects the output to `pvt_raws/tb_not_<corner>_<temp>C_<vdd>V.raw`. The template is **not part of this folder**; supply your own testbench. `compare-all` recovers the PVT parameters from those file names, so do not rename the `.raw` files.

## Usage

```bash
# 1) Sweep -> pvt_results.csv + pvt_raws/*.raw
python3 pvt_runner.py sweep --jobs 8

# 2) Waveforms of several corners at fixed temperature / VDD -> pvt_analysis/
python3 pvt_runner.py compare --temp 125 --vdd 3.0 --corners typical ss ff

# 3) All combinations in one figure (color = corner, line = VDD, opacity = temperature)
python3 pvt_runner.py compare-all --signals "v(outb)" "v(in)"

# 4) Summary and plots from the CSV -> pvt_analysis/
python3 analyze_pvt.py pvt_results.csv
```

To reuse `analyze_pvt.py` with another circuit, edit the column groups (`TIME_COLS`, `CURRENT_COLS`, `EFFICIENCY_COLS`, `MEAS_GROUPS`) to match the `.meas` names of your netlist; nothing else needs to change.
