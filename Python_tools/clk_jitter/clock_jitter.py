#!/usr/bin/env python3
"""
clock_jitter.py

Analyzes jitter and generates the eye diagram of a PERIODIC CLOCK signal
(unlike eye_diagram.py / eye_metrics.py, which are for random PRBS data).
The key differences with respect to the PRBS case:

  - The crossings are separated by DIRECTION (rising/falling), not by
    position in the window — in a clock each direction always occurs at the
    same phase of the period, unlike PRBS where both directions can appear
    at any position depending on the bit pattern.

  - The duty cycle is MEASURED from the data (distance between the rising
    phase and the falling phase), not assumed to be 50%/±0.5 UI as in PRBS.

  - The TIE is computed with respect to an ideal grid fitted by LINEAR
    REGRESSION over the real crossing times (not with respect to the
    nominal 'freq' parameter as is) — this way, if the real clock
    frequency differs slightly from 'freq' (real oscillators rarely match
    exactly), the TIE does not show a spurious linear drift due to that
    mismatch; the period and cycle-to-cycle jitter (differences between
    consecutive crossings) are immune to this by construction, since they
    only compare consecutive cycles with each other.

Metrics it computes:
  - Measured vs. nominal frequency/period
  - Measured duty cycle
  - Rising and falling TIE (with respect to the grid fitted by linear
    regression, separately for each direction)
  - Period jitter (T_n) and cycle-to-cycle jitter (T_n - T_(n-1)),
    for rising and for falling
  - Voltage noise at the high and low levels (sampled at the real midpoint
    of each pulse, according to the measured duty cycle)
  - Eye diagram folded and centered on the rising edge

Usage:
    python3 clock_jitter.py clock.raw --freq 1e9 --signal v(clk)
    python3 clock_jitter.py clock.raw --freq 1e9 --signal v(clk) --vdd 1.8

Requires: spicelib, numpy, matplotlib
    pip install spicelib numpy matplotlib --break-system-packages
"""

import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

try:
    from spicelib.raw.raw_read import RawRead
except ImportError:
    RawRead = None


# ----------------------------------------------------------------------
# Loading and crossing detection (with direction)
# ----------------------------------------------------------------------

def load_waveform(raw_path: str, signal: str):
    if RawRead is None:
        raise RuntimeError(
            "spicelib is not installed. Install it with:\n"
            "    pip install spicelib --break-system-packages"
        )
    raw = RawRead(raw_path, dialect="ngspice")
    time = np.asarray(raw.get_trace("time").get_wave(), dtype=float)
    values = np.asarray(raw.get_trace(signal).get_wave(), dtype=float)
    return time, values


def detect_threshold(values: np.ndarray, vdd: float = None, center_voltage: float = None) -> float:
    if center_voltage is not None:
        return center_voltage
    if vdd is not None:
        return vdd / 2.0
    return (values.max() + values.min()) / 2.0


def find_crossings_by_direction(time: np.ndarray, values: np.ndarray, threshold: float, skip_time: float):
    """Finds the crossings through 'threshold' after skip_time, separated
    into rising and falling, with linear interpolation for sub-sample
    precision. Returns two arrays of absolute times."""
    mask = time >= skip_time
    t = time[mask]
    v = values[mask]

    signs = np.sign(v - threshold)
    idx = np.where(np.diff(signs) != 0)[0]

    rising, falling = [], []
    for i in idx:
        t0, t1 = t[i], t[i + 1]
        v0, v1 = v[i], v[i + 1]
        if v1 == v0:
            continue
        frac = (threshold - v0) / (v1 - v0)
        t_cross = t0 + frac * (t1 - t0)
        if v1 > v0:
            rising.append(t_cross)
        else:
            falling.append(t_cross)

    return np.array(rising), np.array(falling)


