#!/usr/bin/env python3
"""
osc_characterization.py

Characterizes an OSCILLATOR (typically differential) from an ngspice .raw
file. Based on clock_jitter.py (directional crossings, TIE from a linear
fit, period and cycle-to-cycle jitter, eye folding), but unlike a clock the
frequency of an oscillator is NOT an input: it is MEASURED from the signal
itself. --freq is therefore optional (it only reports the deviation from an
expected value).

Metrics:
  1. Frequency and period (linear fit over the crossings) and their spread.
  2. Differential amplitude, common-mode level, symmetry, extra probes.
  3. Start-up time (per-cycle envelope, 10%/90%, exponential growth rate)
     and amplitude / frequency settling time.
  4. Power: mean supply current, power and energy per cycle (total and/or core).
  5. Jitter: TIE, period and cycle-to-cycle (rising and falling edges).
  6. Tuning curve (frequency, amplitude, power vs. a control variable):
     'sweep' subcommand (runs ngspice) or 'tuning' (you already have the .raw files).
  +  Eye diagram (folded on the fitted ideal grid), duty cycle, slew and
     10-90% rise/fall times.
  +  Spectrum (COHERENT FFT: an integer number of periods is resampled, so
     the harmonics fall exactly on a bin and there is no spectral leakage):
     fundamental amplitude, harmonics in dBc and THD.
  +  Phase between outputs (e.g. quadrature I/Q): from the fundamental (FFT)
     and from zero crossings, with optional error vs. an expected phase.
  +  Simulation adequacy checks: warns when the time step is too coarse or
     there are too few cycles/crossings, and suggests a ready-to-paste
     ".tran <step> <stop>".

The steady state is detected automatically (settled amplitude and
frequency); it can be forced with --t-start.

Usage:
    # one simulation (differential signal already built in the netlist, E1 N13)
    python3 osc_characterization.py analyze CS.raw --signal "v(n13)" \\
        --pos "v(n1)" --neg "v(n3)" --vdd 3.3 --isupply "i(v7)" --icore "i(v1)" \\
        --probe "v(vcs)"

    # phase of a second output relative to a reference (expected 90 deg)
    python3 osc_characterization.py analyze CS.raw --signal "v(n13)" \\
        --phase-ref "v(n13)" --phase-sig "v(n24)" --phase-expected 90

    # differential built by the script (pos - neg); "a-b" also works in --phase-*
    python3 osc_characterization.py analyze CS.raw --pos "v(n1)" --neg "v(n3)"

    # sweep a source in the netlist (e.g. the bias current)
    python3 osc_characterization.py sweep --netlist CS.spice --line-prefix I0 \\
        --template "I0 VBP 0 {v}" --values 300u 400u 500u 600u 700u \\
        --ctrl-label "I_bias (uA)" --ctrl-scale 1e-6 --pos "v(n1)" --neg "v(n3)" ...

    # same sweep at several PVT corners (name:temp_C:VDD); the .lib section, VDD= and TEMP=
    # of the netlist are rewritten automatically. Preset worst3 = ss:125:3.0, typical:60:3.3, ff:-40:3.6
    python3 osc_characterization.py sweep --netlist CS.spice --line-prefix I0 \\
        --template "I0 VBP 0 {v}" --values 300u 400u 500u 600u 700u \\
        --corners worst3 --target-f 600meg --pos "v(n1)" --neg "v(n3)" --isupply "i(v7)" --icore "i(v1)"
    #   (single corners can be added or used alone: --corner ss:125:3.0 --corner typical:27:3.3)

    # everything above can live in a JSON file (keys = option names, '-' or '_'; whole-line // comments and
    # "_note" keys are allowed; "extends" inherits another JSON; "command" is analyze/tuning/sweep).
    # Command-line options override the file; input paths in the file are relative to the file itself.
    python3 osc_characterization.py --config configs/cs_diff_worst3.json
    python3 osc_characterization.py sweep --config configs/cs_diff_worst3.json --jobs 1 --outdir test
    # turn a command line that worked into a JSON (it writes the file and exits, it does not simulate):
    python3 osc_characterization.py sweep --netlist ... --values ... --save-config configs/mine.json
    # every run also writes <outdir>/config_used.json (the effective options, usable as --config)

    # tuning curve from .raw files you already have
    python3 osc_characterization.py tuning --run 0.3m:a.raw --run 0.5m:b.raw ...

As a library (for the future PVT / Monte Carlo runners):
    from osc_characterization import characterize, default_config
    res, report = characterize("run.raw", default_config(pos="v(n1)", neg="v(n3)",
                               vdd=3.3, isupply="i(v7)"))
    res["warnings"], res.get("suggested_tran"), res["freq"]["f"], ...

Requires: spicelib, numpy, scipy, matplotlib
    pip install spicelib numpy scipy matplotlib --break-system-packages
"""

import argparse
import contextlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.interpolate import CubicSpline
from scipy.signal import get_window

try:
    from spicelib.raw.raw_read import RawRead
except ImportError:
    RawRead = None

_trapz = getattr(np, "trapezoid", None) or np.trapz     # numpy 1.x / 2.x


# ======================================================================
# Configuration
# ======================================================================

def default_config(**overrides):
    cfg = dict(
        signal=None, pos=None, neg=None,            # signals to analyze
        single_ended=False,                          # signal is single-ended (labels/report only)
        probe=[],                                    # extra nodes (mean, ripple)
        vdd=None, vsupply=None,                      # for power
        isupply=None, icore=None,                    # supply-source currents
        freq=None,                                   # expected frequency (optional)
        threshold=None,                              # crossing threshold (default: mid-level)
        t_start=None,                                # steady-state start (s)
        amp_tol=0.02, freq_tol=0.005,                # settling criteria
        settle_margin=2,                             # extra cycles after settling
        ui_window=2.0, oversample=200,               # eye
        nharm=9, ppp=256, window="rect",             # spectrum
        noisy=False,                                 # sim includes transient noise
        phase_ref=None, phase_sigs=[], phase_expected=[],   # phase between outputs
        min_ppp=20,                                  # min points per period (worst case)
        min_cycles=10,                               # min steady-state cycles
        target_cycles=50,                            # steady-state cycles to suggest in .tran
    )
    cfg.update(overrides)
    return cfg


# ======================================================================
# Data loading
# ======================================================================

def trace_names_of(spec):
    """'v(a)-v(b)' -> ['v(a)', 'v(b)'];  'v(a)' -> ['v(a)']."""
    m = re.fullmatch(r"\s*(.+\))\s*-\s*(.+\))\s*", spec)
    return [m.group(1), m.group(2)] if m else [spec.strip()]


def get_signal(spec, tr):
    nm = trace_names_of(spec)
    return tr[nm[0]] - tr[nm[1]] if len(nm) == 2 else tr[nm[0]]


def load_traces(raw_path, names):
    if RawRead is None:
        raise RuntimeError("spicelib is not installed. Install it with:\n"
                           "    pip install spicelib --break-system-packages")
    raw = RawRead(raw_path, dialect="ngspice")
    avail = raw.get_trace_names()
    time = np.asarray(raw.get_trace("time").get_wave(), dtype=float)
    keep = np.concatenate(([True], np.diff(time) > 0))      # strictly increasing time
    out = {}
    for n in names:
        try:
            out[n] = np.asarray(raw.get_trace(n).get_wave(), dtype=float)[keep]
        except Exception:
            raise KeyError(f"Trace '{n}' not found in {raw_path}. Available traces: "
                           f"{', '.join(sorted(avail))}")
    return time[keep], out


# ======================================================================
# Signal utilities
# ======================================================================

def find_crossings(t, v, thr):
    """Crossings of thr with linear interpolation. Returns (t_rise, i_rise,
    t_fall, i_fall); i_* is the sample index just before the crossing."""
    s = v - thr
    ir = np.where((s[:-1] < 0) & (s[1:] >= 0))[0]
    jf = np.where((s[:-1] >= 0) & (s[1:] < 0))[0]

    def interp(i):
        return t[i] + (-s[i]) / (s[i + 1] - s[i]) * (t[i + 1] - t[i])
    return interp(ir), ir, interp(jf), jf


def linear_fit(times):
    """t_n ~ t0 + n*T (least squares). Returns (TIE, T, t0)."""
    n = len(times)
    idx = np.arange(n)
    A = np.vstack([idx, np.ones(n)]).T
    T, t0 = np.linalg.lstsq(A, times, rcond=None)[0]
    return times - (t0 + idx * T), T, t0


def circ_mean_phase(times, T, t0=0.0):
    ang = ((times - t0) / T % 1.0) * 2 * np.pi
    return (np.arctan2(np.mean(np.sin(ang)), np.mean(np.cos(ang))) / (2 * np.pi)) % 1.0


def stats(x):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return dict(n=0, mean=np.nan, std=np.nan, min=np.nan, max=np.nan, pp=np.nan)
    return dict(n=len(x), mean=float(x.mean()), std=float(x.std(ddof=1)) if len(x) > 1 else 0.0,
                min=float(x.min()), max=float(x.max()), pp=float(x.max() - x.min()))


