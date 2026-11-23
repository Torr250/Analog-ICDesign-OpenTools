#!/usr/bin/env python3
"""
mc_runner.py

Runs the TB_not testbench (CMOS inverter, gf180mcuD) with Monte Carlo
enabled (sw_stat_global=1, sw_stat_mismatch=1) N times, and collects:
  1. The scalar results of the .meas (trise, tfall, tplh, tphl,
     tpd_avg, ivdd_rms, effy) in a CSV, one row per run.
  2. An individual .raw per run (to plot/compare waveforms between
     Monte Carlo samples).

Unlike the PVT runner, here NOTHING is substituted in the netlist between
runs (same corner, same VDD, same temp) — each invocation of
'ngspice -b' is an independent process that starts with its own random
seed from the system, so it is enough to run the netlist N times.

IMPORTANT: there is no way to fix/reproduce the seed of a particular run
(see the note in the netlist) — each run is unique and unrepeatable.

Usage:
    # 1) Run the Monte Carlo sweep (generates CSV + one .raw per run)
    python3 mc_runner.py sweep                # 200 runs (default), sequential
    python3 mc_runner.py sweep --n 500
    python3 mc_runner.py sweep --n 500 --jobs 8   # 8 ngspice runs in parallel

    # 2) Overlay the waveforms of several runs in a single plot
    python3 mc_runner.py plot                         # overlays all the available runs
    python3 mc_runner.py plot --n-overlay 30          # overlays only 30 (random sample)
    python3 mc_runner.py plot --n-overlay 30 --mode first   # the first 30, no randomness
    python3 mc_runner.py plot --signals "v(outb)" "v(in)"
"""

import argparse
import csv
import os
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt

try:
    from spicelib.raw.raw_read import RawRead
except ImportError:
    RawRead = None

TEMPLATE = "TB_not_mc_template.spice"
WORKDIR = "mc_runs"
RAWDIR = "mc_raws"
OUTPUT_CSV = "mc_results.csv"
PLOTDIR = "mc_analysis"

N_RUNS = 200

MEAS_NAMES = ["trise", "tfall", "tplh", "tphl", "tpd_avg", "ivdd_rms", "effy"]

TEMPLATE_RAW_NAME = "TB_not.raw"

RAW_FILENAME_RE = re.compile(r"mc_run_(?P<idx>\d+)\.raw$")


# ----------------------------------------------------------------------
# sweep: runs N times, saves CSV + one .raw per run (same as before)
# ----------------------------------------------------------------------

def raw_path_for(run_idx: int) -> str:
    return os.path.join(RAWDIR, f"mc_run_{run_idx:04d}.raw")


def build_netlist(template_text: str, run_idx: int) -> str:
    """Only redirects the 'write' to a unique .raw per run; nothing else changes."""
    raw_path = raw_path_for(run_idx)
    return template_text.replace(f"write {TEMPLATE_RAW_NAME}", f"write {raw_path}")


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


def run_one(template_text: str, run_idx: int) -> dict:
    """Executes ONE complete run (netlist -> ngspice -> parsing) and returns
    everything needed to report progress and write the CSV. This function
    is the unit of work that is sent to the thread pool."""
    raw_path = raw_path_for(run_idx)
    netlist = build_netlist(template_text, run_idx)

    fname = os.path.join(WORKDIR, f"mc_run_{run_idx:04d}.spice")
    with open(fname, "w") as f:
        f.write(netlist)

    stdout = run_ngspice(fname)

    log_fname = fname.replace(".spice", ".log")
    with open(log_fname, "w") as f:
        f.write(stdout)

    row = {"run": run_idx}
    for meas in MEAS_NAMES:
        row[meas] = parse_meas(stdout, meas)
    missing = [m for m in MEAS_NAMES if row[m] is None]

    return {
        "run_idx": run_idx,
        "row": row,
        "missing": missing,
        "raw_path": raw_path,
        "log_fname": log_fname,
        "raw_ok": os.path.isfile(raw_path),
    }


