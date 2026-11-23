#!/usr/bin/env python3
"""
pvt_runner.py

Runs the full PVT sweep (corner x temp x VDD): generates one netlist per
combination from a template, runs ngspice, collects the scalar .meas
results in a CSV, and saves a unique .raw per combination. It also offers
commands to compare waveforms between corners.

Requires:
    pip install spicelib --break-system-packages

Usage:
    # 1) Run the full sweep (generates CSV + one .raw per combination)
    python3 pvt_runner.py sweep
    python3 pvt_runner.py sweep --jobs 8      # 8 combinations in parallel

    # 2) Generate a waveform comparison between corners, for a fixed
    #    temperature and VDD (default: nominal temp / nominal vdd)
    python3 pvt_runner.py compare
    python3 pvt_runner.py compare --temp 125 --vdd 3.0
    python3 pvt_runner.py compare --corners typical ss ff

    # 3) Plot ALL the PVT combinations together in a single figure
    #    (color = corner, line = VDD, opacity = temperature)
    python3 pvt_runner.py compare-all
    python3 pvt_runner.py compare-all --signals "v(outb)" "v(in)"
    python3 pvt_runner.py compare-all --corners typical ss ff --vdds 3.0 3.6
"""

import argparse
import csv
import itertools
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt

try:
    from spicelib.raw.raw_read import RawRead
except ImportError:
    RawRead = None

# ----------------------------------------------------------------------
# Configuration (same as pvt_runner.py, plus the .raw directory)
# ----------------------------------------------------------------------

TEMPLATE = "TB_not_template.spice"
WORKDIR = "pvt_runs"
RAWDIR = "pvt_raws"
OUTPUT_CSV = "pvt_results.csv"
PLOTDIR = "pvt_analysis"

CORNERS = ["typical", "ff", "ss", "fs", "sf"]
TEMPS = [-40, 27, 125]
VDDS = [3.0, 3.3, 3.6]

MEAS_NAMES = ["trise", "tfall", "tplh", "tphl", "tpd_avg", "ivdd_rms", "effy"]

# Name of the .raw file as it appears in the "write ..." of the original template
TEMPLATE_RAW_NAME = "TB_not.raw"


# ----------------------------------------------------------------------
# Sweep: generates netlists, runs ngspice, saves CSV + .raw
# ----------------------------------------------------------------------

def fmt_num(x: float) -> str:
    """Formats a number the same way whether it arrives as int or float (27 and 27.0 -> '27')."""
    return str(int(x)) if float(x).is_integer() else str(x)


def raw_path_for(corner: str, temp: float, vdd: float) -> str:
    return os.path.join(RAWDIR, f"tb_not_{corner}_{fmt_num(temp)}C_{fmt_num(vdd)}V.raw")


def build_netlist(template_text: str, corner: str, temp: float, vdd: float, raw_path: str) -> str:
    """Substitutes corner, TEMP, VDD, and redirects the 'write' to a unique .raw."""
    netlist = template_text.replace("__CORNER__", corner)
    netlist = re.sub(r"VDD=[\d.]+", f"VDD={vdd}", netlist)
    netlist = re.sub(r"TEMP=[\d.\-]+", f"TEMP={temp}", netlist)
    # We redirect the write TB_not.raw -> write pvt_raws/tb_not_<corner>_<temp>_<vdd>.raw
    netlist = netlist.replace(f"write {TEMPLATE_RAW_NAME}", f"write {raw_path}")
    return netlist