def circular_mean_phase(crossing_times: np.ndarray, ui: float) -> float:
    """Average phase (0 to 1, in UI) of a set of crossings, via a
    circular average (robust to the wrap-around at 0/1)."""
    phases = (crossing_times / ui) % 1.0
    angles = phases * 2 * np.pi
    mean_angle = np.arctan2(np.mean(np.sin(angles)), np.mean(np.cos(angles)))
    return (mean_angle / (2 * np.pi)) % 1.0


# ----------------------------------------------------------------------
# Optimal threshold (same criterion as eye_diagram.py: minimize jitter)
# ----------------------------------------------------------------------

def circular_jitter_std(crossing_times: np.ndarray, ui: float) -> float:
    if len(crossing_times) < 2:
        return np.inf
    phases = (crossing_times / ui) % 1.0
    angles = phases * 2 * np.pi
    R = np.hypot(np.mean(np.cos(angles)), np.mean(np.sin(angles)))
    if R <= 0:
        return np.inf
    return np.sqrt(-2 * np.log(R)) * ui


def refine_threshold(time: np.ndarray, values: np.ndarray, ui: float, skip_time: float,
                      initial_threshold: float, n_coarse: int = 60, n_fine: int = 40,
                      search_margin: float = 0.05):
    """Same as in eye_diagram.py: sweeps candidate voltages and keeps the
    one that minimizes the COMBINED (rising+falling) jitter of the crossings."""
    vmin, vmax = values.min(), values.max()
    margin = (vmax - vmin) * search_margin

    def combined_jitter(v_th):
        rising, falling = find_crossings_by_direction(time, values, v_th, skip_time)
        if len(rising) < 3 or len(falling) < 3:
            return np.inf
        return circular_jitter_std(rising, ui) + circular_jitter_std(falling, ui)

    def sweep(v_lo, v_hi, n):
        candidates = np.linspace(v_lo, v_hi, n)
        return [(v, combined_jitter(v)) for v in candidates]

    coarse = sweep(vmin + margin, vmax - margin, n_coarse)
    coarse = [c for c in coarse if np.isfinite(c[1])]
    if not coarse:
        return initial_threshold, 0.0

    coarse.sort(key=lambda r: r[1])
    best_coarse_v = coarse[0][0]
    step = (vmax - vmin - 2 * margin) / (n_coarse - 1)

    fine = sweep(best_coarse_v - step, best_coarse_v + step, n_fine)
    fine = [c for c in fine if np.isfinite(c[1])]
    fine.sort(key=lambda r: r[1])
    best_v = fine[0][0] if fine else best_coarse_v

    return best_v, best_v - initial_threshold


# ----------------------------------------------------------------------
# Jitter metrics: TIE (by linear regression), period, cycle-to-cycle
# ----------------------------------------------------------------------

def linear_fit_tie(crossing_times: np.ndarray):
    """
    Fits t_n ~ n*T_fit + t0_fit by least squares, and returns the TIE
    of each crossing with respect to that fitted grid (not with respect
    to the nominal 'freq') — so the result is not contaminated if the real
    clock frequency differs slightly from the nominal one.
    """
    n = len(crossing_times)
    if n < 3:
        return np.array([]), None, None

    idx = np.arange(n)
    # linear fit: crossing_times = T_fit * idx + t0_fit
    A = np.vstack([idx, np.ones(n)]).T
    T_fit, t0_fit = np.linalg.lstsq(A, crossing_times, rcond=None)[0]

    ideal = t0_fit + idx * T_fit
    tie = crossing_times - ideal
    return tie, T_fit, t0_fit


def period_and_cycle_jitter(crossing_times: np.ndarray):
    """Period jitter (T_n = t_n - t_(n-1)) and cycle-to-cycle jitter
    (T_n - T_(n-1)), from consecutive crossings of the SAME direction.
    Both are immune to a possible mismatch between the real and the
    nominal frequency, because they only compare neighboring cycles."""
    if len(crossing_times) < 2:
        return np.array([]), np.array([])
    periods = np.diff(crossing_times)
    cycle_to_cycle = np.diff(periods)
    return periods, cycle_to_cycle