def settle_index(x, tol):
    """First index from which x stays within +-tol (relative) of its final
    value (median of the last quarter). len(x) if it never settles."""
    x = np.asarray(x, dtype=float)
    xf = np.median(x[-max(3, len(x) // 4):])
    bad = np.where(np.abs(x - xf) > tol * abs(xf))[0]
    return 0 if len(bad) == 0 else int(bad[-1] + 1)


def window_mean(t, y, ta, tb):
    m = (t >= ta) & (t <= tb)
    return float(_trapz(y[m], t[m]) / (t[m][-1] - t[m][0]))


def window_rms(t, y, ta, tb):
    m = (t >= ta) & (t <= tb)
    return float(np.sqrt(_trapz(y[m] ** 2, t[m]) / (t[m][-1] - t[m][0])))


def wrap180(deg):
    return (deg + 180.0) % 360.0 - 180.0


def fmt_time(s):
    s = max(float(s), 0.0)
    if s < 60:
        return f"{s:.1f} s"
    m, sec = divmod(int(round(s)), 60)
    return f"{m} min {sec:02d} s" if m < 60 else f"{m // 60} h {m % 60:02d} min"


def edge_time(grid, trace, v_lo, v_hi, g_a, g_b, rising):
    """Time (in periods) between crossing v_lo and v_hi inside grid in [g_a, g_b]."""
    m = (grid >= g_a) & (grid <= g_b)
    g, y = grid[m], trace[m]

    def first_cross(level):
        s = y - level
        idx = np.where((s[:-1] < 0) & (s[1:] >= 0))[0] if rising else np.where((s[:-1] >= 0) & (s[1:] < 0))[0]
        if len(idx) == 0:
            return np.nan
        i = idx[0]
        return g[i] + (-s[i]) / (s[i + 1] - s[i]) * (g[i + 1] - g[i])
    a, b = first_cross(v_lo if rising else v_hi), first_cross(v_hi if rising else v_lo)
    return abs(b - a)


def nice_125(x, mode):
    """Round x down ('floor') or up ('ceil') to the 1-2-5 sequence."""
    e = math.floor(math.log10(x))
    m = x / 10 ** e
    steps = (1, 2, 5, 10)
    v = max(s for s in steps if s <= m * (1 + 1e-9)) if mode == "floor" else \
        min(s for s in steps if s >= m * (1 - 1e-9))
    return v * 10 ** e


def spice_fmt(x):
    for suf, sc in (("", 1.0), ("m", 1e-3), ("u", 1e-6), ("n", 1e-9), ("p", 1e-12), ("f", 1e-15)):
        if x >= sc * 0.999999:
            return f"{round(x / sc, 6):g}{suf}"
    return f"{x:g}"


# ======================================================================
# Coherent spectrum
# ======================================================================

def coherent_spectrum(t, x, t_a, T, K, M, window, nharm):
    """FFT of K exact periods (T) resampled with M points per period (cubic
    spline). Returns peak amplitude of the fundamental, harmonics (V, dBV,
    dBc), THD and the complex spectrum X (peak-normalised, bin K = fundamental)."""
    N = K * M
    tg = t_a + np.arange(N) * (T / M)
    cs = CubicSpline(t, x)
    xs = cs(tg)
    w = np.ones(N) if window == "rect" else get_window("hann", N, fftbins=True)
    X = np.fft.rfft(xs * w) / (N * w.mean())
    amp = 2.0 * np.abs(X)
    amp[0] = np.abs(X[0])
    span = 1 if window == "rect" else 2
    freqs = np.fft.rfftfreq(N, d=T / M)
    harm = []
    for h in range(1, nharm + 1):
        kb = h * K
        if kb + span >= len(amp):
            break
        a = float(amp[kb - span:kb + span + 1].max())
        harm.append(dict(h=h, f=float(h / T), amp=a))
    a1 = harm[0]["amp"]
    for hh in harm:
        hh["dBV"] = 20 * math.log10(max(hh["amp"], 1e-30))
        hh["dBc"] = 20 * math.log10(max(hh["amp"] / a1, 1e-30))
    thd = math.sqrt(sum(hh["amp"] ** 2 for hh in harm[1:])) / a1 if len(harm) > 1 else float("nan")
    return dict(freqs=freqs, amp=amp, X=X, dc=float(amp[0]), harmonics=harm,
                thd=thd, thd_dB=20 * math.log10(max(thd, 1e-30)), K=K, N=N)


# ======================================================================
# Phase between outputs
# ======================================================================

def measure_phase(t, tr, ref_spec, sig_spec, T, ta, tb, K, t_ss, spec_ref, spec_sig, expected):
    """Phase of 'sig' relative to 'ref'. Positive = sig LAGS ref (it is later).
    Two estimates: fundamental of the coherent FFT (robust to waveform shape)
    and zero crossings (mean over cycles, with its spread)."""
    ref, sig = get_signal(ref_spec, tr), get_signal(sig_spec, tr)
    mw = (t >= ta) & (t <= tb)

    def mid(x):
        return 0.5 * (x[mw].max() + x[mw].min())
    trr = find_crossings(t, ref, mid(ref))[0]
    trs = find_crossings(t, sig, mid(sig))[0]
    trr = trr[trr >= t_ss - T]
    trs = trs[(trs >= ta) & (trs <= tb)]
    lag_cross = delay_cross = sigma_ps = np.nan
    if len(trr) >= 3 and len(trs) >= 3:
        idx = np.searchsorted(trr, trs, side="right") - 1
        ok = idx >= 0
        d = (trs[ok] - trr[idx[ok]]) / T
        ang = (d % 1.0) * 2 * np.pi
        R = min(np.hypot(np.mean(np.cos(ang)), np.mean(np.sin(ang))), 1.0)
        mean_ph = (np.arctan2(np.mean(np.sin(ang)), np.mean(np.cos(ang))) / (2 * np.pi)) % 1.0
        lag_cross = wrap180(360.0 * mean_ph)
        delay_cross = lag_cross / 360.0 * T * 1e12                      # ps
        sigma_ps = float(np.sqrt(max(-2 * np.log(max(R, 1e-300)), 0.0)) * T * 1e12) + 0.0   # +0.0 avoids "-0.0"
    Xr, Xs = spec_ref["X"][K], spec_sig["X"][K]
    lag_fft = wrap180(math.degrees(np.angle(Xr) - np.angle(Xs)))
    out = dict(ref=ref_spec, sig=sig_spec, lag_fft_deg=float(lag_fft), lag_cross_deg=float(lag_cross),
               delay_fft_ps=float(lag_fft / 360.0 * T * 1e12), delay_cross_ps=float(delay_cross),
               spread_ps=float(sigma_ps), amp_ratio=float(abs(Xs) / abs(Xr)),
               expected_deg=expected,
               error_deg=None if expected is None else float(wrap180(lag_fft - expected)))
    return out


def fold_mean(t, x, t0, T, n_cycles, grid_ui):
    acc = np.zeros_like(grid_ui)
    for k in range(n_cycles):
        acc += np.interp(t0 + (k + grid_ui) * T, t, x)
    return acc / n_cycles


# ======================================================================
# Core: characterization of one simulation
# ======================================================================

def short_sim_hint(t, n_rise, T_est, cfg, t_onset=None):
    dt = float(np.median(np.diff(t)))
    dur = t[-1] - t[0]
    lines = [f"The simulation spans {dur*1e9:.2f} ns (median step {dt*1e12:.2f} ps) and has "
             f"{n_rise} rising crossing(s) in total."]
    if T_est:
        step = nice_125(T_est / 200, "floor")
        if t_onset is not None:
            stop = nice_125(t_onset + cfg["target_cycles"] * T_est, "ceil")
            why = f"stop = steady-state onset ~ {t_onset*1e9:.1f} ns + {cfg['target_cycles']} periods"
        else:
            stop = nice_125(max(2 * dur, 40 * T_est), "ceil")
            why = f"stop >= start-up + {cfg['target_cycles']} periods"
        lines.append(f"Estimated period ~ {T_est*1e12:.1f} ps. Try:  .tran {spice_fmt(step)} {spice_fmt(stop)}  "
                     f"(step = T/200; {why}).")
    else:
        lines.append("No periodic oscillation was detected. Check that the circuit actually starts "
                     "(.ic / initial kick), the signal name and --threshold. If it does oscillate, the run is "
                     f"too short: try a longer .tran, e.g. .tran {spice_fmt(dt)} {spice_fmt(nice_125(5 * dur, 'ceil'))}.")
    return " ".join(lines)


def characterize(raw_path, cfg, outdir=None, plots=True, label=None):
    """Analyzes a .raw file. Returns (result: dict, report: str)."""
    cfg = {**default_config(), **cfg}
    names = []
    for k in ("signal", "pos", "neg", "vsupply", "isupply", "icore"):
        if cfg[k]:
            names.append(cfg[k])
    names += list(cfg["probe"])
    if cfg["phase_ref"]:
        for sp in [cfg["phase_ref"]] + list(cfg["phase_sigs"]):
            names += trace_names_of(sp)
    if not cfg["signal"] and not (cfg["pos"] and cfg["neg"]):
        raise ValueError("Give --signal (already-differential trace) or both --pos and --neg.")
    if cfg["phase_sigs"] and not cfg["phase_ref"]:
        raise ValueError("--phase-sig needs --phase-ref.")
    names = list(dict.fromkeys(names))
    t, tr = load_traces(raw_path, names)

    se = bool(cfg["pos"] and cfg["neg"])
    single = bool(cfg["single_ended"])
    if cfg["signal"]:
        vd, vd_name = tr[cfg["signal"]], cfg["signal"]
    else:
        vd, vd_name = tr[cfg["pos"]] - tr[cfg["neg"]], f"{cfg['pos']}-{cfg['neg']}"
    vcm = 0.5 * (tr[cfg["pos"]] + tr[cfg["neg"]]) if se else None

    L, C, WARN = [], [], []                  # body lines, adequacy-check lines, warnings
    def P(s=""):
        L.append(s)
    def head(s):
        P("=" * 66); P(s); P("=" * 66)

    res = dict(raw=os.path.abspath(raw_path), signal=vd_name, warnings=WARN)
    dt_all = np.diff(t)
    H = [f"File: {raw_path}",
         f"Analyzed signal: {vd_name}   ({len(t)} points, t = {t[0]*1e9:.3f} to {t[-1]*1e9:.3f} ns, "
         f"median step {np.median(dt_all)*1e12:.2f} ps)"]

    # --- threshold and global crossings (for envelope and start-up) ---
    late = t >= t[0] + 0.5 * (t[-1] - t[0])
    thr = cfg["threshold"] if cfg["threshold"] is not None else \
        0.5 * (np.percentile(vd[late], 99) + np.percentile(vd[late], 1))
    tr_all, ir_all, tf_all, jf_all = find_crossings(t, vd, thr)
    if len(tr_all) < 6:
        T_est = float(np.median(np.diff(tr_all))) if len(tr_all) >= 2 else (1.0 / cfg["freq"] if cfg["freq"] else None)
        raise RuntimeError(f"Not enough oscillation found at threshold {thr:.4g} V (signal range "
                           f"{vd.min():.3g} to {vd.max():.3g} V). " + short_sim_hint(t, len(tr_all), T_est, cfg))
    res["threshold"] = float(thr)

    # --- per cycle: period, amplitude ---
    periods_all = np.diff(tr_all)
    mx = np.maximum.reduceat(vd, ir_all)[:-1]
    mn = np.minimum.reduceat(vd, ir_all)[:-1]
    amp_cyc = 0.5 * (mx - mn)
    t_cyc = 0.5 * (tr_all[:-1] + tr_all[1:])
    n_cyc = len(periods_all)

    # --- steady state ---
    i_amp = settle_index(amp_cyc, cfg["amp_tol"])
    i_per = settle_index(periods_all, cfg["freq_tol"])
    ss_fallback = False
    if cfg["t_start"] is not None:
        t_ss = cfg["t_start"]
        ss_note = "forced with --t-start"
    else:
        i_s = max(i_amp, i_per) + cfg["settle_margin"]
        if i_s > n_cyc - 6:
            t_ss = tr_all[n_cyc // 2]
            ss_fallback = True
            ss_note = ("WARNING: no clear settling detected; using the second half of the "
                       "simulation (lengthen the .tran or check .ic)")
        else:
            t_ss = tr_all[i_s]
            ss_note = (f"auto (amplitude within {cfg['amp_tol']*100:g}% and period within "
                       f"{cfg['freq_tol']*100:g}% + {cfg['settle_margin']} cycles)")
    res["t_ss"] = float(t_ss)

    # ------------------------------------------------------------------
    # 3. START-UP
    # ------------------------------------------------------------------
    A_final = float(np.median(amp_cyc[-max(3, n_cyc // 4):]))

    def t_reach(frac):
        idx = np.where(amp_cyc >= frac * A_final)[0]
        return float(t_cyc[idx[0]]) if len(idx) else np.nan
    t10, t90 = t_reach(0.10), t_reach(0.90)
    first_frac = float(amp_cyc[0] / A_final)
    sel = np.where((amp_cyc >= 0.10 * A_final) & (amp_cyc <= 0.50 * A_final))[0]   # exponential growth region
    growth = np.nan
    if len(sel) >= 3:
        growth = float(np.polyfit(t_cyc[sel], np.log(amp_cyc[sel]), 1)[0])
    res["startup"] = dict(A_final=A_final, t10=t10, t90=t90, first_cycle_frac=first_frac,
                          growth_rate=growth, n_growth_pts=int(len(sel)),
                          t_settle_amp=float(tr_all[min(i_amp, n_cyc)]) if i_amp < n_cyc else np.nan,
                          t_settle_freq=float(tr_all[min(i_per, n_cyc)]) if i_per < n_cyc else np.nan)

    # ------------------------------------------------------------------
    # Steady state: crossings, fit, whole-period window
    # ------------------------------------------------------------------
    tr_s = tr_all[tr_all >= t_ss]
    tf_s = tf_all[tf_all >= t_ss]
    if len(tr_s) < 5:
        T_est = float(np.median(periods_all))
        raise RuntimeError(f"Only {len(tr_s)} rising crossings in steady state (starting at t_ss = {t_ss*1e9:.2f} ns). "
                           + short_sim_hint(t, len(tr_all), T_est, cfg, t_onset=t_ss))
    tie_r, T_fit, t0_fit = linear_fit(tr_s)
    tie_f, T_fit_f, t0_f = linear_fit(tf_s) if len(tf_s) >= 3 else (np.array([]), np.nan, np.nan)
    f_osc = 1.0 / T_fit
    ta, tb = tr_s[0], tr_s[-1]                       # whole-period window
    K = len(tr_s) - 1
    per_r = np.diff(tr_s)
    per_f = np.diff(tf_s)
    mwin = (t >= ta) & (t <= tb)
    dt_med = float(np.median(np.diff(t[mwin])))
    dt_max = float(np.max(np.diff(t[mwin])))

    # ------------------------------------------------------------------
    # Simulation adequacy checks (printed first in the report)
    # ------------------------------------------------------------------
    ppp_med, ppp_min = T_fit / dt_med, T_fit / dt_max
    need_tran = False
    C.append("=" * 66)
    C.append("SIMULATION ADEQUACY CHECKS")
    C.append("=" * 66)
    C.append(f"Points per period : median {ppp_med:.0f}, worst case {ppp_min:.0f}   "
             f"(largest step in steady state = {dt_max*1e12:.2f} ps)")
    C.append(f"Steady-state cycles: {K}   rising/falling crossings: {len(tr_s)}/{len(tf_s)}   "
             f"spectral resolution f0/K = {f_osc/K/1e6:.2f} MHz")
    if ppp_min < cfg["min_ppp"]:
        msg = (f"WARN  time step too coarse: worst case is {ppp_min:.1f} points/period "
               f"(< {cfg['min_ppp']}); crossing interpolation, eye and FFT lose accuracy.")
        C.append(msg); WARN.append(msg); need_tran = True
    elif ppp_min < 10 * cfg["nharm"]:
        msg = (f"NOTE  with {ppp_min:.0f} points/period, harmonics above H{max(int(ppp_min // 10), 1)} "
               f"may be inaccurate (rule of thumb: >= 10 points per harmonic = {10*cfg['nharm']} for H{cfg['nharm']}).")
        C.append(msg); WARN.append(msg)
    if cfg["noisy"] and ppp_min < 100:
        msg = "NOTE  noisy simulation: use >= 100-200 points/period so the step does not mask the jitter."
        C.append(msg); WARN.append(msg)
    if K < cfg["min_cycles"]:
        msg = (f"WARN  only {K} steady-state cycles (< {cfg['min_cycles']}): statistics (jitter, "
               f"spreads) and spectral resolution are poor.")
        C.append(msg); WARN.append(msg); need_tran = True
    if ss_fallback:
        msg = "WARN  steady state not clearly reached within the simulation time."
        C.append(msg); WARN.append(msg); need_tran = True
    if need_tran:
        t_onset = t_ss if not ss_fallback else (t[-1] - t[0])
        step = nice_125(T_fit / 200, "floor")
        stop = nice_125(t_onset + cfg["target_cycles"] * T_fit, "ceil")
        if ss_fallback:
            stop = max(stop, nice_125(2 * (t[-1] - t[0]), "ceil"))
        sug = f".tran {spice_fmt(step)} {spice_fmt(stop)}"
        res["suggested_tran"] = sug
        C.append(f"SUGGESTED: {sug}   (step = T/200 ~ {T_fit/200*1e12:.1f} ps rounded down; "
                 f"stop = steady-state onset ~ {t_onset*1e9:.1f} ns + {cfg['target_cycles']} periods). "
                 f"In ngspice the internal step is capped by the tstep you give.")
    if not WARN:
        C.append("OK    time step and number of cycles are adequate.")
    C.append("")

    # ------------------------------------------------------------------
    # 1. FREQUENCY
    # ------------------------------------------------------------------
    res["freq"] = dict(f=float(f_osc), T=float(T_fit), n_cycles=K,
                       T_mean=float(per_r.mean()), T_std=float(per_r.std(ddof=1)), T_pp=float(np.ptp(per_r)))
    head("1. FREQUENCY AND PERIOD (steady state)")
    P(f"Steady state from t = {t_ss*1e9:.3f} ns  [{ss_note}]")
    P(f"Cycles analyzed       : {K}")
    P(f"Frequency (fit)       : {f_osc/1e6:.4f} MHz     Period: {T_fit*1e12:.3f} ps")
    P(f"Period mean +- sigma  : {per_r.mean()*1e12:.3f} +- {per_r.std(ddof=1)*1e12:.4f} ps   (pp = {np.ptp(per_r)*1e12:.4f} ps)")
    if cfg["freq"]:
        P(f"Expected frequency    : {cfg['freq']/1e6:.4f} MHz   deviation = {(f_osc-cfg['freq'])/cfg['freq']*100:+.3f} %")
    P()

    # ------------------------------------------------------------------
    # 2. AMPLITUDE AND COMMON MODE
    # ------------------------------------------------------------------
    vdw = vd[mwin]
    amp_d = dict(pp=float(vdw.max() - vdw.min()), peak_pos=float(vdw.max()), peak_neg=float(vdw.min()),
                 mean=window_mean(t, vd, ta, tb), rms=window_rms(t, vd, ta, tb))
    amp_d["amp"] = amp_d["pp"] / 2
    res["amplitude"] = dict(diff=amp_d)
    res["single_ended"] = single
    if single:
        head("2. AMPLITUDE AND DC LEVEL (single-ended)")
        P(f"Single-ended : {amp_d['peak_neg']:.4f} to {amp_d['peak_pos']:.4f} V  ({amp_d['pp']:.4f} Vpp, "
          f"half swing {amp_d['amp']:.4f} V)")
        P(f"               DC level (mean) {amp_d['mean']:.4f} V   rms {amp_d['rms']:.4f} V   "
          f"mid-level {0.5*(amp_d['peak_pos']+amp_d['peak_neg']):.4f} V")
    else:
        head("2. AMPLITUDE AND COMMON MODE")
        P(f"Differential : {amp_d['pp']:.4f} Vpp  (peak amplitude {amp_d['amp']:.4f} V,  rms {amp_d['rms']:.4f} V)")
        P(f"               extremes {amp_d['peak_neg']:+.4f} / {amp_d['peak_pos']:+.4f} V   "
          f"mean offset {amp_d['mean']*1e3:+.3f} mV  (peak+/peak- asymmetry: {(amp_d['peak_pos']+amp_d['peak_neg'])*1e3:+.2f} mV)")
        if abs(amp_d["mean"]) > 0.25 * amp_d["pp"]:
            msg = ("NOTE  the signal has a large DC offset relative to its swing, so it looks single-ended; "
                   "pass --single-ended for the proper labels (differential-only quantities are meaningless here).")
            P(msg); WARN.append(msg)
    if se:
        for nm in (cfg["pos"], cfg["neg"]):
            y = tr[nm][mwin]
            res["amplitude"][nm] = dict(min=float(y.min()), max=float(y.max()), pp=float(np.ptp(y)),
                                        mean=window_mean(t, tr[nm], ta, tb))
            P(f"{nm:<12}: {y.min():.4f} to {y.max():.4f} V  ({np.ptp(y):.4f} Vpp, mean {res['amplitude'][nm]['mean']:.4f} V)")
        cm = vcm[mwin]
        res["amplitude"]["cm"] = dict(mean=window_mean(t, vcm, ta, tb), pp=float(np.ptp(cm)))
        P(f"Common mode : mean {res['amplitude']['cm']['mean']:.4f} V   ripple {np.ptp(cm)*1e3:.2f} mVpp "
          f"(ripple at 2*f0: second-harmonic effect)")
    for nm in cfg["probe"]:
        y = tr[nm][mwin]
        res["amplitude"][nm] = dict(min=float(y.min()), max=float(y.max()), pp=float(np.ptp(y)),
                                    mean=window_mean(t, tr[nm], ta, tb))
        P(f"{nm:<12}: mean {res['amplitude'][nm]['mean']:.4f} V   ripple {np.ptp(y)*1e3:.2f} mVpp")
    P()

    # ------------------------------------------------------------------
    # 3. START-UP (report)
    # ------------------------------------------------------------------
    s = res["startup"]
    head("3. START-UP")
    P(f"Final amplitude (envelope)  : {A_final:.4f} V peak")
    if first_frac >= 0.5:
        msg = (f"NOTE  the first measured cycle is already at {first_frac*100:.0f}% of the final amplitude: "
               f"start-up is not resolved (aggressive .ic or very short first cycle).")
        P(msg)
        P("      To see the growth use a much smaller .ic imbalance or start from rest.")
        WARN.append(msg)

    def fmt_reach(tt, frac):
        if np.isnan(tt):
            return "n/a"
        return ("<= %.3f ns (already reached in the 1st cycle)" if amp_cyc[0] >= frac * A_final else "%.3f ns") % (tt * 1e9)
    P(f"Time to 10% of final amplitude: {fmt_reach(t10, 0.10)}   (from t = 0 of the simulation)")
    P(f"Time to 90% of final amplitude: {fmt_reach(t90, 0.90)}")
    if not np.isnan(growth):
        P(f"Exponential growth (10%->50%) : {growth:.3e} 1/s  (time constant {1e9/growth:.3f} ns, "
          f"{growth*T_fit:.3f} nepers/cycle, {s['n_growth_pts']} cycles)")
    else:
        P("Exponential growth           : n/a (fewer than 3 cycles between 10% and 50% of the final amplitude)")
    ns_amp = "n/a" if np.isnan(s["t_settle_amp"]) else "%.3f ns" % (s["t_settle_amp"] * 1e9)
    ns_frq = "n/a" if np.isnan(s["t_settle_freq"]) else "%.3f ns" % (s["t_settle_freq"] * 1e9)
    P(f"Amplitude settling (+-{cfg['amp_tol']*100:g}%): {ns_amp}   frequency settling (+-{cfg['freq_tol']*100:g}%): {ns_frq}")
    P("Note: with .ic/uic the start-up begins from an imposed imbalance, not from noise; the time depends")
    P("      on that initial condition and is mainly useful to compare designs/corners.")
    P()

    # ------------------------------------------------------------------
    # 4. POWER
    # ------------------------------------------------------------------
    head("4. POWER")
    pw = {}
    vdd = cfg["vdd"]
    if vdd is None and cfg["vsupply"]:
        vdd = window_mean(t, tr[cfg["vsupply"]], ta, tb)
    for key, nm in (("total", cfg["isupply"]), ("core", cfg["icore"])):
        if not nm:
            continue
        iavg = abs(window_mean(t, tr[nm], ta, tb))
        d = dict(trace=nm, i_mean=float(iavg), i_rms=float(window_rms(t, tr[nm], ta, tb)))
        if vdd is not None:
            d.update(vdd=float(vdd), power=float(vdd * iavg), energy_per_cycle=float(vdd * iavg * T_fit))
            P(f"{key:<6} ({nm}): Idd = {iavg*1e3:.4f} mA   P = {d['power']*1e3:.4f} mW @ VDD={vdd:.3g} V   "
              f"E/cycle = {d['energy_per_cycle']*1e12:.4f} pJ")
        else:
            P(f"{key:<6} ({nm}): Idd = {iavg*1e3:.4f} mA   (power needs --vdd or --vsupply)")
        pw[key] = d
    if not pw:
        P("No --isupply / --icore given: power not computed.")
    elif "total" in pw and "core" in pw:
        P(f"Total - core difference = {(pw['total']['i_mean']-pw['core']['i_mean'])*1e3:.4f} mA "
          f"(bias / reference branches)")
    res["power"] = pw
    P()

    # ------------------------------------------------------------------
    # 5. JITTER
    # ------------------------------------------------------------------
    cc_r, cc_f = np.diff(per_r), np.diff(per_f)
    res["jitter"] = dict(
        tie_rise=stats(tie_r), tie_fall=stats(tie_f),
        period_rise=stats(per_r), period_fall=stats(per_f),
        c2c_rise=stats(cc_r), c2c_fall=stats(cc_f), dt_median=dt_med)
    head("5. JITTER (steady state)")
    for lab, tie, per, cc in (("Rising ", tie_r, per_r, cc_r), ("Falling", tie_f, per_f, cc_f)):
        st, sp, sc = stats(tie), stats(per), stats(cc)
        P(f"{lab}:  TIE rms = {st['std']*1e12:.4f} ps (pp {st['pp']*1e12:.4f})   "
          f"period rms = {sp['std']*1e12:.4f} ps   cycle-to-cycle rms = {sc['std']*1e12:.4f} ps (pp {sc['pp']*1e12:.4f})")
    if not cfg["noisy"]:
        P("NOTE: simulation WITHOUT transient noise. These values are NUMERICAL jitter (median step")
        P(f"      {dt_med*1e12:.2f} ps, crossing interpolation), not physical jitter. The oscillator's real")
        P("      jitter comes from phase noise (see Python_tools/isfpn) or from a simulation with noise;")
        P("      if you run one with transient noise, pass --noisy to drop this note.")
    P()

    # ------------------------------------------------------------------
    # Folded eye (fitted ideal grid), duty cycle, slew
    # ------------------------------------------------------------------
    nU = cfg["ui_window"]
    npts = int(cfg["oversample"] * nU) + 1
    grid_rel = np.linspace(-nU / 2 * T_fit, nU / 2 * T_fit, npts)
    grid_ui = grid_rel / T_fit
    rows = []
    for k in range(len(tr_s)):
        tc = t0_fit + k * T_fit
        if tc + grid_rel[-1] > t[-1] or tc + grid_rel[0] < t_ss - T_fit:
            continue
        rows.append(np.interp(tc + grid_rel, t, vd))
    eye = np.array(rows)
    if len(eye) < 3:
        raise RuntimeError("Too few windows for the eye diagram. " + short_sim_hint(t, len(tr_all), T_fit, cfg))
    mean_tr = eye.mean(axis=0)
    duty = circ_mean_phase(tf_s, T_fit, t0_fit) if len(tf_s) >= 3 else np.nan
    top_c = duty / 2.0
    bot_c = duty + (1 - duty) / 2.0
    if bot_c > grid_ui.max():
        bot_c -= 1.0
    it, ib = np.argmin(np.abs(grid_ui - top_c)), np.argmin(np.abs(grid_ui - bot_c))
    top, bot = stats(eye[:, it]), stats(eye[:, ib])
    lvl_hi, lvl_lo = mean_tr[it], mean_tr[ib]
    v10, v90 = lvl_lo + 0.1 * (lvl_hi - lvl_lo), lvl_lo + 0.9 * (lvl_hi - lvl_lo)
    t_rise = edge_time(grid_ui, mean_tr, v10, v90, bot_c - 1.0 if bot_c > 0 else bot_c, top_c, True) * T_fit
    t_fall = edge_time(grid_ui, mean_tr, v10, v90, top_c, bot_c if bot_c > top_c else bot_c + 1.0, False) * T_fit
    dgrid = np.gradient(mean_tr, grid_rel)
    slew_r = float(dgrid[np.argmin(np.abs(grid_ui - 0.0))])
    slew_f = float(dgrid[np.argmin(np.abs(grid_ui - duty))]) if not np.isnan(duty) else np.nan
    res["eye"] = dict(n_windows=int(len(eye)), duty=float(duty), top=top, bottom=bot,
                      eye_height_center=float(top["mean"] - bot["mean"]),
                      t_rise_10_90=float(t_rise), t_fall_90_10=float(t_fall),
                      slew_rise=slew_r, slew_fall=slew_f)
    head("EXTRA - EYE DIAGRAM / WAVEFORM")
    P(f"Folded windows: {len(eye)}   Duty cycle: {duty*100:.3f} %")
    P(f"High level (pulse center): {top['mean']:+.4f} V  sigma = {top['std']*1e3:.3f} mV")
    P(f"Low level  (pulse center): {bot['mean']:+.4f} V  sigma = {bot['std']*1e3:.3f} mV")
    P(f"Eye height at center     : {res['eye']['eye_height_center']:.4f} V")
    P(f"10-90% rise / fall time  : {t_rise*1e12:.2f} ps / {t_fall*1e12:.2f} ps   ({t_rise/T_fit*100:.1f}% / {t_fall/T_fit*100:.1f}% of the period)")
    P(f"Slew at rising / falling crossing: {slew_r*1e-9:+.3f} V/ns / {slew_f*1e-9:+.3f} V/ns")
    P()

    # ------------------------------------------------------------------
    # Coherent spectrum
    # ------------------------------------------------------------------
    spec = coherent_spectrum(t, vd, ta, T_fit, K, cfg["ppp"], cfg["window"], cfg["nharm"])
    res["spectrum"] = dict(diff=dict(harmonics=spec["harmonics"], thd=spec["thd"], thd_dB=spec["thd_dB"],
                                     dc=spec["dc"]), K=K, ppp=cfg["ppp"], window=cfg["window"],
                           df=float(f_osc / K))
    se_specs = {}
    if se:
        for nm in (cfg["pos"], cfg["neg"]):
            sp = coherent_spectrum(t, tr[nm], ta, T_fit, K, cfg["ppp"], cfg["window"], cfg["nharm"])
            se_specs[nm] = sp
            res["spectrum"][nm] = dict(harmonics=sp["harmonics"], thd=sp["thd"], thd_dB=sp["thd_dB"], dc=sp["dc"])
    head("EXTRA - SPECTRUM (coherent FFT of %d periods, %s window)" % (K, cfg["window"]))
    P(f"Spectral resolution = f0/K = {f_osc/K/1e6:.2f} MHz.  This is a LINE spectrum (harmonics);")
    P("the noise floor / phase-noise skirts do not appear unless the simulation includes noise.")
    sig_lab = "single-ended" if single else "diff"
    if single:
        P(f"DC component = {spec['dc']:.4f} V.  Even harmonics are NOT rejected in a single-ended output.")
    P(f"{'h':>3} {'f (MHz)':>10}  {(sig_lab + ' (V pk)'):>17} {'dBc':>8}" + "".join(f" {('dBc '+nm):>16}" for nm in se_specs))
    for i, hh in enumerate(spec["harmonics"]):
        row = f"{hh['h']:>3} {hh['f']/1e6:>10.2f}  {hh['amp']:>17.5g} {hh['dBc']:>8.1f}"
        for nm, sp in se_specs.items():
            row += f" {sp['harmonics'][i]['dBc']:>16.1f}"
        P(row)
    P(f"{'Single-ended' if single else 'Differential'} THD = {spec['thd_dB']:.1f} dB ({spec['thd']*100:.3f} %)" +
      "".join(f"   THD {nm} = {sp['thd_dB']:.1f} dB" for nm, sp in se_specs.items()))
    if not single:
        P("(A differential output should reject even harmonics; a high differential H2 means asymmetry.)")
    P()

    # ------------------------------------------------------------------
    # Phase between outputs
    # ------------------------------------------------------------------
    phase_list, phase_traces = [], {}
    if cfg["phase_ref"] and cfg["phase_sigs"]:
        ref_spec = cfg["phase_ref"]
        phase_traces[ref_spec] = get_signal(ref_spec, tr)
        spec_ref = coherent_spectrum(t, phase_traces[ref_spec], ta, T_fit, K, cfg["ppp"], cfg["window"], 1)
        exp = list(cfg["phase_expected"])
        for j, sg in enumerate(cfg["phase_sigs"]):
            phase_traces[sg] = get_signal(sg, tr)
            spec_sig = coherent_spectrum(t, phase_traces[sg], ta, T_fit, K, cfg["ppp"], cfg["window"], 1)
            e = exp[j] if j < len(exp) else None
            phase_list.append(measure_phase(t, tr, ref_spec, sg, T_fit, ta, tb, K, t_ss, spec_ref, spec_sig, e))
        res["phase"] = dict(pairs=phase_list)
        head("EXTRA - PHASE BETWEEN OUTPUTS (positive = signal LAGS the reference)")
        P(f"Reference: {ref_spec}   (T = {T_fit*1e12:.2f} ps; 360 deg = one period)")
        for p in phase_list:
            P(f"{p['sig']:<18}: {p['lag_fft_deg']:+8.3f} deg (fundamental/FFT) = {p['delay_fft_ps']:+8.2f} ps   |   "
              f"{p['lag_cross_deg']:+8.3f} deg (zero crossings, spread {p['spread_ps']:.4f} ps)   |   "
              f"amplitude ratio {p['amp_ratio']:.4f}")
            if p["expected_deg"] is not None:
                P(f"{'':<18}  expected {p['expected_deg']:+.2f} deg  ->  error = {p['error_deg']:+.3f} deg "
                  f"({p['error_deg']/360*T_fit*1e12:+.2f} ps)")
        P("(FFT phase compares the fundamentals and ignores waveform shape; the zero-crossing phase is what a")
        P(" digital sampler would see. A noticeable difference between them means the waveforms are not alike.)")
        P()

    report = "\n".join(H + [""] + C + L)

    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "osc_summary.txt"), "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        with open(os.path.join(outdir, "osc_metrics.json"), "w", encoding="utf-8") as fh:
            json.dump(clean(res), fh, indent=2)
        if plots:
            ctx = dict(t=t, vd=vd, vd_name=vd_name, tr=tr, cfg=cfg, se=se, thr=thr, t_ss=t_ss, amp_cyc=amp_cyc,
                       t_cyc=t_cyc, periods_all=periods_all, tr_all=tr_all, A_final=A_final, t10=t10, t90=t90,
                       growth=growth, sel=sel, T_fit=T_fit, grid_ui=grid_ui, eye=eye, duty=duty, top_c=top_c,
                       bot_c=bot_c, tie_r=tie_r, tie_f=tie_f, per_r=per_r, cc_r=cc_r, spec=spec, se_specs=se_specs,
                       f_osc=f_osc, ta=ta, tb=tb, noisy=cfg["noisy"], phase_list=phase_list,
                       phase_traces=phase_traces, K=K, single=single)
            make_plots(ctx, outdir)
    return res, report


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items() if not isinstance(v, np.ndarray)}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if (math.isnan(o) or math.isinf(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


# ======================================================================
# Plots
# ======================================================================

def make_plots(c, outdir):
    t, tn = c["t"], c["t"] * 1e9
    # ---- overview: waveform, envelope, frequency, current ----
    isup = [k for k in (c["cfg"]["isupply"], c["cfg"]["icore"]) if k]
    nrows = 3 + (1 if isup else 0)
    fig, ax = plt.subplots(nrows, 1, figsize=(10, 2.6 * nrows + 0.8), sharex=True)
    ax[0].plot(tn, c["vd"], color="steelblue", lw=1.0, label=c["vd_name"] if c["single"] else f"diff {c['vd_name']}")
    if c["se"]:
        ax[0].plot(tn, c["tr"][c["cfg"]["pos"]], color="darkorange", lw=0.7, alpha=0.7, label=c["cfg"]["pos"])
        ax[0].plot(tn, c["tr"][c["cfg"]["neg"]], color="seagreen", lw=0.7, alpha=0.7, label=c["cfg"]["neg"])
    ax[0].set_ylabel("V"); ax[0].legend(fontsize=8, ncol=3, loc="upper right"); ax[0].grid(alpha=0.3)
    ax[0].set_title("Waveform (the gray line marks the start of steady state)")
    grows = c["amp_cyc"].min() < c["A_final"] / 3          # visible growth -> log scale
    plot_fn = ax[1].semilogy if grows else ax[1].plot
    plot_fn(c["t_cyc"] * 1e9, c["amp_cyc"], "o-", ms=3, color="steelblue", label="per-cycle amplitude")
    ax[1].axhline(c["A_final"], color="k", ls="--", lw=0.8, label=f"final = {c['A_final']:.3f} V")
    for frac, tt, col in ((0.1, c["t10"], "gray"), (0.9, c["t90"], "firebrick")):
        if not np.isnan(tt) and c["amp_cyc"][0] < frac * c["A_final"]:      # only if the crossing was resolved
            ax[1].axvline(tt * 1e9, color=col, ls=":", lw=1, label=f"{int(frac*100)}% at {tt*1e9:.2f} ns")
    if not np.isnan(c["growth"]):
        s = c["sel"]
        p = np.polyfit(c["t_cyc"][s], np.log(c["amp_cyc"][s]), 1)
        tt = c["t_cyc"][s]
        ax[1].plot(tt * 1e9, np.exp(np.polyval(p, tt)), color="firebrick", lw=1.6, label="exponential fit")
    ax[1].set_ylabel("amplitude (V peak)"); ax[1].legend(fontsize=7, ncol=2); ax[1].grid(alpha=0.3, which="both")
    ax[2].plot(c["t_cyc"] * 1e9, 1e-6 / c["periods_all"], "o-", ms=3, color="purple")
    ax[2].axhline(c["f_osc"] / 1e6, color="k", ls="--", lw=0.8, label=f"f0 = {c['f_osc']/1e6:.2f} MHz")
    ax[2].set_ylabel("instantaneous f (MHz)"); ax[2].legend(fontsize=8); ax[2].grid(alpha=0.3)
    if isup:
        ss = t >= c["t_ss"]
        lo, hi = np.inf, -np.inf
        for k in isup:
            ax[3].plot(tn, c["tr"][k] * 1e3, lw=0.9, label=k)
            lo, hi = min(lo, c["tr"][k][ss].min() * 1e3), max(hi, c["tr"][k][ss].max() * 1e3)
        pad = 0.5 * max(hi - lo, 1e-3)               # clip the initial charging spike (uic)
        ax[3].set_ylim(lo - pad, hi + pad)
        ax[3].set_ylabel("current (mA)"); ax[3].legend(fontsize=8); ax[3].grid(alpha=0.3)
        ax[3].set_title("(scale fitted to steady state; the spike at t~0 is the initial charging)", fontsize=8)
    for a in ax:
        a.axvline(c["t_ss"] * 1e9, color="gray", ls="-", lw=1.2, alpha=0.6)
    ax[-1].set_xlabel("time (ns)")
    plt.tight_layout(); plt.savefig(os.path.join(outdir, "osc_overview.png"), dpi=140); plt.close()

    # ---- eye ----
    fig, ax = plt.subplots(figsize=(10, 6))
    for row in c["eye"]:
        ax.plot(c["grid_ui"], row, color="steelblue", alpha=0.15, lw=0.8)
    ax.plot(c["grid_ui"], c["eye"].mean(axis=0), color="navy", lw=1.2, label="mean trace")
    ax.axvline(0, color="green", ls=":", label="rising edge (0 UI)")
    ax.axvline(c["duty"], color="darkorange", ls="--", label=f"falling edge ({c['duty']:.3f} UI)")
    ax.axhline(c["thr"], color="gray", lw=0.6)
    ax.set_xlabel("time (UI = measured period, 0 = rising edge)"); ax.set_ylabel(f"{c['vd_name']} (V)")
    ax.set_title(f"Oscillator eye diagram - T = {c['T_fit']*1e12:.1f} ps, {len(c['eye'])} windows")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(outdir, "osc_eye.png"), dpi=150); plt.close()

    # ---- jitter ----
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for a, (data, ttl, col) in zip(ax, ((c["tie_r"], "TIE (rising)", "firebrick"),
                                        (c["per_r"] - c["per_r"].mean(), "period - mean", "darkorange"),
                                        (c["cc_r"], "cycle-to-cycle", "purple"))):
        d = np.asarray(data) * 1e12
        span = max(np.ptp(d), 1e-6)
        a.hist(d, bins=np.linspace(d.min() - 0.3 * span, d.max() + 0.3 * span, 21), color=col, edgecolor="white")
        a.set_title(f"{ttl}  rms={d.std(ddof=1):.4f} ps"); a.set_xlabel("ps"); a.grid(alpha=0.3)
    fig.suptitle("Jitter" + ("" if c["noisy"] else "  (noise-free simulation: numerical values, not physical)"), fontsize=10)
    plt.tight_layout(); plt.savefig(os.path.join(outdir, "osc_jitter.png"), dpi=140); plt.close()

    # ---- spectrum ----
    sp = c["spec"]
    fig, ax = plt.subplots(figsize=(10, 5))
    nh = c["cfg"]["nharm"]
    fmax = (nh + 0.7) * c["f_osc"]
    m = sp["freqs"] <= fmax

    def dbv(a):
        return 20 * np.log10(np.maximum(a, 1e-12))
    ax.plot(sp["freqs"][m] / 1e9, dbv(sp["amp"][m]), color="steelblue", lw=1.3,
            label="single-ended" if c["single"] else "differential")
    for nm, s2, col in zip(c["se_specs"].keys(), c["se_specs"].values(), ("darkorange", "seagreen")):
        ax.plot(s2["freqs"][m] / 1e9, dbv(s2["amp"][m]), color=col, lw=0.9, alpha=0.8, label=nm)
    for hh in sp["harmonics"]:
        ax.annotate(f"H{hh['h']}", (hh["f"] / 1e9, hh["dBV"]), textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=8, color="navy")
    ax.set_ylim(-140, max(h["dBV"] for h in sp["harmonics"]) + 12)
    ax.set_xlabel("frequency (GHz)"); ax.set_ylabel("peak amplitude (dBV)")
    ax.set_title(f"Spectrum (coherent FFT, {sp['K']} periods, "
                 f"{'single-ended' if c['single'] else 'diff.'} THD = {sp['thd_dB']:.1f} dB)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(outdir, "osc_spectrum.png"), dpi=150); plt.close()

    # ---- phase between outputs ----
    if c["phase_list"]:
        T = c["T_fit"]
        ref_name = c["phase_list"][0]["ref"]
        ref = c["phase_traces"][ref_name]
        mid = 0.5 * (ref[(t >= c["ta"]) & (t <= c["tb"])].max() + ref[(t >= c["ta"]) & (t <= c["tb"])].min())
        tr_ref = find_crossings(t, ref, mid)[0]
        tr_ref = tr_ref[tr_ref >= c["ta"]]
        t0 = tr_ref[0]
        n_cyc = max(min(c["K"], int((t[-1] - t0) / T) - 2), 1)
        grid = np.linspace(0, 1, 361)
        fig, ax = plt.subplots(figsize=(10, 5.5))
        for nm, col in zip([ref_name] + [p["sig"] for p in c["phase_list"]],
                           ("black", "firebrick", "seagreen", "darkorange", "purple", "teal")):
            x = c["phase_traces"][nm]
            mw = (t >= c["ta"]) & (t <= c["tb"])
            xn = (x - 0.5 * (x[mw].max() + x[mw].min())) / (0.5 * np.ptp(x[mw]))
            lab = nm
            for p in c["phase_list"]:
                if p["sig"] == nm:
                    lab = f"{nm}  ({p['lag_fft_deg']:+.2f} deg, {p['delay_fft_ps']:+.1f} ps)"
            ax.plot(grid * 360, fold_mean(t, xn, t0, T, n_cyc, grid), color=col, lw=1.6, label=lab)
        ax.axhline(0, color="gray", lw=0.6)
        ax.set_xlabel("phase relative to the reference rising edge (deg)")
        ax.set_ylabel("normalized signal (offset removed, amplitude = 1)")
        ax.set_xlim(0, 360); ax.set_xticks(range(0, 361, 45))
        ax.set_title(f"Phase between outputs (reference: {ref_name}; positive = lag)")
        ax.legend(fontsize=8, loc="upper right"); ax.grid(alpha=0.3)
        plt.tight_layout(); plt.savefig(os.path.join(outdir, "osc_phase.png"), dpi=150); plt.close()
    print(f"Plots saved in: {outdir}/ (osc_overview, osc_eye, osc_jitter, osc_spectrum"
          f"{', osc_phase' if c['phase_list'] else ''} .png)")


# ======================================================================
# 6. Tuning curve: sweep (runs ngspice) and tuning (analyzes .raw files)
# ======================================================================

_SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12}


def parse_spice_number(s):
    m = re.fullmatch(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-zA-Z]*)", s.strip())
    if not m:
        raise ValueError(f"Invalid value: {s}")
    num, suf = float(m.group(1)), m.group(2).lower()
    if not suf:
        return num
    for key in ("meg",) + tuple(k for k in _SUFFIX if k != "meg"):
        if suf.startswith(key):
            return num * _SUFFIX[key]
    return num


def _na_note(ax, msg):
    """Writes a centered note in an empty panel (so it does not look like a plotting error)."""
    ax.text(0.5, 0.5, msg, transform=ax.transAxes, ha="center", va="center", color="gray", fontsize=10)


def tuning_analysis(entries, cfg, outdir, ctrl_label, ctrl_scale=1.0, title="Oscillator tuning curve"):
    os.makedirs(outdir, exist_ok=True)
    rows = []
    n_tot = len(entries)
    print(f"\nAnalyzing {n_tot} simulation(s)...", flush=True)
    t_an = time.time()
    for i_run, (val, raw) in enumerate(sorted(entries, key=lambda e: e[0]), start=1):
        tag = f"{val:.6g}"
        t_pt = time.time()
        try:
            r, _ = characterize(raw, cfg, outdir=os.path.join(outdir, f"run_{tag}"), plots=False)
            pw = r["power"].get("total") or r["power"].get("core") or {}
            ph = (r.get("phase", {}).get("pairs") or [{}])[0]
            rows.append(dict(ctrl=val, f=r["freq"]["f"], amp=r["amplitude"]["diff"]["amp"],
                             vcm=r["amplitude"].get("cm", {}).get("mean", np.nan),
                             power=pw.get("power", np.nan), idd=pw.get("i_mean", np.nan),
                             energy=pw.get("energy_per_cycle", np.nan), t90=r["startup"]["t90"],
                             thd=r["spectrum"]["diff"]["thd_dB"],
                             phase=ph.get("lag_fft_deg", np.nan),
                             phase_err=(ph.get("error_deg") if ph.get("error_deg") is not None else np.nan),
                             nwarn=len([w for w in r["warnings"] if w.startswith("WARN")]), ok=1))
            el = time.time() - t_an
            print(f"  [{i_run}/{n_tot}] {val/ctrl_scale:g}: f = {rows[-1]['f']/1e6:.3f} MHz, "
                  f"{rows[-1]['nwarn']} warning(s) | {fmt_time(time.time() - t_pt)} | elapsed {fmt_time(el)} | "
                  f"ETA {fmt_time(el / i_run * (n_tot - i_run))}", flush=True)
        except Exception as e:
            print(f"  [{i_run}/{n_tot}] {val/ctrl_scale:g}: ANALYSIS FAILED -> {e}", file=sys.stderr, flush=True)
            rows.append(dict(ctrl=val, f=np.nan, amp=np.nan, vcm=np.nan, power=np.nan, idd=np.nan,
                             energy=np.nan, t90=np.nan, thd=np.nan, phase=np.nan, phase_err=np.nan,
                             nwarn=-1, ok=0))
    x = np.array([r["ctrl"] for r in rows]) / ctrl_scale      # control axis in the requested units
    f = np.array([r["f"] for r in rows])
    good = np.isfinite(f)
    kvco = np.full(len(x), np.nan)
    if good.sum() >= 2:                                        # with 2 points it is the secant slope
        kvco[good] = np.gradient(f[good], x[good])
    for r, k in zip(rows, kvco):
        r["kvco"] = float(k)                                   # Hz per (scaled) control unit
    has_phase = any(np.isfinite(r["phase"]) for r in rows)
    cols = ["ctrl", "f", "amp", "vcm", "idd", "power", "energy", "t90", "thd", "kvco", "phase", "phase_err", "nwarn", "ok"]
    with open(os.path.join(outdir, "tuning.csv"), "w") as fh:
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(f"{(r[k]/ctrl_scale if k == 'ctrl' else r[k]):.8g}" for k in cols) + "\n")
    print("\n" + "-" * 78)
    print(f"{ctrl_label:>14} {'f (MHz)':>10} {'Kvco (MHz/u)':>13} {'Adiff (V)':>10} {'P (mW)':>9} {'E/cycle (pJ)':>13} "
          f"{'THD (dB)':>9}" + (f" {'phase (deg)':>12}" if has_phase else "") + f" {'warns':>6}")
    for r in rows:
        print(f"{r['ctrl']/ctrl_scale:>14.5g} {r['f']/1e6:>10.3f} {r['kvco']/1e6:>13.4g} {r['amp']:>10.4f} "
              f"{r['power']*1e3:>9.4f} {r['energy']*1e12:>13.4f} {r['thd']:>9.1f}"
              + (f" {r['phase']:>12.3f}" if has_phase else "") + f" {r['nwarn']:>6d}")
    ncols = 3 if has_phase else 2
    fig, ax = plt.subplots(2, ncols, figsize=(5.5 * ncols, 7.5), squeeze=False)
    ax[0, 0].plot(x, f / 1e6, "o-", color="steelblue"); ax[0, 0].set_ylabel("frequency (MHz)")
    ax[0, 1].plot(x, kvco / 1e6, "o-", color="purple"); ax[0, 1].set_ylabel("Kvco = df/dctrl (MHz per axis unit)")
    if not np.isfinite(kvco).any():
        _na_note(ax[0, 1], "Kvco n/a: needs at least 2 points\nwith a valid frequency")
    ax[1, 0].plot(x, [r["amp"] for r in rows], "o-", color="seagreen", label="diff. amplitude (V peak)")
    ax[1, 0].plot(x, [r["vcm"] for r in rows], "s--", color="gray", label="common mode (V)")
    ax[1, 0].legend(fontsize=8); ax[1, 0].set_ylabel("V")
    ax[1, 1].plot(x, np.array([r["power"] for r in rows]) * 1e3, "o-", color="firebrick")
    ax2 = ax[1, 1].twinx(); ax2.plot(x, np.array([r["energy"] for r in rows]) * 1e12, "s--", color="darkorange")
    ax2.set_ylabel("energy/cycle (pJ)", color="darkorange"); ax[1, 1].set_ylabel("power (mW)", color="firebrick")
    if has_phase:
        ax[0, 2].plot(x, [r["phase"] for r in rows], "o-", color="teal"); ax[0, 2].set_ylabel("phase vs. reference (deg)")
        ax[1, 2].plot(x, [r["thd"] for r in rows], "o-", color="gray"); ax[1, 2].set_ylabel("differential THD (dB)")
    for a in ax.flat:
        a.set_xlabel(ctrl_label); a.grid(alpha=0.3)
    fig.suptitle(title)
    plt.tight_layout(); plt.savefig(os.path.join(outdir, "osc_tuning.png"), dpi=140); plt.close()
    print(f"\nSaved: {outdir}/tuning.csv and osc_tuning.png")
    return rows


# ----------------------------------------------------------------------
# PVT corners: a corner = (process section of the .lib, temperature, VDD)
# ----------------------------------------------------------------------

PRESETS = {
    "worst3":   ["ss:125:3.0", "typical:60:3.3", "ff:-40:3.6"],
    "process5": ["typical:60:3.3", "ff:60:3.3", "ss:60:3.3", "fs:60:3.3", "sf:60:3.3"],
}
# Full PVT grids (same temperatures and supplies as pvt_runner.py: -40/27/125 C and 3.0/3.3/3.6 V)
_PVT_TEMPS, _PVT_VDDS = (-40, 27, 125), (3.0, 3.3, 3.6)
PRESETS["pvt45"] = [f"{p}:{t}:{v}" for p in ("typical", "ff", "ss", "fs", "sf") for t in _PVT_TEMPS for v in _PVT_VDDS]
PRESETS["pvt27"] = [f"{p}:{t}:{v}" for p in ("typical", "ff", "ss") for t in _PVT_TEMPS for v in _PVT_VDDS]
PRESETS["temp3"] = [f"typical:{t}:3.3" for t in _PVT_TEMPS]       # temperature only (typical, 3.3 V)
PRESETS["vdd3"] = [f"typical:27:{v}" for v in _PVT_VDDS]          # supply only (typical, 27 C)
_SECTION_ALIAS = {"tt": "typical", "typ": "typical", "typical": "typical", "ff": "ff", "ss": "ss", "fs": "fs", "sf": "sf"}
_LIB_RE = re.compile(r"(?im)^(\s*\.lib\s+\S+\s+)(typical|tt|ff|ss|fs|sf)(\s*)$")


def parse_corner(spec):
    """'ss:125:3.0' -> dict(proc='ss', temp=125.0, vdd=3.0, label='ss_125C_3.0V')."""
    parts = spec.split(":")
    if len(parts) != 3 or parts[0].lower() not in _SECTION_ALIAS:
        raise ValueError(f"Invalid corner '{spec}': use name:temp_C:VDD with name in typical/tt/ff/ss/fs/sf "
                         f"(e.g. ss:125:3.0)")
    proc = _SECTION_ALIAS[parts[0].lower()]
    temp, vdd = float(parts[1]), float(parts[2])
    return dict(proc=proc, temp=temp, vdd=vdd, label=f"{proc}_{temp:g}C_{vdd:g}V")


def expand_corners(presets, singles):
    specs = []
    for p in presets or []:
        if p not in PRESETS:
            raise ValueError(f"Unknown preset '{p}'. Available: {', '.join(PRESETS)}")
        specs += PRESETS[p]
    specs += singles or []
    corners, seen = [], set()
    for s in specs:
        c = parse_corner(s)
        if c["label"] not in seen:
            seen.add(c["label"]); corners.append(c)
    return corners


def apply_corner(txt, corner):
    """Rewrites, in the netlist text: the process section of the '.lib <file> <section>' line, VDD= and
    TEMP= inside '.param' lines (and their '+' continuations), and a literal '.temp <number>' if present."""
    txt, n_lib = _LIB_RE.subn(lambda m: m.group(1) + corner["proc"] + m.group(3), txt)
    if n_lib == 0:
        raise RuntimeError("No '.lib <file> <section>' line with a process section (typical/ff/ss/fs/sf) "
                           "was found in the netlist.")
    out, in_param, hit = [], False, dict(VDD=0, TEMP=0)
    for line in txt.split("\n"):
        s = line.lstrip().lower()
        if s.startswith(".param"):
            in_param = True
        elif not s.startswith("+"):
            in_param = False
        if in_param:
            for key, val in (("VDD", corner["vdd"]), ("TEMP", corner["temp"])):
                line, k = re.subn(rf"(?i)\b{key}\s*=\s*[^\s]+", f"{key}={val:g}", line)
                hit[key] += k
        out.append(line)
    txt = "\n".join(out)
    if hit["VDD"] == 0:
        raise RuntimeError("No 'VDD=' found in a .param line of the netlist (needed to apply the corner).")
    if hit["TEMP"] == 0:
        txt, k = re.subn(r"(?im)^(\s*\.temp\s+)[-+\d.eE]+", lambda m: m.group(1) + f"{corner['temp']:g}", txt)
        if k == 0:
            raise RuntimeError("No 'TEMP=' in a .param line (nor a literal '.temp <number>') found in the netlist.")
    return txt


def run_one(netlist_text, line_re, template, value, rundir, tag, path_subs, ngspice, corner=None,
            threads=1, omp_wait=None, timeout=300, mc=None):
    rundir = os.path.abspath(rundir)
    os.makedirs(rundir, exist_ok=True)
    txt = netlist_text
    for old, new in path_subs:
        txt = txt.replace(old, new)
    if corner is not None:
        txt = apply_corner(txt, corner)
    if line_re is not None:
        if not line_re.search(txt):
            raise RuntimeError("The line to replace was not found in the netlist (check --line-prefix).")
        txt = line_re.sub(template.format(v=value), txt, count=1)
    if mc is not None:
        txt = apply_mc(txt, mc["mode"], mc["skew"], mc["seed"])
    raw = os.path.abspath(os.path.join(rundir, f"{tag}.raw"))
    txt, n = re.subn(r"(?im)^(\s*write\s+)\S+", lambda m: m.group(1) + raw, txt)
    if n == 0:
        raise RuntimeError("The netlist has no 'write file.raw' line in its .control block.")
    if threads and threads > 0:
        # A 'set num_threads=N' in ~/.spiceinit or spinit overrides OMP_NUM_THREADS, so a plain ngspice may use
        # many OpenMP threads per process (seen: ~800 % CPU for one run). Forcing it inside .control gives
        # one thread per process: several processes then scale almost linearly.
        txt = re.sub(r"(?im)^\s*set\s+num_threads\s*=.*\n", "", txt)
        txt, n = re.subn(r"(?im)^(\s*\.control\s*)$", lambda m: m.group(1) + f"\nset num_threads={int(threads)}", txt, count=1)
        if n == 0:
            raise RuntimeError("The netlist has no '.control' block (needed to set num_threads).")
    cir = os.path.join(rundir, f"{tag}.spice")
    with open(cir, "w") as fh:
        fh.write(txt)
    log = os.path.join(rundir, f"{tag}.log")
    env = dict(os.environ)
    if omp_wait:                                   # None = leave the environment untouched
        env["OMP_WAIT_POLICY"] = omp_wait
    with open(log, "w") as lf:
        try:
            subprocess.run([ngspice, "-b", cir], stdout=lf, stderr=subprocess.STDOUT, cwd=rundir, env=env,
                           check=False, timeout=(timeout or None))
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"ngspice timed out after {timeout:g} s (stuck run kept: {cir}); see --timeout")
    if not os.path.isfile(raw):
        raise RuntimeError(f"ngspice did not produce {raw}; check {log}")
    return raw


_CORNER_COLORS = {"ss": "firebrick", "typical": "seagreen", "ff": "royalblue", "fs": "darkorange", "sf": "purple"}


def corners_comparison(results, outdir, ctrl_label, ctrl_scale=1.0, target_f=None):
    """results: list of (corner, rows) as returned by tuning_analysis. Writes corners_summary.csv,
    corners_tuning.csv and corners_tuning.png, and prints the frequency range per corner, the range common
    to all corners and (optionally) the control value needed for target_f in each corner."""
    results = [(c, r) for c, r in results if r and any(np.isfinite(x["f"]) for x in r)]
    if len(results) < 1:
        return
    os.makedirs(outdir, exist_ok=True)
    print("\n" + "=" * 78 + "\nCORNER COMPARISON\n" + "=" * 78)
    summ = []
    for c, rows in results:
        x = np.array([r["ctrl"] for r in rows]) / ctrl_scale
        f = np.array([r["f"] for r in rows]); ok = np.isfinite(f)
        kv = np.array([r.get("kvco", np.nan) for r in rows])
        pw = np.array([r["power"] for r in rows])
        s = dict(corner=c["label"], proc=c["proc"], temp=c["temp"], vdd=c["vdd"], n_ok=int(ok.sum()), n=len(rows),
                 fmin=np.nanmin(f), fmax=np.nanmax(f), kvco_mean=np.nanmean(kv) if np.isfinite(kv).any() else np.nan,
                 pmin=np.nanmin(pw), pmax=np.nanmax(pw))
        s["tuning_range_pct"] = 100 * (s["fmax"] - s["fmin"]) / (0.5 * (s["fmax"] + s["fmin"]))
        if target_f:
            o = np.argsort(f[ok]); fs, xs = f[ok][o], x[ok][o]
            s["target_f"] = target_f
            s["ctrl_target"] = (float(np.interp(target_f, fs, xs))
                                if len(fs) >= 2 and fs[0] <= target_f <= fs[-1] else float("nan"))
        summ.append(s)
    print(f"{'corner':>16} {'pts':>5} {'fmin (MHz)':>11} {'fmax (MHz)':>11} {'range (%)':>10} "
          f"{'Kvco avg (MHz/u)':>17} {'P min..max (mW)':>18}")
    for s in summ:
        print(f"{s['corner']:>16} {s['n_ok']:>2}/{s['n']:<2} {s['fmin']/1e6:>11.2f} {s['fmax']/1e6:>11.2f} "
              f"{s['tuning_range_pct']:>10.1f} {s['kvco_mean']/1e6:>17.4g} "
              f"{s['pmin']*1e3:>8.3f}..{s['pmax']*1e3:<8.3f}")
    if len(summ) > 1:
        lo, hi = max(s["fmin"] for s in summ), min(s["fmax"] for s in summ)
        if lo < hi:
            print(f"\nFrequency range reachable in ALL corners: {lo/1e6:.2f} .. {hi/1e6:.2f} MHz "
                  f"(overall envelope {min(s['fmin'] for s in summ)/1e6:.2f} .. {max(s['fmax'] for s in summ)/1e6:.2f} MHz)")
        else:
            print(f"\nNo frequency is reachable in ALL corners with this control range "
                  f"(highest fmin = {lo/1e6:.2f} MHz > lowest fmax = {hi/1e6:.2f} MHz): widen the control range.")
    else:
        lo = hi = None
    ctrl_all = sorted({round(r["ctrl"] / ctrl_scale, 12) for _, rows in results for r in rows})
    with open(os.path.join(outdir, "corners_summary.csv"), "w") as fh:
        keys = ["corner", "proc", "temp", "vdd", "n_ok", "n", "fmin", "fmax", "tuning_range_pct", "kvco_mean", "pmin", "pmax"]
        if target_f:
            keys += ["target_f", "ctrl_target"]       # ctrl_target in control units (same as the printed table); nan = out of range
        fh.write(",".join(keys) + "\n")
        for s in summ:
            fh.write(",".join(str(s[k]) if isinstance(s[k], (str, int)) else f"{s[k]:.8g}" for k in keys) + "\n")
    with open(os.path.join(outdir, "corners_tuning.csv"), "w") as fh:
        fh.write("ctrl," + ",".join(f"f_{c['label']}" for c, _ in results) + "\n")
        for cv in ctrl_all:
            vals = []
            for _, rows in results:
                m = [r["f"] for r in rows if abs(r["ctrl"] / ctrl_scale - cv) <= 1e-9 * max(1.0, abs(cv))]
                vals.append(f"{m[0]:.8g}" if m else "nan")
            fh.write(f"{cv:.8g}," + ",".join(vals) + "\n")
    if target_f:
        print(f"\nControl value needed for f = {target_f/1e6:g} MHz (linear interpolation of each curve):")
        for c, rows in results:
            x = np.array([r["ctrl"] for r in rows]) / ctrl_scale
            f = np.array([r["f"] for r in rows]); ok = np.isfinite(f)
            o = np.argsort(f[ok]); fs, xs = f[ok][o], x[ok][o]
            if len(fs) < 2 or not (fs[0] <= target_f <= fs[-1]):
                print(f"  {c['label']:>16}: out of range ({fs[0]/1e6:.1f}..{fs[-1]/1e6:.1f} MHz)" if len(fs) else
                      f"  {c['label']:>16}: no valid points")
            else:
                print(f"  {c['label']:>16}: {np.interp(target_f, fs, xs):.4g}  ({ctrl_label})")
    # --- comparison figure ---
    has_phase = any(np.isfinite(r["phase"]) for _, rows in results for r in rows)
    fig, ax = plt.subplots(2, 3, figsize=(16, 8.5))
    many = len(results) > 6
    if many:
        vs = sorted({c["vdd"] for c, _ in results}); ts = sorted({c["temp"] for c, _ in results})
        ls_vdd = {v: ["-", "--", ":", "-."][i % 4] for i, v in enumerate(vs)}
        alpha_t = {t: (0.35 + 0.65 * (t - ts[0]) / (ts[-1] - ts[0]) if len(ts) > 1 else 1.0) for t in ts}
    panels = [(ax[0, 0], "f", 1e-6, "frequency (MHz)"), (ax[0, 1], "kvco", 1e-6, "Kvco = df/dctrl (MHz per axis unit)"),
              (ax[0, 2], "amp", 1.0, "differential amplitude (V peak)"), (ax[1, 0], "power", 1e3, "power (mW)"),
              (ax[1, 1], "energy", 1e12, "energy per cycle (pJ)"),
              (ax[1, 2], "phase" if has_phase else "thd", 1.0, "phase vs. reference (deg)" if has_phase else "differential THD (dB)")]
    for a, key, k, yl in panels:
        for c, rows in results:
            x = np.array([r["ctrl"] for r in rows]) / ctrl_scale
            y = np.array([r.get(key, np.nan) for r in rows]) * k
            if many:    # color = process, line style = VDD, opacity = temperature (as in pvt_runner.py)
                a.plot(x, y, ls=ls_vdd[c["vdd"]], lw=1.2, color=_CORNER_COLORS.get(c["proc"], None), alpha=alpha_t[c["temp"]])
            else:
                a.plot(x, y, "o-", ms=4, color=_CORNER_COLORS.get(c["proc"], None), label=c["label"])
        a.set_xlabel(ctrl_label); a.set_ylabel(yl); a.grid(alpha=0.3)
    if not any(np.isfinite(r.get("kvco", np.nan)) for _, rows in results for r in rows):
        _na_note(ax[0, 1], "Kvco n/a: needs at least 2 points\nwith a valid frequency per corner")
    a = ax[0, 0]
    if len(results) > 1:
        fm = np.array([[next((r["f"] for r in rows if abs(r["ctrl"] / ctrl_scale - cv) <= 1e-9 * max(1.0, abs(cv))), np.nan)
                        for cv in ctrl_all] for _, rows in results]) / 1e6
        with np.errstate(all="ignore"):
            a.fill_between(ctrl_all, np.nanmin(fm, axis=0), np.nanmax(fm, axis=0), color="gray", alpha=0.15, lw=0)
        if lo is not None and lo < hi:
            a.axhspan(lo / 1e6, hi / 1e6, color="gold", alpha=0.25, label="common to all corners")
    if target_f:
        a.axhline(target_f / 1e6, color="k", ls=":", lw=1, label="target f")
    if many:
        from matplotlib.lines import Line2D
        procs = list(dict.fromkeys(c["proc"] for c, _ in results))
        h = [Line2D([], [], color=_CORNER_COLORS.get(p, "k"), lw=2, label=p) for p in procs]
        h += [Line2D([], [], color="gray", ls=ls_vdd[v], label=f"VDD = {v:g} V") for v in vs]
        if len(ts) > 1:
            h += [Line2D([], [], color="gray", alpha=alpha_t[t], lw=2, label=f"{t:g} C") for t in (ts[0], ts[-1])]
            h[-2].set_label(f"{ts[0]:g} C (lighter)"); h[-1].set_label(f"{ts[-1]:g} C (darker)")
        ax[0, 0].legend(handles=h, fontsize=7, ncol=2)
    else:
        ax[0, 0].legend(fontsize=8)
    fig.suptitle("Oscillator tuning curve across PVT corners")
    plt.tight_layout(); plt.savefig(os.path.join(outdir, "corners_tuning.png"), dpi=140); plt.close()
    print(f"\nSaved: {outdir}/corners_summary.csv (includes the control value for the target f), corners_tuning.csv and corners_tuning.png", flush=True)


# ----------------------------------------------------------------------
# Monte Carlo ('mc' subcommand) for the gf180mcuD statistical models
# ----------------------------------------------------------------------
# The PDK switches the variations with two parameters: sw_stat_global (process, common to every device of
# a run) and sw_stat_mismatch (independent per instance). The global part only exists in the 'statistical'
# library section (centered on typical); the mismatch part works on top of any corner section
# (typical / ss / ff / fs / sf). Every run gets its own '.option seed=N'.

MC_METRICS = [("f", "f", "MHz", 1e-6), ("amp", "Adiff", "V", 1.0), ("power", "P", "mW", 1e3),
              ("energy", "E/cycle", "pJ", 1e12), ("thd", "THD", "dB", 1.0), ("phase_err", "phase err", "deg", 1.0)]
_MC_SW = {"global": (1, 0), "mismatch": (0, 1), "both": (1, 1)}
_ROW_KEYS = ["f", "amp", "vcm", "power", "idd", "energy", "t90", "thd", "phase", "phase_err", "nwarn"]


def apply_mc(txt, mode, skew, seed):
    """Selects the statistical switches (and, for global variation, the 'statistical' section) and a seed."""
    g, m = _MC_SW[mode]
    mt = _LIB_RE.search(txt)
    if not mt:
        raise RuntimeError("No '.lib <file> <section>' line (typical/ff/ss/fs/sf) found in the netlist.")
    if g:
        if mt.group(2).lower() not in ("typical", "tt"):
            raise RuntimeError(f"global variation (modes global/both) only exists around the typical corner, "
                               f"but the netlist/corner uses '{mt.group(2)}'. Use --mc-mode mismatch for ss/ff/fs/sf.")
        txt = _LIB_RE.sub(lambda x: x.group(1) + "statistical" + x.group(3), txt, count=1)
    lines = txt.split("\n")
    last = max((i for i, l in enumerate(lines) if re.match(r"(?i)^\s*\.(include|inc|lib)\b", l)), default=0)
    lines.insert(last + 1, ".param sw_stat_global=%d sw_stat_mismatch=%d mc_skew=%g res_mc_skew=%g cap_mc_skew=%g"
                 % (g, m, skew, skew, skew))      # after every .include/.lib, so design.ngspice cannot reset them
    lines.insert(1, ".option seed=%d" % int(seed))   # line 0 is the netlist title
    return "\n".join(lines)


def row_from_result(r):
    pw = r["power"].get("total") or r["power"].get("core") or {}
    ph = (r.get("phase", {}).get("pairs") or [{}])[0]
    pe = ph.get("error_deg")
    return dict(f=r["freq"]["f"], amp=r["amplitude"]["diff"]["amp"], vcm=r["amplitude"].get("cm", {}).get("mean", np.nan),
                power=pw.get("power", np.nan), idd=pw.get("i_mean", np.nan), energy=pw.get("energy_per_cycle", np.nan),
                t90=r["startup"]["t90"], thd=r["spectrum"]["diff"]["thd_dB"], phase=ph.get("lag_fft_deg", np.nan),
                phase_err=(pe if pe is not None else np.nan),
                nwarn=len([w for w in r["warnings"] if w.startswith("WARN")]))


def mc_stats(vals):
    v = np.asarray(vals, float)
    v = v[np.isfinite(v)]
    n = len(v)
    if n == 0:
        return None
    sd = float(v.std(ddof=1)) if n > 1 else float("nan")
    mean = float(v.mean())
    return dict(n=n, mean=mean, std=sd, rel=(100 * sd / abs(mean) if mean else float("nan")),
                se=(sd / math.sqrt(2 * (n - 1)) if n > 1 else float("nan")), mn=float(v.min()), mx=float(v.max()),
                p5=float(np.percentile(v, 5)), p50=float(np.percentile(v, 50)), p95=float(np.percentile(v, 95)))


def parse_spec(s):
    """'f:550meg:650meg' -> ('f', 5.5e8, 6.5e8); an empty side means no limit ('thd::-20')."""
    p = s.split(":")
    keys = [m[0] for m in MC_METRICS] + ["vcm", "idd", "t90", "phase"]
    if len(p) != 3 or p[0] not in keys:
        raise ValueError(f"Invalid --spec '{s}': use metric:min:max with metric in {keys} (e.g. f:550meg:650meg)")
    lo = parse_spice_number(p[1]) if p[1] else -math.inf
    hi = parse_spice_number(p[2]) if p[2] else math.inf
    return p[0], lo, hi


def mc_yield(rows, specs):
    """Fraction of ALL samples (failed ones count as failures) meeting every spec; per-spec fractions too."""
    n = len(rows)
    if not specs or n == 0:
        return None
    per = []
    for k, lo, hi in specs:
        per.append(sum(1 for r in rows if r["ok"] and lo <= r[k] <= hi) / n)
    joint = sum(1 for r in rows if r["ok"] and all(lo <= r[k] <= hi for k, lo, hi in specs)) / n
    return joint, per


def omp_policy(args):
    ncpu = os.cpu_count() or 1
    if args.omp_wait == "auto":
        return "passive" if (args.jobs > 1 and (args.threads == 0 or args.jobs * args.threads > ncpu)) else None
    return None if args.omp_wait == "none" else args.omp_wait


def _case_color(proc):
    return _CORNER_COLORS.get(proc, "gray")


def _mc_hist_figure(path, rows_ok, nominal, specs, title):
    panels = [("f", 1e-6, "f (MHz)"), ("amp", 1.0, "Adiff (V peak)"), ("power", 1e3, "power (mW)"),
              ("energy", 1e12, "energy/cycle (pJ)"), ("thd", 1.0, "THD (dB)")]
    fig, ax = plt.subplots(2, 3, figsize=(15, 8))
    for a, (k, sc, lab) in zip(ax.flat, panels):
        v = np.array([r[k] for r in rows_ok], float) * sc
        v = v[np.isfinite(v)]
        if len(v) < 2:
            _na_note(a, "not enough samples"); a.set_xlabel(lab); continue
        mu, sd = v.mean(), v.std(ddof=1)
        a.hist(v, bins=max(5, int(math.sqrt(len(v)))), density=True, color="steelblue", alpha=0.7)
        if sd > 0:
            xs = np.linspace(v.min() - sd, v.max() + sd, 200)
            a.plot(xs, np.exp(-0.5 * ((xs - mu) / sd) ** 2) / (sd * math.sqrt(2 * math.pi)), "k-", lw=1)
        if nominal and np.isfinite(nominal.get(k, np.nan)):
            a.axvline(nominal[k] * sc, color="darkorange", ls="--", label="nominal")
        for sk, lo, hi in specs:
            if sk == k:
                for lim in (lo, hi):
                    if math.isfinite(lim):
                        a.axvline(lim * sc, color="firebrick", ls=":", label="spec")
        a.set_title("%s: mean %.4g, sigma %.3g (%.2f %%)" % (lab, mu, sd, 100 * sd / abs(mu) if mu else float("nan")), fontsize=9)
        a.set_xlabel(lab); a.grid(alpha=0.3)
    a = ax[1, 2]
    fx = np.array([r["f"] for r in rows_ok]) * 1e-6; pw = np.array([r["power"] for r in rows_ok]) * 1e3
    a.plot(fx, pw, "o", ms=3, color="steelblue", alpha=0.7)
    a.set_xlabel("f (MHz)"); a.set_ylabel("power (mW)"); a.grid(alpha=0.3)
    h, l = ax[0, 0].get_legend_handles_labels()
    if h:
        ax[0, 0].legend(dict(zip(l, h)).values(), dict(zip(l, h)).keys(), fontsize=8)
    fig.suptitle(title)
    plt.tight_layout(); plt.savefig(path, dpi=130); plt.close()


def _mc_tuning_figure(path, F, x, labs, nom_f, title, xlabel):
    """F: samples x control matrix [Hz]. One thin curve per simulated 'die'."""
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    for row in F:
        ax[0, 0].plot(x, row / 1e6, color="steelblue", alpha=0.15, lw=0.8)
    mu = np.nanmean(F, axis=0); sd = np.nanstd(F, axis=0, ddof=1)
    ax[0, 0].fill_between(x, (mu - 3 * sd) / 1e6, (mu + 3 * sd) / 1e6, color="gold", alpha=0.25, label="mean +- 3 sigma")
    ax[0, 0].plot(x, mu / 1e6, "k-", lw=1.5, label="mean")
    ax[0, 0].plot(x, np.array(nom_f) / 1e6, "--", color="darkorange", lw=1.5, label="nominal")
    ax[0, 0].set_ylabel("frequency (MHz)"); ax[0, 0].legend(fontsize=8)
    ax[0, 1].plot(x, 100 * sd / mu, "o-", color="purple"); ax[0, 1].set_ylabel("sigma(f) / mean (%)")
    kv = []
    for row in F:
        ok = np.isfinite(row)
        if ok.sum() >= 2:
            kv.append(np.polyfit(x[ok], row[ok], 1)[0] / 1e6)
    if len(kv) > 1:
        ax[1, 0].hist(kv, bins=max(5, int(math.sqrt(len(kv)))), color="seagreen", alpha=0.75)
    ax[1, 0].set_xlabel("Kvco per die (MHz per axis unit)"); ax[1, 0].set_ylabel("dies")
    data = [F[:, j][np.isfinite(F[:, j])] / 1e6 for j in range(F.shape[1])]
    if all(len(d) for d in data):
        ax[1, 1].boxplot(data)                                  # tick labels set below: works in old and new matplotlib
        ax[1, 1].set_xticks(range(1, len(labs) + 1)); ax[1, 1].set_xticklabels(labs)
    ax[1, 1].set_ylabel("frequency (MHz)"); ax[1, 1].set_xlabel(xlabel)
    for a in (ax[0, 0], ax[0, 1]):
        a.set_xlabel(xlabel)
    for a in ax.flat:
        a.grid(alpha=0.3)
    fig.suptitle(title)
    plt.tight_layout(); plt.savefig(path, dpi=130); plt.close()


def mc_command(args, cfg):
    t_all = time.time()
    with open(args.netlist) as fh:
        text = fh.read()
    subs = [tuple(s.split("=", 1)) for s in args.path_sub]
    have_ctrl = any([args.line_prefix, args.template, args.values])
    if have_ctrl and not all([args.line_prefix, args.template, args.values]):
        sys.exit("Error: --line-prefix, --template and --values go together (or give none of them to run the netlist as it is).")
    line_re = re.compile(rf"(?im)^\s*{re.escape(args.line_prefix)}\s+.*$") if have_ctrl else None
    vals = [(parse_spice_number(v), v) for v in args.values] if have_ctrl else [(0.0, "-")]
    try:
        corners = expand_corners(args.corners, args.corner)
        specs = [parse_spec(s) for s in args.spec]
    except ValueError as e:
        sys.exit(f"Error: {e}")
    cases = [(c, os.path.join(args.outdir, c["label"])) for c in corners] or [(None, args.outdir)]
    clabel = lambda c: c["label"] if c else "nominal"
    modes_req = ["global", "mismatch", "both"] if args.mc_mode == "split" else [args.mc_mode]
    # which modes are possible in each case (global/both only around typical)
    base_proc = None
    mt = _LIB_RE.search(text)
    if mt:
        base_proc = _SECTION_ALIAS.get(mt.group(2).lower())
    case_modes = {}
    for c, _ in cases:
        proc = c["proc"] if c else base_proc
        ok_modes = [m for m in modes_req if not (_MC_SW[m][0] and proc != "typical")]
        if not ok_modes:
            sys.exit(f"Error: --mc-mode {args.mc_mode} needs global variation, which only exists around the typical corner, "
                     f"but '{clabel(c)}' uses '{proc}'. Use --mc-mode mismatch (or split) for ss/ff/fs/sf.")
        if len(ok_modes) < len(modes_req):
            print(f"NOTE: {clabel(c)}: modes {sorted(set(modes_req) - set(ok_modes))} skipped (global variation only exists "
                  f"around typical); only {ok_modes} will run.", flush=True)
        case_modes[clabel(c)] = ok_modes
    try:                                         # fail early if the netlist cannot take what is requested
        for c, _ in cases:
            t = apply_corner(text, c) if c else text
            for m in case_modes[clabel(c)]:
                apply_mc(t, m, args.mc_skew, 1)
    except RuntimeError as e:
        sys.exit(f"Error: {e}")
    N = args.mc_n
    rng = np.random.default_rng(np.random.SeedSequence(args.mc_seed))
    seeds = [int(s) for s in rng.integers(1, 2 ** 31 - 1, size=N)]       # the same seeds in every case/mode/control value
    omp_wait = omp_policy(args)
    ncpu = os.cpu_count() or 1
    tasks = []
    for c, odir in cases:
        for num, lab in vals:
            tasks.append((c, odir, num, lab, "nominal", 0, None))
            for m in case_modes[clabel(c)]:
                for i, sd in enumerate(seeds):
                    tasks.append((c, odir, num, lab, m, i, sd))
    n_tot = len(tasks)
    print(f"Monte Carlo: {len(cases)} case(s) x {len(vals)} control value(s) x modes {sorted({m for v in case_modes.values() for m in v})}"
          f" x {N} sample(s) (+ nominal runs) = {n_tot} run(s), {args.jobs} job(s).", flush=True)
    print(f"ngspice: {args.threads if args.threads else 'default'} thread(s) per run, OMP_WAIT_POLICY={omp_wait or 'untouched'}, "
          f"timeout {args.timeout:g} s, {ncpu} CPU(s) visible. Seeds: master {args.mc_seed}, skew {args.mc_skew:g}.", flush=True)
    if args.jobs * max(args.threads, 1) > ncpu:
        print(f"  NOTE: jobs x threads = {args.jobs * max(args.threads, 1)} exceeds the {ncpu} visible CPU(s).", flush=True)
    lock, state = threading.Lock(), dict(done=0, fail=0)
    step = max(1, n_tot // 20)
    results = []

    def job(t):
        c, odir, num, lab, mode, i, sd = t
        row = dict(corner=clabel(c), mode=mode, ctrl=num, lab=lab, run=i, seed=(sd if sd is not None else 0), ok=0, error="",
                   **{k: float("nan") for k in _ROW_KEYS})
        try:
            tag = f"v_{lab}" if mode == "nominal" else f"v_{lab}_s{i:05d}"
            raw = run_one(text, line_re, args.template, lab, os.path.join(odir, mode, "runs"), tag, subs, args.ngspice,
                          corner=c, threads=args.threads, omp_wait=omp_wait, timeout=args.timeout,
                          mc=None if mode == "nominal" else dict(mode=mode, skew=args.mc_skew, seed=sd))
            ccfg = dict(cfg)
            if c and not cfg.get("vsupply"):
                ccfg["vdd"] = c["vdd"]
            r, _ = characterize(raw, ccfg, outdir=None, plots=False)
            row.update(row_from_result(r))
            row["ok"] = int(math.isfinite(row["f"]))
            if not row["ok"]:
                row["error"] = "no oscillation measured"
            else:
                vref = abs(ccfg.get("vdd") or 0) or 1.0
                if not (row["amp"] >= args.min_amp * vref):
                    row["ok"] = 0
                    row["error"] = f"dead/non-oscillating (amp {row['amp']:.3g} V < {args.min_amp:g} x VDD)"
            if not args.keep_raw:
                try:
                    os.remove(raw)
                except OSError:
                    pass
        except Exception as e:                      # one failed sample must not stop the study
            row["error"] = str(e.args[0] if e.args else e)[:160]
        with lock:
            state["done"] += 1
            state["fail"] += 0 if row["ok"] else 1
            if not row["ok"]:
                print(f"  FAILED {row['corner']} | {mode} | {lab} | sample {i}: {row['error']}", file=sys.stderr, flush=True)
            if state["done"] % step == 0 or state["done"] == n_tot:
                el = time.time() - t_all
                print(f"  [{state['done']}/{n_tot}] elapsed {fmt_time(el)} | ETA {fmt_time(el / state['done'] * (n_tot - state['done']))}"
                      f" | failed so far: {state['fail']}", flush=True)
        results.append(row)
        return row

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        list(ex.map(job, tasks))
    print(f"Simulations + analysis finished in {fmt_time(time.time() - t_all)}: "
          f"{n_tot - state['fail']}/{n_tot} succeeded.", flush=True)
    if state["fail"] == n_tot:
        sys.exit("Error: nothing succeeded; check the .log files under " + args.outdir)

    # ---------------- statistics ----------------
    os.makedirs(args.outdir, exist_ok=True)
    cs = args.ctrl_scale
    col = ["corner", "mode", "ctrl", "run", "seed", "ok"] + _ROW_KEYS + ["error"]
    results.sort(key=lambda r: (r["corner"], r["mode"] != "nominal", r["mode"], r["ctrl"], r["run"]))
    with open(os.path.join(args.outdir, "mc_samples.csv"), "w") as fh:
        fh.write(",".join(col) + "\n")
        for r in results:
            fh.write(",".join(("%.8g" % (r[k] / cs) if k == "ctrl" else
                               "%s" % r[k] if k in ("corner", "mode", "run", "seed", "ok") else
                               '"%s"' % r[k].replace('"', "'") if k == "error" else "%.8g" % r[k]) for k in col) + "\n")
    rep = []

    def Rp(s=""):
        rep.append(s)
    nom = {(r["corner"], r["lab"]): r for r in results if r["mode"] == "nominal"}
    groups = {}
    for r in results:
        if r["mode"] != "nominal":
            groups.setdefault((r["corner"], r["mode"], r["lab"]), []).append(r)
    summ_rows, stat_cache = [], {}
    n_hist, max_hist = 0, 30
    print("\n" + "=" * 78 + "\nMONTE CARLO SUMMARY (sigma relative to the mean; +- is the standard error of sigma)\n" + "=" * 78, flush=True)
    for c, odir in cases:
        cl = clabel(c)
        Rp("=" * 78); Rp(f"CASE {cl}"); Rp("=" * 78)
        for m in case_modes[cl]:
            for num, lab in vals:
                g = groups.get((cl, m, lab), [])
                okr = [r for r in g if r["ok"]]
                nm = nom.get((cl, lab))
                Rp(f"\n[{m}] control = {num / cs:g}   samples ok: {len(okr)}/{len(g)}")
                Rp(f"{'metric':>10} {'nominal':>11} {'mean':>11} {'sigma':>10} {'sig/mean %':>11} {'+-':>7} {'min':>11} {'p5':>11} {'p95':>11} {'max':>11}")
                for k, nme, unit, sc in MC_METRICS:
                    st = mc_stats([r[k] for r in okr])
                    stat_cache[(cl, m, lab, k)] = st
                    if st is None:
                        continue
                    nv = (nm[k] * sc) if nm and math.isfinite(nm[k]) else float("nan")
                    Rp(f"{nme + ' (' + unit + ')':>10} {nv:>11.5g} {st['mean'] * sc:>11.5g} {st['std'] * sc:>10.4g} "
                       f"{st['rel']:>11.3f} {(100 * st['se'] / abs(st['mean']) if st['mean'] else float('nan')):>7.3f} "
                       f"{st['mn'] * sc:>11.5g} {st['p5'] * sc:>11.5g} {st['p95'] * sc:>11.5g} {st['mx'] * sc:>11.5g}")
                    summ_rows.append(dict(corner=cl, mode=m, ctrl=num / cs, metric=k, n=st["n"], n_total=len(g),
                                          nominal=(nm[k] if nm else float("nan")), **{q: st[q] for q in
                                          ("mean", "std", "rel", "se", "mn", "p5", "p50", "p95", "mx")}))
                yl = mc_yield(g, specs)
                if yl:
                    Rp("yield (all samples, failures count): joint %.1f %%   per spec: %s" % (
                        100 * yl[0], ", ".join("%s %.1f %%" % (s[0], 100 * p) for s, p in zip(specs, yl[1]))))
                fs = stat_cache.get((cl, m, lab, "f"))
                if fs:
                    nf = (nm["f"] / 1e6) if nm else float("nan")
                    print("  %-16s | %-8s | %-6s: nominal %7.2f MHz | mean %7.2f, sigma %6.2f MHz (%.2f %% +- %.2f %%) | %d/%d ok%s" % (
                        cl, m, lab if have_ctrl else "-", nf, fs["mean"] / 1e6, fs["std"] / 1e6, fs["rel"],
                        100 * fs["se"] / abs(fs["mean"]) if fs["mean"] else float("nan"), len(okr), len(g),
                        (" | yield %.0f %%" % (100 * yl[0])) if yl else ""), flush=True)
                if not args.no_mc_plots and len(okr) >= 2 and n_hist < max_hist:
                    n_hist += 1
                    sfx = "" if len(vals) == 1 else f"_{lab}"
                    _mc_hist_figure(os.path.join(odir, m, f"mc_hist{sfx}.png"), okr,
                                    {k: nm[k] for k in _ROW_KEYS} if nm else None, specs,
                                    f"Monte Carlo {m}: {cl}" + (f", control {lab}" if have_ctrl else ""))
    if n_hist >= max_hist and not args.no_mc_plots:
        print(f"NOTE: histogram figures limited to the first {max_hist} groups (see mc_summary.csv for the rest).", flush=True)

    # ---------------- per-die tuning curves (needs >= 2 control values) ----------------
    die = {}                                     # (corner, mode) -> dict(F, x, fmin, fmax, kvco)
    if have_ctrl and len(vals) >= 2:
        xs = np.array([v[0] for v in vals]) / cs
        order = np.argsort(xs)
        xs = xs[order]
        labs = [vals[j][1] for j in order]
        for c, odir in cases:
            cl = clabel(c)
            for m in case_modes[cl]:
                F = np.full((N, len(vals)), np.nan)
                for jj, j in enumerate(order):
                    for r in groups.get((cl, m, vals[j][1]), []):
                        if r["ok"]:
                            F[r["run"], jj] = r["f"]
                nomf = [nom[(cl, labs[jj])]["f"] if (cl, labs[jj]) in nom else np.nan for jj in range(len(vals))]
                kv = np.array([np.polyfit(xs[np.isfinite(row)], row[np.isfinite(row)], 1)[0] if np.isfinite(row).sum() >= 2
                               else np.nan for row in F])
                fmin, fmax = F[:, 0], F[:, -1]
                die[(cl, m)] = dict(F=F, x=xs, fmin=fmin, fmax=fmax, kvco=kv)
                Rp(f"\n[{cl} | {m}] per-die tuning ({np.isfinite(F).all(axis=1).sum()}/{N} dies with every point valid)")
                for nme, v, sc in (("f at lowest control (MHz)", fmin, 1e-6), ("f at highest control (MHz)", fmax, 1e-6),
                                   ("Kvco per die (MHz/unit)", kv, 1e-6)):
                    st = mc_stats(v)
                    if st:
                        Rp(f"  {nme:>28}: mean {st['mean'] * sc:.4g}  sigma {st['std'] * sc:.3g}  p5 {st['p5'] * sc:.4g}  p95 {st['p95'] * sc:.4g}")
                if not args.no_mc_plots and np.isfinite(F).any():
                    _mc_tuning_figure(os.path.join(odir, m, "mc_tuning.png"), F, xs, labs, nomf,
                                      f"Monte Carlo {m}: {cl} - tuning curve of every simulated die", args.ctrl_label)

    # ---------------- split: contribution of each source ----------------
    split_rows = []
    if args.mc_mode == "split":
        Rp("\n" + "=" * 78 + "\nSPLIT: contribution of global process variation and mismatch (variances)\n" + "=" * 78)
        print("\nSPLIT (sigma of each source; share of the variance)", flush=True)
        for c, odir in cases:
            cl = clabel(c)
            if not {"global", "mismatch", "both"} <= set(case_modes[cl]):
                Rp(f"{cl}: only {case_modes[cl]} available (global variation needs the typical corner)")
                continue
            for num, lab in vals:
                for k, nme, unit, sc in MC_METRICS[:5]:
                    sg, sm, sb = (stat_cache.get((cl, m, lab, k)) for m in ("global", "mismatch", "both"))
                    if not (sg and sm and sb and sg["std"] == sg["std"] and sm["std"] == sm["std"]):
                        continue
                    vg, vm = sg["std"] ** 2, sm["std"] ** 2
                    tot = vg + vm
                    line = (f"{cl:>16} {lab:>6} {nme:>8}: sigma global {sg['std'] * sc:.4g}, mismatch {sm['std'] * sc:.4g}, "
                            f"both {sb['std'] * sc:.4g} {unit} | variance share: global {100 * vg / tot:.0f} %, mismatch {100 * vm / tot:.0f} % "
                            f"| both^2/(g^2+m^2) = {sb['std'] ** 2 / tot:.2f}")
                    Rp(line)
                    split_rows.append(dict(corner=cl, ctrl=num / cs, metric=k, sigma_global=sg["std"], sigma_mismatch=sm["std"],
                                           sigma_both=sb["std"], share_global_pct=100 * vg / tot, share_mismatch_pct=100 * vm / tot,
                                           both_over_sum=sb["std"] ** 2 / tot))
                    if k == "f":
                        print("  " + line, flush=True)
            if not args.no_mc_plots and len(vals) >= 1:
                fig, ax = plt.subplots(2, 2, figsize=(12, 8))
                xs_ = [v[0] / cs for v in vals]
                for a, (k, nme, unit, sc) in zip(ax.flat, [MC_METRICS[0], MC_METRICS[1], MC_METRICS[2], MC_METRICS[4]]):
                    for m, colr in (("global", "royalblue"), ("mismatch", "firebrick"), ("both", "black")):
                        y = [(stat_cache.get((cl, m, lab, k)) or {}).get("rel" if k != "thd" else "std", np.nan) for _, lab in vals]
                        a.plot(xs_, y, "o-", color=colr, label=m)
                    a.set_ylabel("sigma / mean (%)" if k != "thd" else "sigma (dB)"); a.set_title(nme); a.grid(alpha=0.3)
                    a.set_xlabel(args.ctrl_label)
                ax[0, 0].legend(fontsize=8)
                fig.suptitle(f"Variation by source: {cl}")
                plt.tight_layout(); plt.savefig(os.path.join(odir, "mc_split.png"), dpi=130); plt.close()
        if split_rows:
            with open(os.path.join(args.outdir, "mc_split.csv"), "w") as fh:
                ks = list(split_rows[0])
                fh.write(",".join(ks) + "\n")
                for r in split_rows:
                    fh.write(",".join(str(r[k]) if isinstance(r[k], str) else "%.8g" % r[k] for k in ks) + "\n")

    # ---------------- comparison across corners ----------------
    if len(cases) >= 2:
        allm = [set(case_modes[clabel(c)]) for c, _ in cases]
        pm = "both" if all("both" in s for s in allm) else ("mismatch" if all("mismatch" in s for s in allm) else sorted(set.intersection(*allm))[0])
        Rp("\n" + "=" * 78 + f"\nCOMPARISON ACROSS CORNERS (mode {pm})\n" + "=" * 78)
        print(f"\nCOMPARISON ACROSS CORNERS (mode {pm}): mean +- 3 sigma of f", flush=True)
        fig, ax = plt.subplots(1, 2, figsize=(14, 5.5))
        many = len(cases) > 6
        for c, _ in cases:
            cl = clabel(c)
            xs_, mu_, sd_, nm_ = [], [], [], []
            for num, lab in vals:
                st = stat_cache.get((cl, pm, lab, "f"))
                if st:
                    xs_.append(num / cs); mu_.append(st["mean"]); sd_.append(st["std"])
                    nm_.append(nom[(cl, lab)]["f"] if (cl, lab) in nom else np.nan)
            if not xs_:
                continue
            xs_, mu_, sd_, nm_ = map(np.array, (xs_, mu_, sd_, nm_))
            cc = _case_color(c["proc"]) if c else "gray"
            ax[0].errorbar(xs_, mu_ / 1e6, yerr=3 * sd_ / 1e6, fmt="o-", ms=3, capsize=3, color=cc, alpha=0.8 if not many else 0.45,
                           label=cl if not many else None)
            ax[0].plot(xs_, nm_ / 1e6, "--", color=cc, lw=0.8, alpha=0.6)
            ax[1].plot(xs_, 100 * sd_ / mu_, "o-", ms=3, color=cc, alpha=0.8 if not many else 0.45, label=cl if not many else None)
            for (x_, mu1, sd1, lab) in zip(xs_, mu_, sd_, [l for _, l in vals]):
                Rp(f"{cl:>16} control {x_:g}: mean {mu1 / 1e6:.2f} MHz, sigma {sd1 / 1e6:.2f} MHz ({100 * sd1 / mu1:.2f} %), "
                   f"-3s {(mu1 - 3 * sd1) / 1e6:.2f}, +3s {(mu1 + 3 * sd1) / 1e6:.2f} MHz")
        ax[0].set_ylabel("frequency (MHz)  [dashed: nominal; bars: +-3 sigma]"); ax[1].set_ylabel("sigma(f) / mean (%)")
        for a in ax:
            a.set_xlabel(args.ctrl_label); a.grid(alpha=0.3)
        if not many:
            ax[0].legend(fontsize=8)
        fig.suptitle(f"Monte Carlo ({pm}) across corners")
        plt.tight_layout(); plt.savefig(os.path.join(args.outdir, "mc_corners.png"), dpi=130); plt.close()
        if die and all((clabel(c), pm) in die for c, _ in cases):
            lo = max(np.nanpercentile(die[(clabel(c), pm)]["fmin"], 95) for c, _ in cases)
            hi = min(np.nanpercentile(die[(clabel(c), pm)]["fmax"], 5) for c, _ in cases)
            msg = (f"Frequency range covered by (about) 90 % of the dies in ALL corners: {lo / 1e6:.1f} .. {hi / 1e6:.1f} MHz "
                   f"(p95 of f at the lowest control .. p5 of f at the highest control)" if lo < hi else
                   f"No frequency is covered by 90 % of the dies in all corners with this control range "
                   f"(p95 of f at lowest control = {lo / 1e6:.1f} MHz > p5 of f at highest control = {hi / 1e6:.1f} MHz)")
            print("\n" + msg, flush=True)
            Rp("\n" + msg)
    with open(os.path.join(args.outdir, "mc_summary.csv"), "w") as fh:
        if summ_rows:
            ks = list(summ_rows[0])
            fh.write(",".join(ks) + "\n")
            for r in summ_rows:
                fh.write(",".join(str(r[k]) if isinstance(r[k], (str, int)) else "%.8g" % r[k] for k in ks) + "\n")
    with open(os.path.join(args.outdir, "mc_report.txt"), "w") as fh:
        fh.write("\n".join(rep) + "\n")
    print(f"\nSaved: {args.outdir}/mc_report.txt, mc_summary.csv, mc_samples.csv" +
          (", mc_split.csv" if split_rows else "") + " and figures (mc_hist*.png, mc_tuning.png, mc_split.png, mc_corners.png) "
          f"in the case/mode folders.", flush=True)


def _exec_args(p, default_outdir):
    """Options shared by 'sweep' and 'mc' (control label/scale, paths, corners, parallel execution)."""
    p.add_argument("--ctrl-label", default="ctrl")
    p.add_argument("--ctrl-scale", type=float, default=1.0, help="Divides the control value for display (1e-6 -> uA)")
    p.add_argument("--path-sub", action="append", default=[], metavar="OLD=NEW",
                   help="Substitute text in the netlist (e.g. PDK paths); repeatable")
    pc = p.add_argument_group("PVT corners (optional; each corner repeats everything)")
    pc.add_argument("--corner", action="append", default=[], metavar="NAME:TEMP:VDD",
                    help="Corner, e.g. ss:125:3.0 (NAME in typical/tt/ff/ss/fs/sf); repeatable")
    pc.add_argument("--corners", action="append", default=[], metavar="PRESET",
                    help="Corner preset: " + ", ".join(PRESETS) + "; repeatable")
    p.add_argument("--jobs", type=int, default=1,
                   help="Simulations run in parallel (default 1; raise it only if your machine copes)")
    p.add_argument("--threads", type=int, default=1,
                   help="num_threads forced inside each ngspice .control (default 1: processes scale better "
                        "than threads); 0 = leave ngspice as configured")
    p.add_argument("--omp-wait", choices=["auto", "passive", "active", "none"], default="auto",
                   help="OMP_WAIT_POLICY for ngspice. auto (default): untouched in serial; with --jobs>1 passive only if "
                        "--threads 0 or jobs*threads exceeds the CPUs; none: never touch it")
    p.add_argument("--timeout", type=float, default=300.0,
                   help="Seconds allowed per ngspice run (default 300; 0 = no limit). A stuck run is marked FAILED")
    p.add_argument("--ngspice", default="ngspice")
    p.add_argument("--outdir", default=default_outdir)


# ======================================================================
# CLI
# ======================================================================

# ----------------------------------------------------------------------
# JSON configuration files (--config / --save-config)
# ----------------------------------------------------------------------

_PATH_KEYS = ("netlist", "raw_path")          # plus the file part of each 'run' entry


def _read_json(path):
    """JSON with whole-line '//' comments allowed."""
    with open(path) as fh:
        txt = "\n".join(l for l in fh.read().split("\n") if not l.lstrip().startswith("//"))
    try:
        return json.loads(txt)
    except ValueError as e:
        raise ValueError(f"{path}: invalid JSON ({e})")


def load_config_file(path, _depth=0):
    """Loads a config, resolving 'extends' (parent first, child overrides) and turning the input-file paths
    into absolute paths relative to the folder of the file that defines them."""
    if _depth > 8:
        raise ValueError("'extends' is nested too deeply (cycle?)")
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ValueError(f"config file not found: {path}")
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: the top level must be a JSON object")
    base = os.path.dirname(path)
    out = {}
    parents = raw.get("extends") or []
    for parent in ([parents] if isinstance(parents, str) else parents):
        out.update(load_config_file(os.path.join(base, parent), _depth + 1))
    own = {k.replace("-", "_"): v for k, v in raw.items() if k != "extends" and not k.startswith("_")}
    for k in _PATH_KEYS:
        if isinstance(own.get(k), str) and not os.path.isabs(own[k]):
            own[k] = os.path.normpath(os.path.join(base, own[k]))
    if "run" in own:
        runs = [own["run"]] if isinstance(own["run"], str) else list(own["run"])
        fixed = []
        for r in runs:
            v, _, f = str(r).partition(":")
            fixed.append(f"{v}:{f if os.path.isabs(f) else os.path.normpath(os.path.join(base, f))}")
        own["run"] = fixed
    out.update(own)
    return out


def _coerce(action, key, val):
    """Converts a JSON value to what argparse would have produced for this option."""
    if isinstance(action, argparse._StoreTrueAction):
        return bool(val)
    multi = isinstance(action, argparse._AppendAction) or action.nargs in ("+", "*")
    if key == "path_sub" and isinstance(val, dict):
        val = [f"{a}={b}" for a, b in val.items()]
    conv = action.type or str
    try:
        if multi:
            items = val if isinstance(val, list) else [val]
            return [str(i) for i in items] if action.type is None else [action.type(i) for i in items]
        out = conv(val) if (action.type and val is not None) else val
    except (TypeError, ValueError):
        raise ValueError(f"invalid value for '{key}': {val!r}")
    if action.choices and out not in action.choices:
        raise ValueError(f"'{key}' must be one of {list(action.choices)} (got {out!r})")
    return out


def config_to_json(ns, real_def, dest_file=None):
    """Effective options that differ from the defaults, ready to dump. Input paths are written relative to the
    JSON file (dest_file) or absolute when there is none."""
    def pth(f):
        return os.path.relpath(os.path.abspath(f), os.path.dirname(os.path.abspath(dest_file))) if dest_file \
            else os.path.abspath(f)
    out = {"command": ns["cmd"]}
    for k, v in ns.items():
        if k in ("cmd", "config", "save_config") or v is None or v == real_def.get(k):
            continue
        if k in _PATH_KEYS:
            v = pth(v)
        elif k == "run":
            v = [f"{r.partition(':')[0]}:{pth(r.partition(':')[2])}" for r in v]
        out[k] = v
    return out


def write_json(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


def build_cfg(a):
    return default_config(
        signal=a.signal, pos=a.pos, neg=a.neg, single_ended=a.single_ended,
        probe=a.probe or [], vdd=a.vdd, vsupply=a.vsupply,
        isupply=a.isupply, icore=a.icore, freq=a.freq, threshold=a.threshold, t_start=a.t_start,
        amp_tol=a.amp_tol, freq_tol=a.freq_tol, ui_window=a.ui_window, oversample=a.oversample,
        nharm=a.nharm, ppp=a.ppp, window=a.window, noisy=a.noisy,
        phase_ref=a.phase_ref, phase_sigs=a.phase_sig or [], phase_expected=a.phase_expected or [],
        min_ppp=a.min_ppp, min_cycles=a.min_cycles, target_cycles=a.target_cycles)


def main():
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("signals")
    g.add_argument("--signal", help="Differential trace already computed in the netlist, e.g. v(n13)")
    g.add_argument("--pos", help="Positive node (without --signal, diff = pos - neg; also enables common mode)")
    g.add_argument("--neg", help="Negative node")
    g.add_argument("--single-ended", action="store_true",
                   help="The analyzed --signal is single-ended (e.g. a ring oscillator node): "
                        "uses single-ended labels and skips differential-only quantities")
    g.add_argument("--probe", action="append", help="Extra node to report (mean and ripple); repeatable, e.g. v(vcs)")
    g.add_argument("--vdd", type=float, help="VDD (V), to compute power")
    g.add_argument("--vsupply", help="VDD trace (if you do not give --vdd), e.g. v(vdd)")
    g.add_argument("--isupply", help="TOTAL supply-source current, e.g. i(v7)")
    g.add_argument("--icore", help="CORE current (without reference branches), e.g. i(v1)")
    g.add_argument("--freq", type=float, help="Expected frequency (Hz), only to report the deviation")
    g.add_argument("--threshold", type=float, help="Crossing threshold (default: signal mid-level)")
    g.add_argument("--t-start", type=float, help="Steady-state start (s); default: auto")
    g.add_argument("--amp-tol", type=float, default=0.02, help="Amplitude settling tolerance (0.02)")
    g.add_argument("--freq-tol", type=float, default=0.005, help="Period settling tolerance (0.005)")
    g.add_argument("--ui-window", type=float, default=2.0, help="Eye window width in periods (2)")
    g.add_argument("--oversample", type=int, default=200, help="Eye points per period (200)")
    g.add_argument("--nharm", type=int, default=9, help="Harmonics to report (9)")
    g.add_argument("--ppp", type=int, default=256, help="FFT points per period (256)")
    g.add_argument("--window", choices=["rect", "hann"], default="rect", help="FFT window (rect = coherent)")
    g.add_argument("--noisy", action="store_true", help="The simulation includes transient noise (drops the numerical-jitter note)")
    gp = common.add_argument_group("phase between outputs")
    gp.add_argument("--phase-ref", help="Reference signal for the phase, e.g. v(n13) or v(n1)-v(n3)")
    gp.add_argument("--phase-sig", action="append", help="Signal whose phase is measured vs. the reference; repeatable")
    gp.add_argument("--phase-expected", type=float, action="append",
                    help="Expected phase (deg) for each --phase-sig, in the same order; repeatable")
    gf = common.add_argument_group("configuration file")
    gf.add_argument("--config", metavar="FILE.json",
                    help="Read the options from a JSON file (keys = option names; command-line options override it)")
    gf.add_argument("--save-config", metavar="FILE.json",
                    help="Write the effective options to a JSON file and exit (does not simulate)")
    gc = common.add_argument_group("simulation adequacy checks")
    gc.add_argument("--min-ppp", type=int, default=20, help="Minimum points per period, worst case (20)")
    gc.add_argument("--min-cycles", type=int, default=10, help="Minimum steady-state cycles (10)")
    gc.add_argument("--target-cycles", type=int, default=50, help="Steady-state cycles to suggest in .tran (50)")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    pa = sub.add_parser("analyze", parents=[common], help="Characterize one .raw file")
    pa.add_argument("raw_path", nargs="?", help="Simulation .raw file")
    pa.add_argument("--outdir", default="osc_analysis")
    pt = sub.add_parser("tuning", parents=[common], help="Tuning curve from several .raw files")
    pt.add_argument("--run", action="append", metavar="VALUE:file.raw",
                    help="One point of the curve (repeatable), e.g. 500u:run1.raw")
    pt.add_argument("--ctrl-label", default="ctrl")
    pt.add_argument("--ctrl-scale", type=float, default=1.0, help="Divides the control value for display (1e-6 -> uA)")
    pt.add_argument("--outdir", default="osc_tuning")
    ps = sub.add_parser("sweep", parents=[common], help="Run ngspice varying one netlist line and build the curve")
    ps.add_argument("--netlist")
    ps.add_argument("--line-prefix", help="Name of the element to replace, e.g. I0")
    ps.add_argument("--template", help="New line containing {v}, e.g. \"I0 VBP 0 {v}\"")
    ps.add_argument("--values", nargs="+", help="Values (SPICE suffixes: 300u 1.2 ...)")
    _exec_args(ps, "osc_sweep")
    ps.add_argument("--target-f", type=str, default=None,
                    help="Frequency (SPICE suffixes, e.g. 600meg): reports the control value needed in each corner")
    ps.add_argument("--verbose", action="store_true",
                    help="With corners: print the full analysis of every corner on screen "
                         "(by default it is saved in <corner>/analysis.log and only one line per corner is shown)")

    pm = sub.add_parser("mc", parents=[common], help="Monte Carlo (global process variation and/or mismatch), "
                        "at one or several control values and corners")
    pm.add_argument("--netlist")
    pm.add_argument("--line-prefix", help="Control element to replace (optional: without it the netlist runs as it is)")
    pm.add_argument("--template", help="New line containing {v}, e.g. \"I0 VBP 0 {v}\"")
    pm.add_argument("--values", nargs="+", help="Control values; one = MC at one operating point, several = a tuning curve per die")
    _exec_args(pm, "osc_mc")
    gm = pm.add_argument_group("Monte Carlo")
    gm.add_argument("--mc-n", type=int, default=100, help="Samples per case/mode/control value (default 100)")
    gm.add_argument("--mc-seed", type=int, default=1, help="Master seed; the same seeds are used in every case (default 1)")
    gm.add_argument("--mc-mode", choices=["both", "global", "mismatch", "split"], default="both",
                    help="both = global process + mismatch (typical only); global = process only (typical only); mismatch = "
                         "mismatch only, on ANY corner; split = runs global, mismatch and both to separate the contributions")
    gm.add_argument("--mc-skew", type=float, default=3.0, help="PDK mc_skew / res_mc_skew / cap_mc_skew (default 3)")
    gm.add_argument("--spec", action="append", default=[], metavar="METRIC:MIN:MAX",
                    help="Specification for the yield, e.g. f:550meg:650meg (empty side = no limit); repeatable")
    gm.add_argument("--keep-raw", action="store_true", help="Keep every .raw (by default they are deleted after the analysis)")
    gm.add_argument("--min-amp", type=float, default=0.05,
                    help="MC validity: a sample whose amplitude is below this fraction of VDD counts as a failure (default 0.05)")
    gm.add_argument("--no-mc-plots", action="store_true", help="Do not draw the Monte Carlo figures")

    cmds = {"analyze": pa, "tuning": pt, "sweep": ps, "mc": pm}
    argv = sys.argv[1:]
    cfg_file = next((argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--config"), None)
    if cfg_file is None:
        cfg_file = next((a.split("=", 1)[1] for a in argv if a.startswith("--config=")), None)
    jcfg = {}
    if cfg_file:
        try:
            jcfg = load_config_file(cfg_file)
        except ValueError as e:
            sys.exit(f"Error: {e}")
    if argv and argv[0] not in tuple(cmds) + ("-h", "--help"):
        if jcfg.get("command") in cmds and argv[0].startswith("--"):
            argv = [jcfg["command"]] + argv
        else:
            argv = ["analyze"] + argv
    elif not argv:
        ap.print_help(); sys.exit(1)
    cmd = argv[0] if argv[0] in cmds else None
    if cmd is None:
        ap.parse_args(argv)                     # -h/--help prints and exits
        ap.print_help(); sys.exit(1)
    sp = cmds[cmd]
    acts = {a.dest: a for a in sp._actions if a.dest != "help"}
    real_def = {k: a.default for k, a in acts.items()}
    for a in acts.values():                     # only options really typed on the command line will appear
        a.default = argparse.SUPPRESS
    explicit = vars(ap.parse_args(argv))
    explicit.pop("cmd", None)
    merged = dict(real_def)
    try:
        for k, v in jcfg.items():
            if k == "command":
                continue
            if k not in acts:
                import difflib
                close = difflib.get_close_matches(k, list(acts), n=2)
                raise ValueError(f"unknown key '{k}' in {cfg_file} for '{cmd}'" + (f" (did you mean {close}?)" if close else ""))
            merged[k] = _coerce(acts[k], k, v)
    except ValueError as e:
        sys.exit(f"Error: {e}")
    merged.update(explicit)                     # command line wins over the JSON
    merged["cmd"] = cmd
    need = {"analyze": ["raw_path"], "tuning": ["run"], "sweep": ["netlist", "line_prefix", "template", "values"],
            "mc": ["netlist"]}[cmd]
    miss = [k for k in need if not merged.get(k)]
    if miss:
        sys.exit("Error: missing " + ", ".join("--" + k.replace("_", "-") for k in miss) +
                 " (give them on the command line or in the --config file)")
    if merged.get("save_config"):
        write_json(merged["save_config"], config_to_json(merged, real_def, merged["save_config"]))
        print(f"Saved configuration to {merged['save_config']}\nRun it with: python3 {os.path.basename(sys.argv[0])} --config {merged['save_config']}")
        return
    args = argparse.Namespace(**merged)
    used_cfg = config_to_json(merged, real_def)

    def record_config(outdir):
        write_json(os.path.join(outdir, "config_used.json"), used_cfg)

    cfg = build_cfg(args)

    if args.cmd == "analyze":
        if not os.path.isfile(args.raw_path):
            sys.exit(f"Error: '{args.raw_path}' not found")
        record_config(args.outdir)
        try:
            res, rep = characterize(args.raw_path, cfg, outdir=args.outdir)
        except (RuntimeError, KeyError, ValueError) as e:
            sys.exit(f"Error: {e.args[0] if e.args else e}")
        print(rep)
        print(f"Summary: {args.outdir}/osc_summary.txt   Metrics: {args.outdir}/osc_metrics.json")

    elif args.cmd == "tuning":
        record_config(args.outdir)
        entries = []
        for r in args.run:
            v, _, p = r.partition(":")
            entries.append((parse_spice_number(v), p))
        tuning_analysis(entries, cfg, args.outdir, args.ctrl_label, args.ctrl_scale)

    elif args.cmd == "mc":
        if not os.path.isfile(args.netlist):
            sys.exit(f"Error: '{args.netlist}' not found")
        record_config(args.outdir)
        mc_command(args, cfg)

    elif args.cmd == "sweep":
        with open(args.netlist) as fh:
            text = fh.read()
        line_re = re.compile(rf"(?im)^\s*{re.escape(args.line_prefix)}\s+.*$")
        subs = [tuple(s.split("=", 1)) for s in args.path_sub]
        try:
            corners = expand_corners(args.corners, args.corner)
            target_f = parse_spice_number(args.target_f) if args.target_f else None
            for c in corners:                       # fail early if the netlist cannot take the corner
                apply_corner(text, c)
        except (ValueError, RuntimeError) as e:
            sys.exit(f"Error: {e.args[0] if e.args else e}")
        vals = [(parse_spice_number(v), v) for v in args.values]
        record_config(args.outdir)
        # no corners -> one "case" without rewriting (previous behaviour, flat output folder)
        cases = [(c, os.path.join(args.outdir, c["label"])) for c in corners] or [(None, args.outdir)]

        n_tot, lock, state = len(vals) * len(cases), threading.Lock(), dict(done=0)
        t_sw = time.time()
        names = ("nominal netlist" if not corners else
                 ", ".join(c["label"] for c, _ in cases) if len(cases) <= 6 else f"{len(cases)} corners")
        print(f"Sweep: {len(vals)} point(s) of '{args.line_prefix}' x {len(cases)} case(s) [{names}] = {n_tot} run(s), "
              f"{args.jobs} job(s) in parallel. Output in {args.outdir}/", flush=True)

        ncpu = os.cpu_count() or 1
        if args.omp_wait == "auto":
            omp_wait = "passive" if (args.jobs > 1 and (args.threads == 0 or args.jobs * args.threads > ncpu)) else None
        else:
            omp_wait = None if args.omp_wait == "none" else args.omp_wait
        print(f"ngspice: {args.threads if args.threads else 'default'} thread(s) per run, OMP_WAIT_POLICY="
              f"{omp_wait or 'untouched'}, timeout {args.timeout:g} s, {ncpu} CPU(s) visible.", flush=True)
        rounds = -(-n_tot // args.jobs)
        best = [j for j in range(1, min(ncpu, n_tot) + 1) if -(-n_tot // j) == -(-n_tot // min(ncpu, n_tot))]
        if args.jobs * max(args.threads, 1) > ncpu:
            print(f"  NOTE: jobs x threads = {args.jobs * max(args.threads, 1)} exceeds the {ncpu} visible CPU(s) (oversubscribed).", flush=True)
        if args.jobs > 1 and n_tot > 1:
            need = -(-n_tot // rounds)
            if need < args.jobs:
                print(f"  NOTE: {n_tot} runs with {args.jobs} jobs = {rounds} round(s); {need} job(s) give the same {rounds} round(s).", flush=True)
        elif args.jobs == 1 and n_tot > 1 and ncpu > 1:
            print(f"  TIP: --jobs {min(best)} would run the {n_tot} runs in {-(-n_tot // min(best))} round(s) instead of {n_tot} "
                  f"(only with --threads 1 and if your machine has that many free cores).", flush=True)

        def job(item):
            (corner, odir), (num, lab) = item
            who = f"{corner['label']} | {lab}" if corner else lab
            with lock:
                print(f"  -> running ngspice for {who} ...", flush=True)
            t0 = time.time()
            try:
                raw = run_one(text, line_re, args.template, lab, os.path.join(odir, "runs"), f"v_{lab}", subs,
                              args.ngspice, corner=corner, threads=args.threads, omp_wait=omp_wait,
                              timeout=args.timeout)
                err = None
            except Exception as e:                      # one failed point must not abort the sweep
                raw, err = None, e
            with lock:
                state["done"] += 1
                el = time.time() - t_sw
                eta = el / state["done"] * (n_tot - state["done"])
                status = f"simulated in {fmt_time(time.time() - t0)}" if raw else f"FAILED -> {err}"
                print(f"  [{state['done']}/{n_tot}] {who}: {status} | elapsed {fmt_time(el)} | "
                      f"ETA {fmt_time(eta)}", flush=True)
            return corner, num, raw

        items = [(case, v) for case in cases for v in vals]
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(job, items))
        n_ok = sum(1 for _, _, r in results if r)
        print(f"Simulations finished in {fmt_time(time.time() - t_sw)}: {n_ok}/{n_tot} succeeded.", flush=True)
        if n_ok == 0:
            sys.exit("Error: no simulation succeeded; check the .log files under " + args.outdir)

        all_rows = []
        quiet = bool(corners) and not args.verbose
        if quiet:
            print(f"\nAnalyzing {len(cases)} corner(s); the detail of each goes to <corner>/analysis.log "
                  f"(use --verbose to print it here).", flush=True)
        for i_case, (corner, odir) in enumerate(cases, start=1):
            entries = [(n, r) for c, n, r in results if r and (c is None or c["label"] == corner["label"])]
            if not entries:
                print(f"\n[{corner['label'] if corner else 'nominal'}] no successful simulation; skipped.", file=sys.stderr)
                continue
            ccfg = dict(cfg)
            ttl = "Oscillator tuning curve"
            if corner:
                if not cfg.get("vsupply"):             # power must use the VDD of THIS corner
                    ccfg["vdd"] = corner["vdd"]
                ttl += f" - {corner['proc']}, {corner['temp']:g} C, VDD = {corner['vdd']:g} V"
            if quiet:
                os.makedirs(odir, exist_ok=True)
                logp = os.path.join(odir, "analysis.log")
                t_c = time.time()
                with open(logp, "w") as lf, contextlib.redirect_stdout(lf):
                    print("#" * 78 + f"\n# CORNER {corner['label']}\n" + "#" * 78, flush=True)
                    rows = tuning_analysis(entries, ccfg, odir, args.ctrl_label, args.ctrl_scale, title=ttl)
                ff = np.array([r["f"] for r in rows])
                nw = sum(max(r["nwarn"], 0) for r in rows)
                nfail = sum(1 for r in rows if not r["ok"])
                el = time.time() - t_sw
                print(f"  [{i_case}/{len(cases)}] {corner['label']}: f = {np.nanmin(ff)/1e6:.1f}..{np.nanmax(ff)/1e6:.1f} MHz, "
                      f"{nw} warning(s)" + (f", {nfail} failed point(s)" if nfail else "") +
                      f" | {fmt_time(time.time() - t_c)} | elapsed {fmt_time(el)}", flush=True)
            else:
                if corner:
                    print("\n" + "#" * 78 + f"\n# CORNER {corner['label']}\n" + "#" * 78, flush=True)
                rows = tuning_analysis(entries, ccfg, odir, args.ctrl_label, args.ctrl_scale, title=ttl)
            all_rows.append((corner, rows))
        if corners:
            corners_comparison(all_rows, args.outdir, args.ctrl_label, args.ctrl_scale, target_f=target_f)


if __name__ == "__main__":
    main()
