#!/usr/bin/env python3
"""
eye_diagram.py

Generates an eye diagram from an ngspice .raw file, folding the signal
into windows of N*UI (UI = 1/freq) and interpolating each window onto a
common time grid before overlaying them.

AUTOMATIC EYE CENTERING: instead of assuming that the crossings fall at a
fixed point of the window, the script first scans the raw signal to find
ALL the threshold crossings, computes the average phase of those crossings
with respect to the ideal bit grid (this captures the total propagation
delay of the circuit, whatever it is), and uses that phase to fold the
windows already centered: the CENTER of the eye ends up at 0 UI, the left
crossing ideally at -0.5 UI, and the right one at +0.5 UI. This works
regardless of how much delay the circuit has (one stage, several stages in
cascade, etc.) because the delay is measured from the data, not assumed.

OPTIMAL DECISION THRESHOLD: by default, instead of assuming VDD/2 as the
crossing threshold, the script sweeps candidate voltages and keeps the one
that MINIMIZES the jitter of the crossings (temporal dispersion). This is
necessary because VDD/2 (or the midpoint between the high and low levels)
only coincides with the real crossing point when the circuit has symmetric
rising/falling edges — in drivers with asymmetric dynamics between edges,
the real crossing of the signal can be far from that midpoint.
It can be disabled with --no-refine-threshold to use VDD/2 as is.

Usage:
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9 --signal v(out)
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9 --skip-ui 5 --ui-window 2
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9 --vdd 3.3

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
    """
    INITIAL estimate of the threshold (the sweep of refine_threshold
    corrects it afterwards, so it does not need to be very precise):
      - If center_voltage is passed: it is used as is (for differential or
        other signals where the crossing is not VDD/2).
      - If vdd is passed: VDD/2 (for single-ended 0 to VDD).
      - If nothing is passed: (max+min)/2 of the data — works for
        both cases without the user having to state the voltage
        range explicitly.
    """
    if center_voltage is not None:
        return center_voltage
    if vdd is not None:
        return vdd / 2.0
    return (values.max() + values.min()) / 2.0


def find_all_crossings(time: np.ndarray, values: np.ndarray, threshold: float, t_min: float):
    """Finds ALL the crossings of 'values' through 'threshold' after
    t_min, with linear interpolation for sub-sample precision. Returns
    an array of absolute crossing times (in seconds)."""
    mask = time >= t_min
    t = time[mask]
    v = values[mask]

    signs = np.sign(v - threshold)
    idx = np.where(np.diff(signs) != 0)[0]

    crossing_times = []
    for i in idx:
        t0, t1 = t[i], t[i + 1]
        v0, v1 = v[i], v[i + 1]
        if v1 == v0:
            continue
        frac = (threshold - v0) / (v1 - v0)
        crossing_times.append(t0 + frac * (t1 - t0))

    return np.array(crossing_times)


def detect_center_phase(crossing_times: np.ndarray, ui: float) -> float:
    """
    Computes the average phase (0 to 1, in UI units) at which the
    crossings occur, with respect to the ideal bit grid (multiples of the UI
    from t=0). This captures the total propagation delay of the circuit,
    whatever it is, measuring it from the data instead of assuming it.

    It uses a circular average (via vectors on the unit circle) because
    the phase "wraps" at 1.0 -> 0.0 and a direct arithmetic average would
    fail if the samples are near that wrap-around point.

    Returns eye_center_phase = (average_crossing_phase + 0.5) mod 1.0
    — that is, the midpoint between two consecutive crossings, which is
    where the eye is most open (the best sampling point).
    """
    if len(crossing_times) == 0:
        raise ValueError("No threshold crossing was detected in the signal; "
                          "the eye cannot be centered automatically.")

    phases = (crossing_times / ui) % 1.0
    angles = phases * 2 * np.pi
    mean_angle = np.arctan2(np.mean(np.sin(angles)), np.mean(np.cos(angles)))
    mean_phase = (mean_angle / (2 * np.pi)) % 1.0

    center_phase = (mean_phase + 0.5) % 1.0
    return center_phase, mean_phase


def fold_eye_centered(time: np.ndarray, values: np.ndarray, ui: float, n_ui_window: float,
                       skip_time: float, oversample: int, center_phase: float):
    """
    Folds the signal into windows of width n_ui_window*UI, ALREADY CENTERED: the
    returned grid goes from -n_ui_window/2 to +n_ui_window/2 (in UI), with 0
    corresponding to the center of the eye (point of maximum opening) and the
    expected crossings near -0.5 and +0.5.

    center_phase comes from detect_center_phase(): it is the offset (0 to 1, in
    UI) that must be added to each multiple of the UI to locate the real
    center of the eye (compensating for the propagation delay of the circuit).
    """
    window_width = n_ui_window * ui
    t_end = time[-1]

    n_points_grid = int(oversample * n_ui_window) + 1
    grid_rel = np.linspace(-window_width / 2, window_width / 2, n_points_grid)  # seconds, centered at 0
    grid_in_ui = grid_rel / ui

    rows = []
    k = 0
    while True:
        t_center = skip_time + k * ui + center_phase * ui
        t_lo = t_center + grid_rel[0]
        t_hi = t_center + grid_rel[-1]
        if t_hi > t_end:
            break
        if t_lo < time[0]:
            k += 1
            continue
        grid_abs = t_center + grid_rel
        interp_vals = np.interp(grid_abs, time, values)
        rows.append(interp_vals)
        k += 1

    if not rows:
        raise ValueError(
            "No centered window could be generated: check that skip_time + "
            "n_ui_window*UI does not exceed the total duration of the simulation."
        )

    return grid_in_ui, np.array(rows)


def circular_jitter_std(crossing_times: np.ndarray, ui: float) -> float:
    """Circular dispersion (in seconds) of the phase of the crossings with respect
    to the UI grid. Lower value = more consistent crossings in time
    = better decision-threshold candidate."""
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
    """
    Finds the "true" decision threshold by sweeping candidate voltages and
    keeping the one that MINIMIZES the jitter of the crossings (temporal
    dispersion). This is the physically correct and general criterion: it
    coincides with the midpoint between high/low levels ONLY when the
    circuit has symmetric rising/falling edges: in drivers with asymmetric
    dynamics between edges (e.g. segmented drivers with unbalanced
    pull-up/pull-down), the real crossing point of the signal can be quite
    far from that midpoint, and taking VDD/2 (or the midpoint of the levels)
    as the threshold introduces an artificial bias in the jitter
    measurements.

    It performs a two-stage search (coarse over the whole range of the
    signal, fine around the best candidate of the coarse stage).

    Returns (refined_threshold, offset_with_respect_to_the_initial, history).
    """
    vmin, vmax = values.min(), values.max()
    margin = (vmax - vmin) * search_margin

    def sweep(v_lo, v_hi, n):
        candidates = np.linspace(v_lo, v_hi, n)
        scored = []
        for v_th in candidates:
            crossings = find_all_crossings(time, values, v_th, skip_time)
            scored.append((v_th, crossings))
        return scored

    def best_by_jitter_with_min_count(scored, min_count_frac=0.9):
        """
        Among the evaluated candidates, discards those that capture MANY
        FEWER crossings than the observed maximum (< min_count_frac of the maximum).
        This prevents the search from locking onto a threshold that gives
        artificially low jitter only because it captures a small,
        unrepresentative subset of the transitions (typical with severe ISI,
        where several "families" of crossings appear at different levels) --
        the real threshold must capture ALL the transitions, not just the
        ones most consistent with each other.
        """
        counts = [len(c) for _, c in scored]
        if not counts:
            return None
        max_count = max(counts)
        valid = [(v, c) for v, c in scored if len(c) >= 5 and len(c) >= min_count_frac * max_count]
        if not valid:
            return None
        scored_jitter = [(v, circular_jitter_std(c, ui), len(c)) for v, c in valid]
        scored_jitter.sort(key=lambda r: r[1])
        return scored_jitter[0]

    coarse_raw = sweep(vmin + margin, vmax - margin, n_coarse)
    coarse_best = best_by_jitter_with_min_count(coarse_raw)
    if coarse_best is None:
        # no candidate could be evaluated (signal without enough crossings);
        # we return the initial threshold unchanged
        return initial_threshold, 0.0, [initial_threshold]

    best_coarse_v = coarse_best[0]
    step = (vmax - vmin - 2 * margin) / (n_coarse - 1)

    fine_raw = sweep(best_coarse_v - step, best_coarse_v + step, n_fine)
    fine_best = best_by_jitter_with_min_count(fine_raw)
    best_v = fine_best[0] if fine_best is not None else best_coarse_v

    history = [initial_threshold, best_coarse_v, best_v]
    offset = best_v - initial_threshold
    return best_v, offset, history


def plot_eye(grid_in_ui: np.ndarray, matrix: np.ndarray, signal: str, ui: float,
             n_windows: int, outdir: str):
    fig, ax = plt.subplots(figsize=(9, 6))

    for row in matrix:
        ax.plot(grid_in_ui, row, color="steelblue", alpha=0.15, linewidth=0.8)

    ax.axvline(-0.5, color="darkorange", linestyle="--", linewidth=1, label="ideal left crossing (-0.5 UI)")
    ax.axvline(0.5, color="darkorange", linestyle="--", linewidth=1, label="ideal right crossing (+0.5 UI)")
    ax.axvline(0.0, color="green", linestyle=":", linewidth=1, label="eye center (0 UI)")

    ax.set_xlabel("Time (UI, 0 = eye center)")
    ax.set_ylabel(f"{signal} (V)")
    ax.set_title(f"Eye diagram — {signal}  (UI = {ui*1e12:.1f} ps, {n_windows} folded windows)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    safe_signal = signal.replace("(", "").replace(")", "")
    fname = os.path.join(outdir, f"eye_{safe_signal}.png")
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Saved: {fname}")
    return fname


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_path", help="Path to the ngspice .raw file")
    parser.add_argument("--freq", type=float, required=True, help="Bit frequency (Hz). UI = 1/freq")
    parser.add_argument("--signal", default="v(out)", help="Signal to plot (default: v(out))")
    parser.add_argument("--vdd", type=float, default=None,
                         help="Circuit VDD (for SINGLE-ENDED signals from 0 to VDD), sets the initial "
                              "threshold at VDD/2. Do NOT use for differential signals — use "
                              "--center-voltage instead, or simply omit both flags.")
    parser.add_argument("--center-voltage", type=float, default=None,
                         help="Explicit initial threshold, in Volts, not divided by anything (useful for "
                              "DIFFERENTIAL signals centered near 0V, or any signal whose "
                              "crossing is not VDD/2). If omitted (together with --vdd), it is auto-detected "
                              "as (max+min)/2 of the data — it works well for both single-ended "
                              "and differential, since it assumes no fixed voltage range.")
    parser.add_argument("--no-refine-threshold", action="store_true",
                         help="Disables the search for the optimal threshold (see refine_threshold()). "
                              "If passed, VDD/2 (or the auto-detected value) is used as is, without searching "
                              "for the voltage that minimizes the jitter of the crossings.")
    parser.add_argument("--ui-window", type=float, default=2.0,
                         help="Width of each folded window, in UI (default: 2.0)")
    parser.add_argument("--skip-ui", type=float, default=2.0,
                         help="How many initial UI to discard as start-up transient (default: 2.0)")
    parser.add_argument("--oversample", type=int, default=200,
                         help="Points per UI in the interpolated grid (default: 200)")
    parser.add_argument("--outdir", default="eye_analysis", help="Output directory (default: eye_analysis)")
    args = parser.parse_args()

    if not os.path.isfile(args.raw_path):
        print(f"Error: '{args.raw_path}' not found", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    ui = 1.0 / args.freq
    print(f"UI = {ui*1e12:.2f} ps  (freq = {args.freq:.3e} Hz)")

    time, values = load_waveform(args.raw_path, args.signal)
    print(f"Signal '{args.signal}' loaded: {len(time)} points, "
          f"from t={time[0]*1e9:.2f}ns to t={time[-1]*1e9:.2f}ns")

    threshold_initial = detect_threshold(values, args.vdd, args.center_voltage)
    skip_time = args.skip_ui * ui

    if args.no_refine_threshold:
        threshold, offset, history = threshold_initial, 0.0, [threshold_initial]
        print(f"Threshold used (refinement disabled): {threshold:.4f} V")
    else:
        threshold, offset, history = refine_threshold(time, values, ui, skip_time, threshold_initial)
        print(f"Initial threshold (VDD/2 or auto) : {threshold_initial:.4f} V")
        print(f"Refined threshold (minimum jitter): {threshold:.4f} V")
        print(f"Detected offset                   : {offset*1e3:+.2f} mV")

    all_crossings = find_all_crossings(time, values, threshold, skip_time)
    center_phase, mean_phase = detect_center_phase(all_crossings, ui)
    print(f"Crossings detected for auto-centering: {len(all_crossings)}")
    print(f"Average phase of the crossings with respect to the ideal grid: {mean_phase*ui*1e12:.2f} ps "
          f"({mean_phase:.4f} UI)  <- this is the total propagation delay detected")
    print(f"Phase of the eye center (used for folding): {center_phase:.4f} UI")

    grid_in_ui, matrix = fold_eye_centered(time, values, ui, args.ui_window, skip_time,
                                            args.oversample, center_phase)
    n_windows = matrix.shape[0]
    print(f"Folded windows: {n_windows}  (window width: {args.ui_window} UI, "
          f"{args.oversample} points/UI)")

    plot_eye(grid_in_ui, matrix, args.signal, ui, n_windows, args.outdir)

    npz_path = os.path.join(args.outdir, "eye_folded_data.npz")
    np.savez(npz_path, grid_in_ui=grid_in_ui, matrix=matrix, ui=ui, signal=args.signal,
             threshold=threshold, threshold_initial=threshold_initial, threshold_offset=offset,
             threshold_refined=not args.no_refine_threshold,
             center_phase=center_phase, mean_phase=mean_phase)
    print(f"Folded data saved to: {npz_path}  (for the later metrics calculation)")


if __name__ == "__main__":
    main()