def stats_of(values: np.ndarray) -> dict:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan"),
                "min": float("nan"), "max": float("nan"), "pp": float("nan")}
    return {
        "n": n, "mean": values.mean(),
        "std": values.std(ddof=1) if n > 1 else 0.0,
        "min": values.min(), "max": values.max(),
        "pp": values.max() - values.min(),
    }


# ----------------------------------------------------------------------
# Eye folding, centered on the RISING edge
# ----------------------------------------------------------------------

def fold_eye_on_rising(time: np.ndarray, values: np.ndarray, ui: float, n_ui_window: float,
                        skip_time: float, oversample: int, rising_phase: float):
    window_width = n_ui_window * ui
    t_end = time[-1]

    n_points_grid = int(oversample * n_ui_window) + 1
    grid_rel = np.linspace(-window_width / 2, window_width / 2, n_points_grid)
    grid_in_ui = grid_rel / ui

    rows = []
    k = 0
    while True:
        t_center = skip_time + k * ui + rising_phase * ui
        t_lo, t_hi = t_center + grid_rel[0], t_center + grid_rel[-1]
        if t_hi > t_end:
            break
        if t_lo < time[0]:
            k += 1
            continue
        rows.append(np.interp(t_center + grid_rel, time, values))
        k += 1

    if not rows:
        raise ValueError("No centered window could be generated — check skip_time/n_ui_window.")

    return grid_in_ui, np.array(rows)


def compute_top_bottom_noise(grid_in_ui: np.ndarray, matrix: np.ndarray, threshold: float,
                              duty_cycle: float):
    """Samples the high level at the midpoint of the high pulse (at
    duty_cycle/2 UI from the rising edge, which is grid=0) and the low
    level at the midpoint of the low pulse — using the MEASURED duty
    cycle, not assuming 50%."""
    top_center_ui = duty_cycle / 2.0
    bottom_center_ui = duty_cycle + (1.0 - duty_cycle) / 2.0
    if bottom_center_ui > grid_in_ui.max():
        bottom_center_ui -= 1.0  # falls in the "left" half of the window

    top_idx = np.argmin(np.abs(grid_in_ui - top_center_ui))
    bottom_idx = np.argmin(np.abs(grid_in_ui - bottom_center_ui))

    top_vals = matrix[:, top_idx]
    bottom_vals = matrix[:, bottom_idx]
    return stats_of(top_vals), stats_of(bottom_vals), top_vals, bottom_vals, top_center_ui, bottom_center_ui


# ----------------------------------------------------------------------
# Plots
# ----------------------------------------------------------------------