def run_ngspice(netlist_path: str) -> str:
    result = subprocess.run(["ngspice", "-b", netlist_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [!] ngspice returned code {result.returncode} for {netlist_path}", file=sys.stderr)
        if result.stderr:
            print(f"      stderr: {result.stderr.strip()[:300]}", file=sys.stderr)
    return result.stdout


def parse_meas(stdout: str, meas_name: str):
    match = re.search(rf"\b{meas_name}\s*=\s*([\d.eE+\-]+)", stdout)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def run_one(template_text: str, combo: tuple) -> dict:
    """Executes ONE complete PVT combination (netlist -> ngspice -> parsing) and
    returns everything needed to report progress and write the CSV.
    This function is the unit of work that is sent to the thread pool."""
    corner, temp, vdd = combo
    raw_path = raw_path_for(corner, temp, vdd)
    netlist = build_netlist(template_text, corner, temp, vdd, raw_path)

    fname = os.path.join(WORKDIR, f"tb_not_{corner}_{fmt_num(temp)}C_{fmt_num(vdd)}V.spice")
    with open(fname, "w") as f:
        f.write(netlist)

    stdout = run_ngspice(fname)

    log_fname = fname.replace(".spice", ".log")
    with open(log_fname, "w") as f:
        f.write(stdout)

    row = {"corner": corner, "temp": temp, "vdd": vdd}
    for meas in MEAS_NAMES:
        row[meas] = parse_meas(stdout, meas)
    missing = [m for m in MEAS_NAMES if row[m] is None]

    return {
        "combo": combo,
        "row": row,
        "missing": missing,
        "raw_path": raw_path,
        "log_fname": log_fname,
        "raw_ok": os.path.isfile(raw_path),
    }


def cmd_sweep(args):
    jobs = args.jobs

    if not os.path.isfile(TEMPLATE):
        print(f"Error: template '{TEMPLATE}' not found in the current directory.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(WORKDIR, exist_ok=True)
    os.makedirs(RAWDIR, exist_ok=True)

    with open(TEMPLATE, "r") as f:
        template_text = f.read()

    combinations = list(itertools.product(CORNERS, TEMPS, VDDS))
    total = len(combinations)
    # results indexed by position so they can be reordered at the end, since the
    # parallel combinations do not necessarily finish in the order in which
    # itertools.product generated them
    results = [None] * total
    done = 0

    print(f"Running {total} PVT combinations with {jobs} worker(s) in parallel "
          f"(saving an individual .raw per run)...\n")

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(run_one, template_text, combo): idx
                    for idx, combo in enumerate(combinations)}

        for future in as_completed(futures):
            idx = futures[future]
            combo = combinations[idx]
            outcome = future.result()

            results[idx] = outcome["row"]
            done += 1

            corner, temp, vdd = combo
            if not outcome["raw_ok"]:
                print(f"    [!] {corner}/{temp}C/{vdd}V: the expected .raw was not generated "
                      f"({outcome['raw_path']}); check {outcome['log_fname']}")
            if outcome["missing"]:
                print(f"    [!] {corner}/{temp}C/{vdd}V: could not extract "
                      f"{', '.join(outcome['missing'])} (check {outcome['log_fname']})")

            print(f"[{done}/{total}] corner={corner:8s} temp={temp:>4}C vdd={vdd}V completed")

    fieldnames = ["corner", "temp", "vdd"] + MEAS_NAMES
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. {len(results)} runs completed.")
    print(f"  Measurements CSV  : {OUTPUT_CSV}")
    print(f"  Netlists + logs   : {WORKDIR}/")
    print(f"  Waveforms (.raw)  : {RAWDIR}/")


# ----------------------------------------------------------------------
# Compare: reads the .raw files of several corners (same temp/vdd) and overlays them
# ----------------------------------------------------------------------

def load_waveform(raw_path: str, signal: str = "v(outb)"):
    """Returns (time, values) of a signal inside a .raw generated by ngspice."""
    if RawRead is None:
        raise RuntimeError(
            "spicelib is not installed. Install it with:\n"
            "    pip install spicelib --break-system-packages"
        )
    raw = RawRead(raw_path, dialect="ngspice")
    time = raw.get_trace("time").get_wave()
    values = raw.get_trace(signal).get_wave()
    return time, values


def cmd_compare(args):
    corners = args.corners if args.corners else CORNERS
    temp = args.temp
    vdd = args.vdd
    signals = args.signals

    os.makedirs(PLOTDIR, exist_ok=True)

    missing_raws = []
    for corner in corners:
        rp = raw_path_for(corner, temp, vdd)
        if not os.path.isfile(rp):
            missing_raws.append(rp)
    if missing_raws:
        print("Error: these .raw files were not found (did you run 'sweep' first with these same temp/vdd?):",
              file=sys.stderr)
        for rp in missing_raws:
            print(f"  - {rp}", file=sys.stderr)
        sys.exit(1)

    for signal in signals:
        fig, ax = plt.subplots(figsize=(9, 5))
        for corner in corners:
            rp = raw_path_for(corner, temp, vdd)
            time, values = load_waveform(rp, signal=signal)
            # time in ns so that the axis is readable
            ax.plot(time * 1e9, values, label=corner)

        ax.set_xlabel("Time (ns)")
        ax.set_ylabel(f"{signal} (V)")
        ax.set_title(f"Comparison between corners — {signal}  (temp={temp}°C, vdd={vdd}V)")
        ax.legend(title="Corner")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_signal = signal.replace("(", "").replace(")", "")
        fname = os.path.join(PLOTDIR, f"waveform_compare_{safe_signal}_{temp}C_{vdd}V.png")
        plt.savefig(fname, dpi=150)
        plt.close()
        print(f"Saved: {fname}")


# ----------------------------------------------------------------------
# Compare-all: overlays ALL the generated .raw files (all the
# corner/temp/vdd combinations) in a single figure, encoding each variable visually
# ----------------------------------------------------------------------

RAW_FILENAME_RE = re.compile(r"tb_not_(?P<corner>.+?)_(?P<temp>-?\d+(?:\.\d+)?)C_(?P<vdd>\d+(?:\.\d+)?)V\.raw$")

_LINESTYLES = ["-", "--", "-.", ":"]


def discover_raws(raw_dir: str):
    """Scans raw_dir and returns a list of dicts {path, corner, temp, vdd}
    parsed directly from the file name generated by 'sweep'."""
    entries = []
    if not os.path.isdir(raw_dir):
        return entries
    for fname in sorted(os.listdir(raw_dir)):
        m = RAW_FILENAME_RE.search(fname)
        if not m:
            continue
        entries.append({
            "path": os.path.join(raw_dir, fname),
            "corner": m.group("corner"),
            "temp": float(m.group("temp")),
            "vdd": float(m.group("vdd")),
        })
    return entries


def cmd_compare_all(args):
    signals = args.signals
    raw_dir = args.raw_dir

    entries = discover_raws(raw_dir)
    if not entries:
        print(f"Error: no .raw files found in '{raw_dir}/'. Did you run 'sweep' first?", file=sys.stderr)
        sys.exit(1)

    # optional filters, in case you do not want ALL the combinations in the plot
    if args.corners:
        entries = [e for e in entries if e["corner"] in args.corners]
    if args.temps:
        entries = [e for e in entries if e["temp"] in args.temps]
    if args.vdds:
        entries = [e for e in entries if e["vdd"] in args.vdds]

    if not entries:
        print("Error: the --corners/--temps/--vdds filters left no .raw file to plot.", file=sys.stderr)
        sys.exit(1)

    corners_present = sorted({e["corner"] for e in entries})
    vdds_present = sorted({e["vdd"] for e in entries})

    cmap = plt.get_cmap("tab10")
    color_for_corner = {c: cmap(i % 10) for i, c in enumerate(corners_present)}
    style_for_vdd = {v: _LINESTYLES[i % len(_LINESTYLES)] for i, v in enumerate(vdds_present)}

    # alpha as a function of temperature: hotter -> more opaque
    temps_present = sorted({e["temp"] for e in entries})
    if len(temps_present) > 1:
        tmin, tmax = min(temps_present), max(temps_present)
        alpha_for_temp = {t: 0.35 + 0.65 * (t - tmin) / (tmax - tmin) for t in temps_present}
    else:
        alpha_for_temp = {temps_present[0]: 1.0}

    os.makedirs(PLOTDIR, exist_ok=True)

    print(f"Plotting {len(entries)} waveforms "
          f"({len(corners_present)} corners x {len(temps_present)} temps x {len(vdds_present)} vdd)...")

    for signal in signals:
        fig, ax = plt.subplots(figsize=(11, 6))

        for e in entries:
            try:
                time, values = load_waveform(e["path"], signal=signal)
            except Exception as exc:
                print(f"  [!] could not read {e['path']} ({signal}): {exc}", file=sys.stderr)
                continue

            ax.plot(
                time * 1e9, values,
                color=color_for_corner[e["corner"]],
                linestyle=style_for_vdd[e["vdd"]],
                alpha=alpha_for_temp[e["temp"]],
                linewidth=1.2,
            )

        # Composite legend: one group of proxies per color (corner) and another per linestyle (vdd)
        corner_handles = [
            plt.Line2D([0], [0], color=color_for_corner[c], lw=2, label=c)
            for c in corners_present
        ]
        vdd_handles = [
            plt.Line2D([0], [0], color="gray", lw=2, linestyle=style_for_vdd[v], label=f"{fmt_num(v)} V")
            for v in vdds_present
        ]

        legend1 = ax.legend(handles=corner_handles, title="Corner (color)", loc="upper left",
                             bbox_to_anchor=(1.01, 1.0))
        ax.add_artist(legend1)
        ax.legend(handles=vdd_handles, title="VDD (line)", loc="lower left", bbox_to_anchor=(1.01, 0.0))

        ax.set_xlabel("Time (ns)")
        ax.set_ylabel(f"{signal} (V)")
        temp_note = f"temp: lighter = colder, darker = hotter ({fmt_num(min(temps_present))}°C to {fmt_num(max(temps_present))}°C)" \
            if len(temps_present) > 1 else f"temp={fmt_num(temps_present[0])}°C"
        ax.set_title(f"All PVT combinations — {signal}\n{temp_note}")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_signal = signal.replace("(", "").replace(")", "")
        fname = os.path.join(PLOTDIR, f"waveform_compare_all_{safe_signal}.png")
        plt.savefig(fname, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Saved: {fname}")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_sweep = subparsers.add_parser("sweep", help="Runs the full PVT sweep and saves CSV + one .raw per run")
    p_sweep.add_argument("--jobs", "-j", type=int, default=1,
                          help="Parallel combinations (default: 1 = sequential, as before). "
                               "Use ~os.cpu_count() to take advantage of all the cores.")
    p_sweep.set_defaults(func=cmd_sweep)

    p_compare = subparsers.add_parser("compare", help="Compares waveforms between corners for a fixed temp/vdd")
    p_compare.add_argument("--temp", type=float, default=27, help="Fixed temperature to compare (default: 27)")
    p_compare.add_argument("--vdd", type=float, default=3.3, help="Fixed VDD to compare (default: 3.3)")
    p_compare.add_argument("--corners", nargs="+", default=None,
                            help=f"Corners to compare (default: all: {CORNERS})")
    p_compare.add_argument("--signals", nargs="+", default=["v(outb)"],
                            help="Signals to plot, one figure per signal (default: v(outb))")
    p_compare.set_defaults(func=cmd_compare)

    p_all = subparsers.add_parser("compare-all",
                                   help="Plots ALL the PVT combinations (all the .raw files) in the same plot")
    p_all.add_argument("--raw-dir", default=RAWDIR, help=f"Directory with the .raw files (default: {RAWDIR})")
    p_all.add_argument("--signals", nargs="+", default=["v(outb)"],
                        help="Signals to plot, one figure per signal (default: v(outb))")
    p_all.add_argument("--corners", nargs="+", default=None, help="Filter only these corners (default: all)")
    p_all.add_argument("--temps", nargs="+", type=float, default=None, help="Filter only these temperatures")
    p_all.add_argument("--vdds", nargs="+", type=float, default=None, help="Filter only these VDD values")
    p_all.set_defaults(func=cmd_compare_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