def cmd_sweep(args):
    n_runs = args.n
    jobs = args.jobs

    if not os.path.isfile(TEMPLATE):
        print(f"Error: template '{TEMPLATE}' not found in the current directory.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(WORKDIR, exist_ok=True)
    os.makedirs(RAWDIR, exist_ok=True)

    with open(TEMPLATE, "r") as f:
        template_text = f.read()

    # results indexed by position so they can be reordered at the end, since
    # the parallel runs do not necessarily finish in order
    results = [None] * n_runs
    done = 0

    print(f"Running {n_runs} Monte Carlo samples with {jobs} worker(s) in parallel...\n")

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(run_one, template_text, i): i for i in range(1, n_runs + 1)}

        for future in as_completed(futures):
            run_idx = futures[future]
            outcome = future.result()

            results[run_idx - 1] = outcome["row"]
            done += 1

            if not outcome["raw_ok"]:
                print(f"    [!] run {run_idx}: the expected .raw was not generated "
                      f"({outcome['raw_path']}); check {outcome['log_fname']}")
            if outcome["missing"]:
                print(f"    [!] run {run_idx}: could not extract "
                      f"{', '.join(outcome['missing'])} (check {outcome['log_fname']})")

            if done % 10 == 0 or done == n_runs:
                print(f"[{done}/{n_runs}] runs completed")

    fieldnames = ["run"] + MEAS_NAMES
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. {len(results)} runs completed.")
    print(f"  Measurements CSV  : {OUTPUT_CSV}")
    print(f"  Netlists + logs   : {WORKDIR}/")
    print(f"  Waveforms (.raw)  : {RAWDIR}/")


# ----------------------------------------------------------------------
# plot: overlays the waveforms of N runs in a single plot
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


def discover_mc_raws(raw_dir: str):
    """Scans raw_dir and returns [(run_idx, path), ...] sorted by run index."""
    entries = []
    if not os.path.isdir(raw_dir):
        return entries
    for fname in os.listdir(raw_dir):
        m = RAW_FILENAME_RE.search(fname)
        if not m:
            continue
        entries.append((int(m.group("idx")), os.path.join(raw_dir, fname)))
    entries.sort(key=lambda e: e[0])
    return entries


def cmd_plot(args):
    raw_dir = args.raw_dir
    entries = discover_mc_raws(raw_dir)

    if not entries:
        print(f"Error: no .raw files found in '{raw_dir}/'. Did you run 'sweep' first?", file=sys.stderr)
        sys.exit(1)

    total_available = len(entries)
    n_overlay = args.n_overlay if args.n_overlay is not None else total_available
    n_overlay = min(n_overlay, total_available)

    if n_overlay < total_available:
        if args.mode == "random":
            if args.seed is not None:
                random.seed(args.seed)
            selected = random.sample(entries, n_overlay)
            selected.sort(key=lambda e: e[0])
        else:  # "first"
            selected = entries[:n_overlay]
    else:
        selected = entries

    os.makedirs(PLOTDIR, exist_ok=True)

    print(f"Overlaying {len(selected)} of {total_available} available runs "
          f"(mode: {args.mode if n_overlay < total_available else 'all'})...")

    for signal in args.signals:
        fig, ax = plt.subplots(figsize=(10, 6))

        for run_idx, raw_path in selected:
            try:
                time, values = load_waveform(raw_path, signal=signal)
            except Exception as exc:
                print(f"  [!] could not read {raw_path} ({signal}): {exc}", file=sys.stderr)
                continue
            ax.plot(time * 1e9, values, color="steelblue", alpha=0.35, linewidth=0.9)

        ax.set_xlabel("Time (ns)")
        ax.set_ylabel(f"{signal} (V)")
        ax.set_title(f"Monte Carlo — {signal}  ({len(selected)} overlaid runs)")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_signal = signal.replace("(", "").replace(")", "")
        fname = os.path.join(PLOTDIR, f"mc_overlay_{safe_signal}_{len(selected)}runs.png")
        plt.savefig(fname, dpi=150)
        plt.close()
        print(f"Saved: {fname}")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_sweep = subparsers.add_parser("sweep", help="Runs N Monte Carlo samples and saves CSV + one .raw per run")
    p_sweep.add_argument("--n", type=int, default=N_RUNS, help=f"Number of runs (default: {N_RUNS})")
    p_sweep.add_argument("--jobs", "-j", type=int, default=1,
                          help="Parallel runs (default: 1 = sequential, as before). "
                               "Use ~os.cpu_count() to take advantage of all the cores.")
    p_sweep.set_defaults(func=cmd_sweep)

    p_plot = subparsers.add_parser("plot", help="Overlays the waveforms of several runs in a single plot")
    p_plot.add_argument("--raw-dir", default=RAWDIR, help=f"Directory with the .raw files (default: {RAWDIR})")
    p_plot.add_argument("--n-overlay", type=int, default=None,
                         help="How many runs to overlay (default: all the available ones)")
    p_plot.add_argument("--mode", choices=["random", "first"], default="random",
                         help="If --n-overlay is smaller than the total: 'random' (random sample, default) "
                              "or 'first' (the first N runs, no randomness)")
    p_plot.add_argument("--seed", type=int, default=None,
                         help="Seed for the random selection of runs (reproducibility of WHICH runs "
                              "are plotted, not of the simulation itself)")
    p_plot.add_argument("--signals", nargs="+", default=["v(outb)"],
                         help="Signals to plot, one figure per signal (default: v(outb))")
    p_plot.set_defaults(func=cmd_plot)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