def plot_eye(grid_in_ui, matrix, signal, ui, duty_cycle, top_center_ui, bottom_center_ui, outdir):
    fig, ax = plt.subplots(figsize=(10, 6))
    for row in matrix:
        ax.plot(grid_in_ui, row, color="steelblue", alpha=0.15, linewidth=0.8)

    ax.axvline(0.0, color="green", linestyle=":", linewidth=1.2, label="rising edge (0 UI)")
    ax.axvline(duty_cycle, color="darkorange", linestyle="--", linewidth=1.2,
               label=f"falling edge ({duty_cycle:.3f} UI)")
    ax.axvline(top_center_ui, color="seagreen", linestyle=":", linewidth=1, alpha=0.7, label="high sampling")
    ax.axvline(bottom_center_ui, color="chocolate", linestyle=":", linewidth=1, alpha=0.7, label="low sampling")

    ax.set_xlabel("Time (UI, 0 = rising edge)")
    ax.set_ylabel(f"{signal} (V)")
    ax.set_title(f"Eye diagram — clock  ({signal}, measured duty cycle = {duty_cycle*100:.2f}%)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fname = os.path.join(outdir, "clock_eye.png")
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Saved: {fname}")


def plot_histogram(values, title, xlabel, color, fname, outdir, unit_scale=1e12, unit_label="ps"):
    if len(values) == 0:
        return
    vals = np.asarray(values) * unit_scale
    fig, ax = plt.subplots(figsize=(7, 4.5))
    data_min, data_max = vals.min(), vals.max()
    span = max(data_max - data_min, 1e-6)
    pad = span * 0.3
    n_bins = max(5, min(25, len(vals) // 2 or 5))
    bin_edges = np.linspace(data_min - pad, data_max + pad, n_bins)

    mean, sigma = vals.mean(), vals.std(ddof=1) if len(vals) > 1 else 0.0
    ax.hist(vals, bins=bin_edges, color=color, edgecolor="white", alpha=0.85)
    ax.axvline(mean, color="black", linestyle="--", linewidth=1.2,
               label=f"mean = {mean:.3f}\nsigma = {sigma:.3f}")
    ax.set_xlabel(f"{xlabel} ({unit_label})")
    ax.set_ylabel("Count (# samples)")
    ax.set_title(f"{title}  (n={len(vals)})")
    ax.legend()
    plt.tight_layout()
    path = os.path.join(outdir, fname)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_path", help="Path to the ngspice .raw file")
    parser.add_argument("--freq", type=float, required=True, help="NOMINAL clock frequency (Hz)")
    parser.add_argument("--signal", default="v(clk)", help="Signal to analyze (default: v(clk))")
    parser.add_argument("--vdd", type=float, default=None, help="VDD, for an initial threshold of VDD/2")
    parser.add_argument("--center-voltage", type=float, default=None, help="Explicit initial threshold")
    parser.add_argument("--no-refine-threshold", action="store_true",
                         help="Disables the search for the optimal threshold (uses VDD/2 or the auto-detected value as is)")
    parser.add_argument("--ui-window", type=float, default=2.0, help="Width of the folded window, in UI (default: 2.0)")
    parser.add_argument("--skip-ui", type=float, default=2.0, help="Initial UI to discard (default: 2.0)")
    parser.add_argument("--oversample", type=int, default=200, help="Points per UI in the grid (default: 200)")
    parser.add_argument("--outdir", default="clock_analysis", help="Output directory")
    args = parser.parse_args()

    if not os.path.isfile(args.raw_path):
        print(f"Error: '{args.raw_path}' not found", file=sys.stderr)
        sys.exit(1)
    os.makedirs(args.outdir, exist_ok=True)

    ui_nominal = 1.0 / args.freq
    time, values = load_waveform(args.raw_path, args.signal)
    print(f"Signal '{args.signal}' loaded: {len(time)} points, t=0 to {time[-1]*1e9:.2f}ns")
    print(f"Nominal UI (1/freq): {ui_nominal*1e12:.2f} ps\n")

    threshold_initial = detect_threshold(values, args.vdd, args.center_voltage)
    skip_time = args.skip_ui * ui_nominal

    if args.no_refine_threshold:
        threshold = threshold_initial
        print(f"Threshold used (unrefined): {threshold:.4f} V\n")
    else:
        threshold, offset = refine_threshold(time, values, ui_nominal, skip_time, threshold_initial)
        print(f"Initial threshold: {threshold_initial:.4f} V   Refined threshold: {threshold:.4f} V   "
              f"Offset: {offset*1e3:+.2f} mV\n")

    rising, falling = find_crossings_by_direction(time, values, threshold, skip_time)
    print(f"Crossings detected: {len(rising)} rising, {len(falling)} falling\n")
    if len(rising) < 3 or len(falling) < 3:
        print("Error: not enough crossings of each direction for the analysis.", file=sys.stderr)
        sys.exit(1)

    # --- measured frequency/period, duty cycle ---
    rising_phase = circular_mean_phase(rising, ui_nominal)
    falling_phase = circular_mean_phase(falling, ui_nominal)
    duty_cycle = (falling_phase - rising_phase) % 1.0

    tie_rise, T_rise_fit, t0_rise_fit = linear_fit_tie(rising)
    tie_fall, T_fall_fit, _ = linear_fit_tie(falling)

    freq_measured = 1.0 / T_rise_fit if T_rise_fit else float("nan")

    print("=" * 60)
    print("FREQUENCY AND DUTY CYCLE")
    print("=" * 60)
    print(f"Nominal frequency  : {args.freq:.6e} Hz")
    print(f"Measured frequency : {freq_measured:.6e} Hz  (linear fit over rising edges)")
    print(f"Deviation          : {(freq_measured-args.freq)/args.freq*100:+.4f} %")
    print(f"Measured duty cycle: {duty_cycle*100:.3f} %")
    print()

    # --- TIE ---
    print("=" * 60)
    print("TIE (with respect to the grid fitted by linear regression)")
    print("=" * 60)
    for label, tie in [("Rising", tie_rise), ("Falling", tie_fall)]:
        s = stats_of(tie)
        print(f"\n{label}  (n={s['n']}):")
        print(f"  pp = {s['pp']*1e12:.2f} ps   rms = {s['std']*1e12:.2f} ps")
    print()

    # --- period and cycle-to-cycle jitter ---
    period_rise, cc_rise = period_and_cycle_jitter(rising)
    period_fall, cc_fall = period_and_cycle_jitter(falling)

    print("=" * 60)
    print("PERIOD AND CYCLE-TO-CYCLE JITTER")
    print("=" * 60)
    for label, periods, cc in [("Rising", period_rise, cc_rise), ("Falling", period_fall, cc_fall)]:
        sp, sc = stats_of(periods), stats_of(cc)
        print(f"\n{label}:")
        print(f"  Period  (n={sp['n']}): mean={sp['mean']*1e12:.2f}ps  pp={sp['pp']*1e12:.2f}ps  "
              f"rms={sp['std']*1e12:.2f}ps")
        print(f"  Cycle-to-cycle (n={sc['n']}): pp={sc['pp']*1e12:.2f}ps  rms={sc['std']*1e12:.2f}ps")
    print()

    # --- folded eye diagram ---
    grid_in_ui, matrix = fold_eye_on_rising(time, values, ui_nominal, args.ui_window,
                                             skip_time, args.oversample, rising_phase)
    n_windows = matrix.shape[0]
    print(f"Folded windows for the eye diagram: {n_windows}\n")

    top_stats, bottom_stats, top_vals, bottom_vals, top_c, bottom_c = compute_top_bottom_noise(
        grid_in_ui, matrix, threshold, duty_cycle)

    print("=" * 60)
    print("VOLTAGE NOISE (high and low)")
    print("=" * 60)
    for label, s in [("High", top_stats), ("Low", bottom_stats)]:
        print(f"\n{label}  (n={s['n']}): mean={s['mean']:.4f}V  sigma={s['std']*1e3:.2f}mV")
    print()

    plot_eye(grid_in_ui, matrix, args.signal, ui_nominal, duty_cycle, top_c, bottom_c, args.outdir)

    plot_histogram(tie_rise, "TIE - Rising", "TIE", "firebrick", "hist_tie_rising.png", args.outdir)
    plot_histogram(tie_fall, "TIE - Falling", "TIE", "steelblue", "hist_tie_falling.png", args.outdir)
    plot_histogram(period_rise, "Period jitter - Rising", "Period", "darkorange",
                    "hist_period_rising.png", args.outdir)
    plot_histogram(cc_rise, "Cycle-to-cycle jitter - Rising", "T_n - T_(n-1)", "purple",
                    "hist_cycle_to_cycle_rising.png", args.outdir)
    plot_histogram(top_vals, "Voltage noise - High", "Voltage", "seagreen",
                    "hist_noise_high.png", args.outdir, unit_scale=1e3, unit_label="mV")
    plot_histogram(bottom_vals, "Voltage noise - Low", "Voltage", "chocolate",
                    "hist_noise_low.png", args.outdir, unit_scale=1e3, unit_label="mV")

    print(f"All plots saved in: {args.outdir}/")


if __name__ == "__main__":
    main()
