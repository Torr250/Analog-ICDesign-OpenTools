#!/usr/bin/env python3
"""
pll_characterization.py - Time-domain characterization of a PLL from ngspice transient simulations.

Self-contained (it does NOT import osc_characterization.py). The small helpers for reading the .raw,
finding crossings and fitting a line were adapted from osc_characterization.py; `selftest` checks that
they still agree with it on the example oscillator .raw.

Subcommands
  analyze   characterize ONE .raw (ref, fb, clk, vctrl)
  run       simulate one or several CASES (PVT corner + its own parameter values) and analyze each one
  selftest  regression check of the helpers against the osc_characterization example (597.29 MHz)

Sign convention of the phase error: positive = fb LAGS ref (fb edge arrives after the ref edge).
"""
import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from prettytable import PrettyTable, TableStyle

try:
    from spicelib.raw.raw_read import RawRead
except Exception:                                   # pragma: no cover
    RawRead = None

try:
    from scipy.signal import find_peaks
except Exception:                                   # pragma: no cover
    find_peaks = None

PRESETS = {
    "worst3": ["ss:125:3.0", "typical:60:3.3", "ff:-40:3.6"],
    "process5": ["typical:60:3.3", "ff:60:3.3", "ss:60:3.3", "fs:60:3.3", "sf:60:3.3"],
    "temp3": ["typical:-40:3.3", "typical:27:3.3", "typical:125:3.3"],
    "vdd3": ["typical:27:3.0", "typical:27:3.3", "typical:27:3.6"],
}
DEFAULT_TOLS = [5e-3, 1e-3, 1e-4, 1e-5]


# ======================================================================
# Basic utilities (adapted from osc_characterization.py)
# ======================================================================

def load_traces(raw_path, names):
    """Read traces from an ngspice .raw. Returns (time, {name: wave}) with strictly increasing time."""
    if RawRead is None:
        raise RuntimeError("spicelib is not installed:  pip install spicelib --break-system-packages")
    raw = RawRead(raw_path, dialect="ngspice")
    avail = raw.get_trace_names()
    t = np.abs(np.asarray(raw.get_trace("time").get_wave(), dtype=float))
    keep = np.concatenate(([True], np.diff(t) > 0))
    out = {}
    for n in names:
        try:
            out[n] = np.asarray(raw.get_trace(n).get_wave(), dtype=float)[keep]
        except Exception:
            raise KeyError(f"Trace '{n}' not found in {raw_path}. Available: {', '.join(sorted(avail))}")
    return t[keep], out


def find_crossings(t, v, thr, rising=True):
    """Times where v crosses thr (linear interpolation)."""
    a, b = v[:-1], v[1:]
    idx = np.where((a < thr) & (b >= thr))[0] if rising else np.where((a > thr) & (b <= thr))[0]
    return t[idx] + (thr - v[idx]) * (t[idx + 1] - t[idx]) / (v[idx + 1] - v[idx])


def linear_fit(times):
    """Fit t_k = t0 + k*T. Returns (t0, T, tie) where tie = t_k - fit."""
    k = np.arange(len(times))
    T, t0 = np.polyfit(k, times, 1)
    return t0, T, times - (t0 + k * T)


def mid_level(v):
    lo, hi = np.percentile(v, [1, 99])
    return 0.5 * (lo + hi)


def parse_spice_number(s):
    if isinstance(s, (int, float)):
        return float(s)
    m = re.fullmatch(r"\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(meg|[tgkmunpf])?\w*\s*", str(s).lower())
    if not m:
        raise ValueError(f"cannot parse number '{s}'")
    mult = {None: 1, "t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
    return float(m.group(1)) * mult[m.group(2)]


def fmt_time(s):
    if s is None or not np.isfinite(s):
        return "not locked"
    a = abs(s)
    if a >= 1e-6:
        return f"{s * 1e6:.3f} us"
    if a >= 1e-9:
        return f"{s * 1e9:.3f} ns"
    return f"{s * 1e12:.2f} ps"


def tol_label(tol):
    return f"{tol * 100:g} %" if tol >= 1e-3 else f"{tol * 1e6:g} ppm"


# ======================================================================
# PLL metrics
# ======================================================================

def freq_series(edges, n=1):
    """Frequency averaged over n periods, stamped at the closing edge."""
    if len(edges) <= n:
        return np.array([]), np.array([])
    return edges[n:], n / (edges[n:] - edges[:-n])


def last_exit(tm, f, f0, tol):
    """Lock time = first sample after the LAST one outside |f/f0-1| <= tol. nan if never/not at the end."""
    if len(tm) == 0:
        return float("nan")
    bad = np.abs(f / f0 - 1.0) > tol
    if not bad.any():
        return float(tm[0])
    k = np.where(bad)[0][-1]
    return float(tm[k + 1]) if k + 1 < len(tm) else float("nan")


def phase_error(t_ref, t_fb, T_ref):
    """Signed error of the nearest fb edge for every ref edge, wrapped to +-T/2. Positive = fb lags."""
    if len(t_fb) == 0:
        return np.array([]), np.array([])
    j = np.clip(np.searchsorted(t_fb, t_ref), 1, len(t_fb) - 1)
    d1, d0 = t_fb[j] - t_ref, t_fb[j - 1] - t_ref
    e = np.where(np.abs(d0) < np.abs(d1), d0, d1)
    e = (e + T_ref / 2) % T_ref - T_ref / 2
    return t_ref, e


def ringing(tm, dev, noise):
    """Damping estimate from two successive positive peaks of the frequency deviation (None if not possible)."""
    if find_peaks is None or len(dev) < 5:
        return None
    prom = max(10 * noise, 5e-5)
    pk, _ = find_peaks(dev, prominence=prom)
    if len(pk) < 2:
        return None
    a1, a2 = dev[pk[0]], dev[pk[1]]
    if a1 <= 0 or a2 <= 0 or a2 >= a1:
        return None
    delta = math.log(a1 / a2)
    return {"zeta": delta / math.sqrt(4 * math.pi ** 2 + delta ** 2),
            "t_ring": float(tm[pk[1]] - tm[pk[0]]), "f_ring": float(1.0 / (tm[pk[1]] - tm[pk[0]])),
            "peak1": float(a1), "peak2": float(a2)}


def clock_quality(t, clk, vc, wc, tcf, n_div, fref, cfg):
    """Jitter, eye, spectrum and reference spurs of clk in the (locked) final window.
    wc = rising crossings of clk inside the window, tcf = ALL falling crossings of clk."""
    from scipy.interpolate import CubicSpline
    out, warn = {}, []
    P_ui, P_spec, P_ref = 100, 64, 640
    nharm = int(cfg.get("nharm", 11))
    thr = mid_level(clk)
    t0r, T, tie_r = linear_fit(wc)
    f_clk = 1.0 / T
    n = len(wc)

    # ---- edges: next falling edge after every rising edge
    wf = tcf[(tcf >= wc[0]) & (tcf <= wc[-1] + T)]
    j = np.searchsorted(wf, wc)
    ok = j < len(wf)
    kk = np.where(ok)[0]
    tf_ok = wf[j[ok]]
    r_ph = tie_r / T                                  # rising crossing phase error (UI)
    f_ph = (tf_ok - (t0r + kk * T)) / T               # falling crossing phase (UI), ~duty
    duty = f_ph - r_ph[kk]
    tie_f = (f_ph - np.mean(f_ph)) * T
    per = np.diff(wc)

    # ---- jitter
    out["jitter"] = {
        "tie_rms_rise": float(np.std(tie_r)), "tie_pp_rise": float(np.ptp(tie_r)),
        "tie_rms_fall": float(np.std(tie_f)), "tie_pp_fall": float(np.ptp(tie_f)),
        "period_mean": float(np.mean(per)), "period_rms": float(np.std(per)), "period_pp": float(np.ptp(per)),
        "c2c_rms": float(np.std(np.diff(per))), "c2c_pp": float(np.ptp(np.diff(per))),
        "duty_mean": float(np.mean(duty)), "duty_pp": float(np.ptp(duty)), "edges": int(n)}

    # ---- eye (folded on the ideal grid, 2 UI, rising edge at x = 0 and 1)
    x = np.linspace(-0.5, 1.5, 2 * P_ui, endpoint=False)
    ncyc = n - 3
    if ncyc < 3:
        warn.append("too few clk cycles in the window for the eye diagram")
        eye = None
    else:
        k = np.arange(1, ncyc + 1)
        tt = t0r + (k[:, None] + x[None, :]) * T
        E = np.interp(tt, t, clk)
        hi = float(np.median(clk[clk > thr])); lo = float(np.median(clk[clk <= thr]))
        A = hi - lo
        dm = float(np.mean(duty))
        bh = (x > dm / 2 - 0.1) & (x < dm / 2 + 0.1)
        bl = (x > dm + (1 - dm) / 2 - 0.1) & (x < dm + (1 - dm) / 2 + 0.1)
        height = float(E[:, bh].min() - E[:, bl].max())
        # horizontal opening at mid level: all cycles high/low at the same phase window
        high_w = (np.min(f_ph) - np.max(r_ph[kk])) * T
        both = ok[:-1] & ok[1:]
        kb = np.where(both)[0]
        low_w = float(np.min(1.0 + r_ph[kb + 1] - f_ph[np.searchsorted(kk, kb)]) * T) if len(kb) else float("nan")
        m = E.mean(axis=0)
        def edge_t(level, seg, rising):
            xs, ms = x[seg], m[seg]
            if not rising:
                xs, ms = xs[::-1], ms[::-1]
            return float(np.interp(level, ms, xs))
        seg_r = (x > -0.3) & (x < 0.3)
        seg_f = (x > dm - 0.3) & (x < dm + 0.3)
        try:
            tr_ = (edge_t(lo + 0.9 * A, seg_r, True) - edge_t(lo + 0.1 * A, seg_r, True)) * T
            tf_ = (edge_t(lo + 0.1 * A, seg_f, False) - edge_t(lo + 0.9 * A, seg_f, False)) * T
        except Exception:
            tr_ = tf_ = float("nan")
        out["eye"] = {"v_high": hi, "v_low": lo, "amplitude": A, "height": height,
                      "width_high": float(high_w), "width_low": low_w,
                      "width_high_ui": float(high_w / T), "width_low_ui": float(low_w / T) if low_w == low_w else None,
                      "t_rise_10_90": float(tr_), "t_fall_90_10": float(tf_),
                      "slew_rise": float(0.8 * A / tr_) if tr_ and tr_ > 0 else None}
        step = max(1, ncyc // 150)
        eye = {"x": x, "E": E[::step]}

    # ---- spectrum of clk (coherent: integer clk cycles AND integer ref periods, rectangular window)
    K = (n - 1) // n_div * n_div
    spec = None
    if K < 2 * n_div:
        warn.append("fewer than 2 ref periods in the window: no spectrum")
    else:
        ts, Ns = wc[0], K * P_spec
        dt = T / P_spec
        a, b = np.searchsorted(t, ts) - 3, np.searchsorted(t, ts + Ns * dt) + 3
        a, b = max(a, 0), min(b, len(t))
        xs = CubicSpline(t[a:b], clk[a:b])(ts + dt * np.arange(Ns))
        X = np.abs(np.fft.rfft(xs)) / Ns * 2.0
        dbc = lambda i: float(20 * np.log10(max(X[i], 1e-18) / X[K]))
        harm = {str(h): dbc(h * K) for h in range(2, nharm + 1) if h * K < len(X)}
        thd = float(np.sqrt(sum((X[h * K] / X[K]) ** 2 for h in range(2, nharm + 1) if h * K < len(X))))
        step_b = K // n_div
        sb = {}
        for mm in (1, 2, 3):
            lo_i, hi_i = K - mm * step_b, K + mm * step_b
            sb[str(mm)] = {"lower_dbc": dbc(lo_i), "upper_dbc": dbc(hi_i)}
        out["spectrum"] = {"fundamental_Vpk": float(X[K]), "dc": float(X[0] / 2), "harmonics_dbc": harm,
                           "thd_pct": thd * 100, "sidebands_dbc": sb, "window_cycles": int(K),
                           "resolution_Hz": float(f_clk / K), "nyquist_harm": int(P_spec // 2 - 1)}
        fr = np.arange(len(X)) * f_clk / K
        spec = {"f": fr, "dbc": 20 * np.log10(np.maximum(X, 1e-18) / X[K])}

        # ---- spectrum of vctrl over the same integer number of ref periods (reference spurs)
        Kr = K // n_div
        Nr = Kr * P_ref
        dtr = n_div * T / P_ref
        vs = np.interp(ts + dtr * np.arange(Nr), t, vc)
        V = np.abs(np.fft.rfft(vs)) / Nr * 2.0
        amps = {m_: float(V[m_ * Kr]) for m_ in range(1, 6) if m_ * Kr < len(V)}
        vsp = {"dc": float(V[0] / 2), "ripple_pp": float(np.ptp(vs)), "amp_fref_harm": {str(k_): v_ for k_, v_ in amps.items()}}
        kv = cfg.get("kvco")
        if kv:
            kvf = parse_spice_number(kv)
            beta = kvf * amps[1] / fref
            vsp["kvco"] = kvf
            vsp["spur_pred_dbc"] = float(20 * np.log10(beta / 2)) if beta > 0 else None
            vsp["spur_meas_dbc"] = float(max(sb["1"]["lower_dbc"], sb["1"]["upper_dbc"]))
        out["vctrl_spectrum"] = vsp
        out["_vspec"] = {"m": np.arange(1, 6), "amp": np.array([amps.get(m_, np.nan) for m_ in range(1, 6)])}
    out["warnings"] = warn
    out["_eye"], out["_spec"] = eye, spec
    out["_tie"] = {"rise": tie_r, "fall": tie_f, "t_rise": wc, "t_fall": tf_ok}
    return out


def analyze_pll(raw_path, cfg, label=None):
    """Characterize one .raw. cfg keys: clk ref fb vctrl fref n_div vdd isupply final_frac t_final tols phase_tol."""
    want = [cfg["clk"], cfg["ref"], cfg["fb"], cfg["vctrl"]] + ([cfg["isupply"]] if cfg.get("isupply") else [])
    t, tr = load_traces(raw_path, want)
    clk, ref, fb, vc = (tr[cfg[k]] for k in ("clk", "ref", "fb", "vctrl"))
    res = {"raw": os.path.basename(raw_path), "label": label, "warnings": []}
    tend = float(t[-1])
    res["sim"] = {"t_stop": tend, "points": int(len(t)), "dt_median": float(np.median(np.diff(t)))}

    tc = find_crossings(t, clk, mid_level(clk))
    tf = find_crossings(t, fb, mid_level(fb))
    tref = find_crossings(t, ref, mid_level(ref))
    if min(len(tc), len(tf), len(tref)) < 10:
        raise RuntimeError("too few edges in clk/fb/ref: is the simulation long enough?")

    t_fin = cfg.get("t_final")
    if t_fin is None:
        t_fin = tend * (1.0 - cfg.get("final_frac", 0.2))
    wc, wf, wr = tc[tc >= t_fin], tf[tf >= t_fin], tref[tref >= t_fin]
    if min(len(wc), len(wf), len(wr)) < 5:
        raise RuntimeError("final window has too few edges; lower final_frac / t_final")

    # ---- targets
    _, Tc_fit, tie = linear_fit(wc)
    _, Tf_fit, _ = linear_fit(wf)
    _, Tr_fit, _ = linear_fit(wr)
    f_clk, f_fb, f_ref = 1 / Tc_fit, 1 / Tf_fit, 1 / Tr_fit
    fref = parse_spice_number(cfg["fref"]) if cfg.get("fref") else f_ref
    n_div = int(cfg["n_div"]) if cfg.get("n_div") else int(round(f_clk / fref))
    f_target = n_div * fref
    Tref = 1.0 / fref
    res["target"] = {"fref": fref, "n_div": n_div, "f_target": f_target,
                     "fref_measured": f_ref}
    res["final"] = {"window_start": float(t_fin), "f_clk": f_clk, "f_fb": f_fb,
                    "err_ppm_clk": (f_clk / f_target - 1) * 1e6, "err_ppm_fb": (f_fb / fref - 1) * 1e6,
                    "cycles": int(len(wc))}

    # ---- frequency vs time
    tm1, f1 = freq_series(tc, 1)
    tmN, fN = freq_series(tc, n_div)
    tmf, ff = freq_series(tf, 1)
    dev_fb = ff / fref - 1.0
    in_win = tmf >= t_fin
    noise_fb = float(np.std(dev_fb[in_win])) if in_win.sum() > 2 else 1e-6
    res["final"]["fb_ripple_ppm_pp"] = float(np.ptp(dev_fb[in_win]) * 1e6) if in_win.any() else None
    res["final"]["clk1_ripple_ppm_pp"] = float(np.ptp(f1[tm1 >= t_fin] / f_target) * 1e6)
    res["final"]["clkN_ripple_ppm_pp"] = float(np.ptp(fN[tmN >= t_fin] / f_target) * 1e6)

    # ---- lock time (frequency criteria)
    tols = [parse_spice_number(x) if isinstance(x, str) else float(x) for x in cfg.get("tols", DEFAULT_TOLS)]
    lock = []
    for tol in tols:
        row = {"tol": tol, "label": tol_label(tol),
               "fb": last_exit(tmf, ff, fref, tol),
               "clk_N": last_exit(tmN, fN, f_target, tol),
               "clk_1": last_exit(tm1, f1, f_target, tol)}
        lock.append(row)
    res["lock_freq"] = lock
    noise_pp = max(res["final"]["fb_ripple_ppm_pp"] or 0.0, 0.0) * 1e-6
    for row in lock:
        if row["fb"] == row["fb"] and row["tol"] < noise_pp:
            res["warnings"].append(f"tolerance {row['label']} is below the steady-state fb ripple "
                                   f"({noise_pp * 1e6:.1f} ppm pp): that lock time is not reliable")

    # ---- overshoot / ringing (from the fb frequency). The first fb intervals (divider start-up from its
    # initial state) are skipped: they are not a settled period. skip_ref = number of ref periods ignored.
    skip_t = cfg.get("skip_ref", 2) * (1.0 / fref)
    ms = tmf >= skip_t
    tms, dms = tmf[ms], dev_fb[ms]
    pk = int(np.argmax(dms))
    after = tms > tms[pk]
    if after.sum() > 1:
        kk = int(np.argmin(np.where(after, dms, np.inf)))
        under, t_under = float(min(dms[kk], 0) * 100), float(tms[kk])
    else:
        under, t_under = 0.0, float("nan")
    res["transient"] = {
        "skip_s": skip_t, "initial_err_pct": float(dms[0] * 100),
        "f_fb_overshoot_pct": float(max(dms[pk], 0) * 100), "t_overshoot": float(tms[pk]),
        "f_fb_undershoot_after_peak_pct": under, "t_undershoot": t_under,
        "ringing": ringing(tms, dms, noise_fb),
    }

    # ---- phase error ref -> fb
    tpe, pe = phase_error(tref, tf, Tref)
    in_pw = tpe >= t_fin
    pe_static = float(np.median(pe[in_pw]))
    ph_tol = float(cfg.get("phase_tol", 0.005)) * Tref
    bad = np.abs(pe - pe_static) > ph_tol
    t_ph = float("nan") if (bad.any() and np.where(bad)[0][-1] + 1 >= len(tpe)) else \
        float(tpe[np.where(bad)[0][-1] + 1] if bad.any() else tpe[0])
    res["phase"] = {"static_s": pe_static, "static_deg": pe_static / Tref * 360.0,
                    "ripple_pp_s": float(np.ptp(pe[in_pw])), "rms_s": float(np.std(pe[in_pw])),
                    "tol_s": ph_tol, "lock_time": t_ph}

    # ---- vctrl
    vw = (t >= t_fin)
    res["vctrl"] = {"final_mean": float(vc[vw].mean()), "ripple_pp": float(np.ptp(vc[vw])),
                    "min": float(vc.min()), "max": float(vc.max()),
                    "peak_to_final": float(vc.max() - vc[vw].mean())}

    # ---- jitter of clk in the final window (numerical only if the simulation has no noise)
    per = np.diff(wc)
    res["jitter_clk"] = {"tie_rms": float(np.std(tie)), "tie_pp": float(np.ptp(tie)),
                         "period_rms": float(np.std(per)), "c2c_rms": float(np.std(np.diff(per)))}

    # ---- clock quality in the locked window: jitter, eye, spectrum, reference spurs
    if cfg.get("clock_quality", True):
        try:
            tcf = find_crossings(t, clk, mid_level(clk), rising=False)
            cq = clock_quality(t, clk, vc, wc, tcf, n_div, fref, cfg)
            res["warnings"] += cq.pop("warnings")
            res["_clock_plot"] = {k_: cq.pop(k_) for k_ in [k2 for k2 in list(cq) if k2.startswith("_")]}
            res["clock"] = cq
        except Exception as e:                       # never lose the main analysis for this
            res["warnings"].append(f"clock-quality analysis failed: {e}")

    # ---- power
    if cfg.get("isupply") and cfg.get("vdd"):
        i = tr[cfg["isupply"]]
        a, b = wr[0], wr[-1]
        m = (t >= a) & (t <= b)
        iavg = float(np.trapezoid(i[m], t[m]) / (t[m][-1] - t[m][0])) if hasattr(np, "trapezoid") else \
            float(np.trapz(i[m], t[m]) / (t[m][-1] - t[m][0]))
        res["power"] = {"i_mean_abs": abs(iavg), "p_mean": abs(iavg) * float(cfg["vdd"]), "vdd": float(cfg["vdd"])}

    # ---- warnings
    ppp = Tc_fit / res["sim"]["dt_median"]
    if ppp < 20:
        res["warnings"].append(f"only {ppp:.0f} points per clk period: increase the resolution of .tran")
    t_l0 = res["lock_freq"][0]["fb"]
    if t_l0 == t_l0 and t_fin < t_l0:
        res["warnings"].append("the final window starts before the first lock time: lower final_frac or simulate longer")
    if abs(res["final"]["err_ppm_fb"]) > 1000:
        res["warnings"].append("final frequency differs more than 1000 ppm from n_div*fref: the PLL may not be locked")

    # arrays for plotting (not serialized)
    res["_series"] = {"tmf": tmf, "dev_fb": dev_fb, "tmN": tmN, "devN": fN / f_target - 1.0,
                      "tpe": tpe, "pe": pe, "t": t, "vctrl": vc,
                      "isup": tr.get(cfg.get("isupply")) if cfg.get("isupply") else None}
    return res


# ======================================================================
# Report and plots
# ======================================================================

def mk_table(headers, rows, left=(0,), title=None):
    """Console/report table (prettytable, single-line borders). Columns in `left` are left-aligned."""
    t = PrettyTable(list(headers))
    t.set_style(TableStyle.SINGLE_BORDER)
    t.align = "r"
    for i in left:
        t.align[headers[i]] = "l"
    for row in rows:
        t.add_row(list(row))
    if title:
        t.title = title
    return t.get_string()


def summary_table(r, title=None):
    """Key figures of one analysis as Metric | Value | Unit."""
    f, tr, ph, vc = r["final"], r["transient"], r["phase"], r["vctrl"]
    lk = r["lock_freq"]
    rows = [("f_clk", f"{f['f_clk'] / 1e6:.5f}", "MHz"),
            ("Frequency error vs N*fref", f"{f['err_ppm_clk']:+.2f}", "ppm")]
    for row in (lk[0], lk[-1]) if len(lk) > 1 else lk:
        rows.append((f"Lock time, fb, +-{row['label']}", fmt_time(row["fb"]), ""))
    rows += [("Lock time, phase", fmt_time(ph["lock_time"]), ""),
             ("Peak overshoot (f_fb)", f"{tr['f_fb_overshoot_pct']:+.3f}", "%"),
             ("Static phase error", f"{ph['static_s'] * 1e12:+.1f}", "ps"),
             ("vctrl final / ripple", f"{vc['final_mean']:.4f} / {vc['ripple_pp'] * 1e3:.1f}", "V / mVpp")]
    if "clock" in r:
        c = r["clock"]; j = c["jitter"]
        rows.append(("TIE rms (clk)", f"{j['tie_rms_rise'] * 1e12:.3f}", "ps"))
        if "spectrum" in c:
            sb = c["spectrum"]["sidebands_dbc"]["1"]
            rows += [("THD", f"{c['spectrum']['thd_pct']:.1f}", "%"),
                     ("Reference spur (f_clk +- fref)", f"{max(sb['lower_dbc'], sb['upper_dbc']):.1f}", "dBc")]
    if "power" in r:
        rows.append(("Supply power (no VCO)", f"{r['power']['p_mean'] * 1e6:.1f}", "uW"))
    return mk_table(["Metric", "Value", "Unit"], rows, left=(0, 2), title=title)


def report_text(r, title=""):
    L = []
    add = L.append
    f = r["final"]; tg = r["target"]; tr = r["transient"]; ph = r["phase"]; vc = r["vctrl"]
    add("=" * 70); add(f"PLL CHARACTERIZATION {title}"); add("=" * 70)
    add(f"File: {r['raw']}   t_stop = {fmt_time(r['sim']['t_stop'])}   {r['sim']['points']} points")
    for w in r["warnings"]:
        add(f"WARNING  {w}")
    add("")
    add(summary_table(r, title=f"SUMMARY - {r.get('label') or r['raw']}"))
    add("")
    add("1. FREQUENCY (final window, from t = %s)" % fmt_time(f["window_start"]))
    add(f"fref = {tg['fref'] / 1e6:.4f} MHz   N = {tg['n_div']}   target = {tg['f_target'] / 1e6:.4f} MHz")
    add(f"f_clk = {f['f_clk'] / 1e6:.5f} MHz   error = {f['err_ppm_clk']:+.2f} ppm")
    add(f"f_fb  = {f['f_fb'] / 1e6:.6f} MHz   error = {f['err_ppm_fb']:+.2f} ppm")
    add(f"Steady-state ripple of the instantaneous frequency (pp): fb {f['fb_ripple_ppm_pp']:.1f} ppm | "
        f"clk over N cycles {f['clkN_ripple_ppm_pp']:.1f} ppm | clk per cycle {f['clk1_ripple_ppm_pp']:.0f} ppm")
    add("")
    add("2. LOCK TIME (last exit from the band; resolution = one fref period, or one clk period for 'clk 1 cyc')")
    add(mk_table(["Tolerance", "fb (1 ref period)", "clk (N cycles)", "clk (1 cycle)"],
                 [(row["label"], fmt_time(row["fb"]), fmt_time(row["clk_N"]), fmt_time(row["clk_1"]))
                  for row in r["lock_freq"]]))
    add(f"Phase lock (|phase error - static| < {ph['tol_s'] * 1e12:.0f} ps): {fmt_time(ph['lock_time'])}")
    add("")
    add(f"3. TRANSIENT (from the fb frequency; first {fmt_time(tr['skip_s'])} skipped: divider start-up)")
    add(f"Initial error      : {tr['initial_err_pct']:+.2f} %")
    add(f"Peak overshoot     : {tr['f_fb_overshoot_pct']:+.3f} % at {fmt_time(tr['t_overshoot'])}")
    add(f"Undershoot after it: {tr['f_fb_undershoot_after_peak_pct']:+.3f} % at {fmt_time(tr['t_undershoot'])}")
    rg = tr["ringing"]
    if rg:
        add(f"Ringing (two positive peaks, estimate): zeta ~ {rg['zeta']:.2f}   f_ring ~ {rg['f_ring'] / 1e6:.2f} MHz")
    else:
        add("Ringing: fewer than two usable peaks (no damping estimate)")
    add("")
    add("4. PHASE ERROR ref -> fb (positive = fb lags)")
    add(f"Static: {ph['static_s'] * 1e12:+.1f} ps ({ph['static_deg']:+.2f} deg of fref)   "
        f"ripple pp {ph['ripple_pp_s'] * 1e12:.1f} ps   rms {ph['rms_s'] * 1e12:.2f} ps")
    add("")
    add("5. CONTROL VOLTAGE")
    add(f"Final {vc['final_mean']:.4f} V   ripple {vc['ripple_pp'] * 1e3:.1f} mVpp   "
        f"range [{vc['min']:.3f}, {vc['max']:.3f}] V   peak above final {vc['peak_to_final'] * 1e3:.0f} mV")
    add("")
    j = r["jitter_clk"]
    add("6. CLK JITTER in the final window (no transient noise: deterministic jitter from the fref ripple + numerical floor)")
    add(f"TIE rms {j['tie_rms'] * 1e12:.3f} ps  pp {j['tie_pp'] * 1e12:.3f} ps   "
        f"period rms {j['period_rms'] * 1e12:.3f} ps   c2c rms {j['c2c_rms'] * 1e12:.3f} ps")
    if "clock" in r:
        c = r["clock"]; j = c["jitter"]
        add("")
        add(f"7. CLOCK QUALITY IN THE LOCKED WINDOW ({j['edges']} clk edges, from {fmt_time(f['window_start'])})")
        add(f"Jitter  rising TIE rms {j['tie_rms_rise'] * 1e12:.3f} ps (pp {j['tie_pp_rise'] * 1e12:.3f})   "
            f"falling TIE rms {j['tie_rms_fall'] * 1e12:.3f} ps (pp {j['tie_pp_fall'] * 1e12:.3f})")
        add(f"        period {j['period_mean'] * 1e12:.2f} ps  rms {j['period_rms'] * 1e12:.3f} ps (pp {j['period_pp'] * 1e12:.3f})   "
            f"c2c rms {j['c2c_rms'] * 1e12:.3f} ps (pp {j['c2c_pp'] * 1e12:.3f})")
        add(f"        duty cycle {j['duty_mean'] * 100:.4f} %  (pp {j['duty_pp'] * 100:.4f} %)")
        add("        (a noiseless simulation shows only the deterministic part: periodic with fref, it matches the reference spur)")
        if "eye" in c:
            e = c["eye"]
            add(f"Eye     amplitude {e['amplitude']:.4f} V (high {e['v_high']:.4f} / low {e['v_low']:.4f})   "
                f"height {e['height']:.4f} V")
            add(f"        width at mid-level: high {e['width_high'] * 1e12:.1f} ps ({e['width_high_ui']:.4f} UI)   "
                f"low {e['width_low'] * 1e12:.1f} ps")
            add(f"        10-90 % rise {e['t_rise_10_90'] * 1e12:.1f} ps   90-10 % fall {e['t_fall_90_10'] * 1e12:.1f} ps")
        if "spectrum" in c:
            sp = c["spectrum"]
            add(f"Spectrum (coherent, {sp['window_cycles']} clk cycles, resolution {sp['resolution_Hz'] / 1e6:.2f} MHz, "
                f"no window): fundamental {sp['fundamental_Vpk']:.4f} Vpk, DC {sp['dc']:.4f} V, THD {sp['thd_pct']:.1f} %")
            hs = sp["harmonics_dbc"]
            add(mk_table([f"H{h}" for h in hs], [[f"{v:.1f}" for v in hs.values()]], left=(), title="Harmonics (dBc)"))
            fr_mhz = r["target"]["fref"] / 1e6
            vam = c.get("vctrl_spectrum", {}).get("amp_fref_harm", {})
            add(mk_table(["m", "Offset (MHz)", "Lower (dBc)", "Upper (dBc)", "vctrl at m*fref (mV)"],
                         [(m_, f"+-{int(m_) * fr_mhz:g}", f"{v['lower_dbc']:.1f}", f"{v['upper_dbc']:.1f}",
                           f"{vam[m_] * 1e3:.3f}" if m_ in vam else "") for m_, v in sp["sidebands_dbc"].items()],
                         left=(), title="Reference spurs at f_clk +- m*fref"))
        if "vctrl_spectrum" in c:
            v = c["vctrl_spectrum"]
            add(f"vctrl   ripple {v['ripple_pp'] * 1e3:.1f} mVpp in the spectrum window (amplitudes at m*fref in the table above)")
            if "spur_pred_dbc" in v and v["spur_pred_dbc"] is not None:
                add(f"        reference spur from the vctrl ripple (Kvco = {v['kvco'] / 1e6:g} MHz/V, narrow-band FM): "
                    f"predicted {v['spur_pred_dbc']:.1f} dBc   measured {v['spur_meas_dbc']:.1f} dBc")
    if "power" in r:
        p = r["power"]
        add("")
        add("8. POWER (supply current i(v7): excludes the behavioral VCO, which has no supply pin)")
        add(f"I = {p['i_mean_abs'] * 1e6:.1f} uA   P = {p['p_mean'] * 1e6:.1f} uW at {p['vdd']} V")
    return "\n".join(L)


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if np.isfinite(v) else None
    if isinstance(o, np.integer):
        return int(o)
    return o


PROC_COLORS = {"ff": "tab:blue", "typical": "tab:green", "tt": "tab:green", "ss": "tab:red",
               "fs": "tab:orange", "sf": "tab:purple"}          # fast = blue, typical = green, slow = red
DEFAULT_COLOR = "tab:blue"


def case_color(case):
    return PROC_COLORS.get(str(case.get("process", "")).lower(), DEFAULT_COLOR)


# matplotlib (pyplot state, mathtext parser) is not thread-safe: cases run in parallel threads,
# so every plotting function holds this lock.
_PLOT_LOCK = threading.RLock()


def _locked(fn):
    def wrapper(*a, **k):
        with _PLOT_LOCK:
            return fn(*a, **k)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


@_locked
def make_plots(r, outdir, name="pll"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = r["_series"]
    col = r.get("_color", DEFAULT_COLOR)
    fig, ax = plt.subplots(4, 1, figsize=(9, 11), sharex=True)
    ax[0].plot(s["tmf"] * 1e6, s["dev_fb"] * 100, ".-", ms=3, lw=0.8, color=col, label="fb (1 ref period)")
    ax[0].plot(s["tmN"] * 1e6, s["devN"] * 100, lw=0.6, alpha=0.5, color=col, ls="--", label="clk (N cycles)")
    ax[0].axhline(0.5, color="gray", ls="--", lw=0.6); ax[0].axhline(-0.5, color="gray", ls="--", lw=0.6)
    ax[0].set_ylabel("f / f_target - 1 (%)"); ax[0].legend(); ax[0].grid(alpha=0.3)
    ax[1].plot(s["t"] * 1e6, s["vctrl"], lw=0.7, color=col); ax[1].set_ylabel("vctrl (V)"); ax[1].grid(alpha=0.3)
    ax[2].plot(s["tpe"] * 1e6, s["pe"] * 1e12, ".-", ms=3, lw=0.8, color=col)
    ax[2].set_ylabel("phase error (ps)"); ax[2].grid(alpha=0.3)
    ax[3].semilogy(s["tmf"] * 1e6, np.maximum(np.abs(s["dev_fb"]), 1e-9), lw=0.8, color=col)
    for row in r["lock_freq"]:
        ax[3].axhline(row["tol"], color="gray", ls=":", lw=0.7)
        ax[3].text(s["tmf"][-1] * 1e6, row["tol"], " " + row["label"], va="bottom", ha="right", fontsize=7)
        if row["fb"] == row["fb"]:
            ax[3].plot([row["fb"] * 1e6], [row["tol"]], "o", ms=4, color="black")
    ax[3].set_ylabel("|f_fb / fref - 1|"); ax[3].set_xlabel("time (us)"); ax[3].grid(alpha=0.3, which="both")
    fig.suptitle(r.get("label") or name); fig.tight_layout()
    path = os.path.join(outdir, f"{name}_overview.png")
    fig.savefig(path, dpi=130); plt.close(fig)
    return path


@_locked
def make_clock_plots(r, outdir, name="pll"):
    """One figure per topic: eye, jitter (histograms like osc_characterization + TIE vs time), spectrum, supply."""
    if "_clock_plot" not in r or "clock" not in r:
        return []
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cp, c = r["_clock_plot"], r["clock"]
    col = r.get("_color", DEFAULT_COLOR)
    label = r.get("label") or name
    paths = []

    # ---- eye
    eye = cp.get("_eye")
    if eye is not None:
        e, j = c["eye"], c["jitter"]
        fig, ax = plt.subplots(figsize=(10, 6))
        for row in eye["E"]:
            ax.plot(eye["x"], row, color=col, alpha=0.15, lw=0.8)
        ax.plot(eye["x"], eye["E"].mean(axis=0), color="navy", lw=1.2, label="mean trace")
        ax.axvline(0, color="green", ls=":", label="rising edge (0 UI)")
        ax.axvline(j["duty_mean"], color="darkorange", ls="--", label=f"falling edge ({j['duty_mean']:.3f} UI)")
        ax.axhline(0.5 * (e["v_high"] + e["v_low"]), color="gray", lw=0.6)
        ax.set_xlabel("time (UI = measured period, 0 = rising edge)"); ax.set_ylabel("clk (V)")
        ax.set_title(f"{label} - eye of clk: T = {j['period_mean'] * 1e12:.1f} ps, amplitude {e['amplitude']:.3f} V, "
                     f"width {e['width_high_ui']:.3f} UI, rise {e['t_rise_10_90'] * 1e12:.0f} ps", fontsize=10)
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
        fig.tight_layout(); p = os.path.join(outdir, f"{name}_eye.png"); fig.savefig(p, dpi=140); plt.close(fig)
        paths.append(p)

    # ---- jitter: histograms (same three as osc_characterization) + TIE vs time
    tie = cp["_tie"]
    per = np.diff(tie["t_rise"]); cc = np.diff(per)
    fig = plt.figure(figsize=(13, 7.5))
    gs = fig.add_gridspec(2, 3)
    for i, (data, ttl, colr) in enumerate(((tie["rise"], "TIE (rising)", "firebrick"),
                                           (per - per.mean(), "period - mean", "darkorange"),
                                           (cc, "cycle-to-cycle", "purple"))):
        a = fig.add_subplot(gs[0, i])
        d = np.asarray(data) * 1e12
        span = max(np.ptp(d), 1e-6)
        a.hist(d, bins=np.linspace(d.min() - 0.3 * span, d.max() + 0.3 * span, 21), color=colr, edgecolor="white")
        a.set_title(f"{ttl}  rms={d.std(ddof=1):.4f} ps", fontsize=10); a.set_xlabel("ps"); a.grid(alpha=0.3)
    a = fig.add_subplot(gs[1, :])
    a.plot(tie["t_rise"] * 1e6, tie["rise"] * 1e12, ".", ms=4, color=col, label="rising TIE")
    a.plot(tie["t_fall"] * 1e6, tie["fall"] * 1e12, ".", ms=3, color="black", alpha=0.5, label="falling TIE")
    a.set_xlabel("time (us)"); a.set_ylabel("TIE (ps)"); a.legend(fontsize=8); a.grid(alpha=0.3)
    fig.suptitle(f"{label} - jitter of clk in the locked window (noise-free simulation: deterministic jitter, "
                 f"periodic with fref; the histograms are not Gaussian)", fontsize=10)
    fig.tight_layout(); p = os.path.join(outdir, f"{name}_jitter.png"); fig.savefig(p, dpi=140); plt.close(fig)
    paths.append(p)

    # ---- spectrum: clk, zoom on the reference spurs, vctrl at m*fref
    sp, vs = cp.get("_spec"), cp.get("_vspec")
    if sp is not None:
        f0 = 1 / np.mean(np.diff(tie["t_rise"]))
        fref = r["target"]["fref"]
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.8))
        m = sp["f"] <= 6 * f0
        ax[0].plot(sp["f"][m] / 1e6, sp["dbc"][m], lw=0.7, color=col)
        ax[0].set_ylim(-110, 5); ax[0].set_xlabel("frequency (MHz)"); ax[0].set_ylabel("dBc")
        ax[0].set_title(f"clk spectrum (THD {c['spectrum']['thd_pct']:.1f} %)", fontsize=10); ax[0].grid(alpha=0.3)
        mz = (sp["f"] > f0 - 3.5 * fref) & (sp["f"] < f0 + 3.5 * fref)
        ax[1].plot(sp["f"][mz] / 1e6, sp["dbc"][mz], ".-", ms=4, lw=0.8, color=col)
        for mm, v in c["spectrum"]["sidebands_dbc"].items():
            for sgn, key in ((-1, "lower_dbc"), (1, "upper_dbc")):
                fx = (f0 + sgn * int(mm) * fref) / 1e6
                ax[1].annotate(f"{v[key]:.1f}", (fx, v[key]), textcoords="offset points", xytext=(0, 6),
                               ha="center", fontsize=8)
        ax[1].set_ylim(-100, 5); ax[1].set_xlabel("frequency (MHz)")
        ax[1].set_title(f"around f_clk: reference spurs at +-m*fref ({fref / 1e6:g} MHz)", fontsize=10)
        ax[1].grid(alpha=0.3)
        if vs is not None:
            ax[2].bar(vs["m"], vs["amp"] * 1e3, color=col)
            v = c["vctrl_spectrum"]
            t2 = f"vctrl at m*fref (ripple {v['ripple_pp'] * 1e3:.0f} mVpp)"
            if v.get("spur_pred_dbc") is not None:
                t2 += f"\nspur: predicted {v['spur_pred_dbc']:.1f} / measured {v['spur_meas_dbc']:.1f} dBc"
            ax[2].set_title(t2, fontsize=10)
            ax[2].set_xlabel("harmonic of fref"); ax[2].set_ylabel("amplitude (mV)"); ax[2].grid(alpha=0.3)
        fig.suptitle(label + " - spectrum in the locked window", fontsize=10)
        fig.tight_layout(); p = os.path.join(outdir, f"{name}_spectrum.png"); fig.savefig(p, dpi=140); plt.close(fig)
        paths.append(p)

    # ---- supply current
    s = r.get("_series", {})
    if s.get("isup") is not None and "power" in r:
        i = s["isup"]
        i = -i if i[s["t"] >= r["final"]["window_start"]].mean() < 0 else i     # current drawn from the supply, positive
        fig, ax = plt.subplots(2, 1, figsize=(10, 7))
        ax[0].plot(s["t"] * 1e6, i * 1e3, lw=0.5, color=col)
        ax[0].axhline(r["power"]["i_mean_abs"] * 1e3, color="black", ls="--", lw=0.8,
                      label=f"mean in the locked window: {r['power']['i_mean_abs'] * 1e3:.2f} mA")
        ax[0].set_xlabel("time (us)"); ax[0].set_ylabel("supply current (mA)"); ax[0].legend(fontsize=8)
        ax[0].grid(alpha=0.3)
        run = s["t"] >= 0.05 * s["t"][-1]                 # scale fitted to the running circuit; the start-up spike is clipped
        lo, hi = float(i[run].min()) * 1e3, float(i[run].max()) * 1e3
        pad = 0.08 * max(hi - lo, 1e-9)
        ax[0].set_ylim(lo - pad, hi + pad)
        ax[0].set_title("scale fitted to the running circuit (the start-up spike at t ~ 0 is clipped)", fontsize=9)
        w = s["t"] >= r["final"]["window_start"]
        w &= s["t"] <= r["final"]["window_start"] + 5 * (1.0 / r["target"]["fref"])
        ax[1].plot(s["t"][w] * 1e9, i[w] * 1e3, lw=0.7, color=col)
        ax[1].axhline(r["power"]["i_mean_abs"] * 1e3, color="black", ls="--", lw=0.8)
        ax[1].set_xlabel("time (ns)"); ax[1].set_ylabel("supply current (mA)")
        ax[1].set_title("zoom: 5 reference periods in the locked window", fontsize=9); ax[1].grid(alpha=0.3)
        fig.suptitle(f"{label} - supply current i(v7), P = {r['power']['p_mean'] * 1e3:.2f} mW at "
                     f"{r['power']['vdd']:g} V (excludes the behavioral VCO)", fontsize=10)
        fig.tight_layout(); p = os.path.join(outdir, f"{name}_supply.png"); fig.savefig(p, dpi=140); plt.close(fig)
        paths.append(p)
    return paths


# ======================================================================
# Netlist handling
# ======================================================================

def parse_corner(spec):
    p = spec.split(":")
    if len(p) != 3:
        raise ValueError(f"corner '{spec}' must be process:temp:vdd")
    proc = {"tt": "typical"}.get(p[0].lower(), p[0].lower())
    return {"process": proc, "temp": float(p[1]), "vdd": float(p[2])}


def case_name(c):
    g = lambda x: f"{x:g}"
    return c.get("name") or f"{c['process']}_{g(c['temp'])}C_{g(c['vdd'])}V"


def edit_line(text, prefix, newline):
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        tok = ln.split()
        if tok and tok[0].lower() == prefix.lower():
            lines[i] = newline
            return "\n".join(lines)
    raise ValueError(f"edit: no line starts with '{prefix}'")


def set_param(text, name, value):
    """Set NAME=value in the first .param line that defines it; otherwise add a new .param line."""
    pat = re.compile(rf"(?<![\w.]){re.escape(name)}\s*=\s*[^\s]+", re.I)
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.lower().lstrip().startswith(".param") and pat.search(ln):
            lines[i] = pat.sub(f"{name}={value}", ln, count=1)
            return "\n".join(lines)
    for i, ln in enumerate(lines):
        if ln.lower().lstrip().startswith(".param"):
            lines.insert(i + 1, f".param {name}={value}")
            return "\n".join(lines)
    raise ValueError("netlist has no .param line")


def apply_case(text, case, path_subs=(), tstop=None, tstep=None, threads=1, rawname="run.raw", save=None):
    for old, new in path_subs:
        text = text.replace(old, new)
    if "process" in case:
        pat = re.compile(r"^(\s*\.lib\s+\S+\s+)(\w+)(\s*)$", re.I | re.M)
        cands = [m for m in pat.finditer(text) if m.group(2).lower() in
                 ("typical", "ff", "ss", "fs", "sf")]
        if not cands:
            raise ValueError("no '.lib <file> <section>' line with a process section (typical/ff/ss/fs/sf)")
        m = cands[0]
        text = text[:m.start(2)] + case["process"] + text[m.end(2):]
    if "temp" in case:
        text = set_param(text, "TEMP", f"{case['temp']:g}")
    if "vdd" in case:
        text = set_param(text, "VDD", f"{case['vdd']:g}")
    for k, v in (case.get("params") or {}).items():
        text = set_param(text, k, v)
    # digital buses: {"DV": "1111110"} -> DV6=1 DV5=1 ... DV0=0 (leftmost character = highest index, like Verilog [6:0]).
    # With "bus_lsb_first": true the leftmost character is bit 0.
    for name, code in (case.get("bus") or {}).items():
        code = str(code)
        if not code or set(code) - {"0", "1"}:
            raise ValueError(f"bus {name}: '{code}' must contain only 0 and 1")
        bits = code if case.get("bus_lsb_first") else code[::-1]
        for i, ch in enumerate(bits):
            text = set_param(text, f"{name}{i}", ch)
    for prefix, newline in (case.get("edits") or {}).items():
        text = edit_line(text, prefix, newline)
    for old, new in case.get("subs") or []:
        if old not in text:
            raise ValueError(f"subs: '{old}' not found in the netlist")
        text = text.replace(old, new)
    if tstop or tstep:
        m = re.search(r"^(\s*tran\s+)(\S+)\s+(\S+)(.*)$", text, re.I | re.M)
        if not m:
            raise ValueError("no 'tran step stop' line in .control")
        text = text[:m.start()] + f"{m.group(1)}{tstep or m.group(2)} {tstop or m.group(3)}{m.group(4)}" + text[m.end():]
    # one write, to our raw name; optional explicit save list
    writes = list(re.finditer(r"^\s*write\s+\S+.*$", text, re.I | re.M))
    if not writes:
        raise ValueError("netlist has no 'write file.raw' line in .control")
    for m in reversed(writes[1:]):
        text = text[:m.start()] + text[m.end():]
    m = re.search(r"^\s*write\s+\S+.*$", text, re.I | re.M)
    text = text[:m.start()] + f"  write {rawname}" + text[m.end():]
    if save:
        text = re.sub(r"^\s*save\s+all\s*$", f"  save {' '.join(save)}", text, flags=re.I | re.M)
    if threads:
        text = re.sub(r"(?im)^(\s*\.control\s*)$", r"\1\n  set num_threads=%d" % threads, text, count=1)
    return text


def missing_includes(text):
    """Absolute paths of .include / .lib lines of the netlist that do not exist (ngspice would stop on them)."""
    out = []
    for m in re.finditer(r"^\s*\.(?:include|inc|lib)\s+(?:'([^']+)'|\"([^\"]+)\"|(\S+))", text, re.I | re.M):
        path = m.group(1) or m.group(2) or m.group(3)
        if path.startswith("/") and not os.path.exists(path):
            out.append(path)
    return out


def run_ngspice(netlist_path, rundir, ngspice, timeout):
    log = os.path.join(rundir, "ngspice.log")
    t0 = time.time()
    try:
        subprocess.run([ngspice, "-b", os.path.basename(netlist_path), "-o", "ngspice.log"], cwd=rundir,
                       timeout=timeout or None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s", time.time() - t0
    return True, log, time.time() - t0


# ======================================================================
# Commands
# ======================================================================

def cfg_from_args(a):
    keys = ["clk", "ref", "fb", "vctrl", "fref", "n_div", "vdd", "isupply", "final_frac", "t_final", "tols", "phase_tol", "skip_ref", "kvco", "nharm", "clock_quality"]
    return {k: getattr(a, k, None) for k in keys if getattr(a, k, None) is not None}


def cmd_analyze(a):
    if not a.raw_path:
        raise SystemExit("analyze: give the .raw (positional) or raw_path in the JSON config")
    cfg = cfg_from_args(a)
    r = analyze_pll(a.raw_path, cfg, label=os.path.basename(a.raw_path))
    out = report_text(r, "")
    print(out)
    os.makedirs(a.outdir, exist_ok=True)
    open(os.path.join(a.outdir, "pll_summary.txt"), "w").write(out + "\n")
    json.dump(clean(r), open(os.path.join(a.outdir, "pll_metrics.json"), "w"), indent=2)
    if not a.no_plots:
        print("Plot:", make_plots(r, a.outdir))
        for cpth in make_clock_plots(r, a.outdir):
            print("Plot:", cpth)
    return 0


def build_cases(a):
    cases = []
    for p in (a.preset or []):
        cases += [parse_corner(s) for s in PRESETS[p]]
    cases += [parse_corner(s) for s in (a.corner or [])]
    explicit = list(a.cases or [])
    for c in explicit:
        if "corner" in c:
            base = parse_corner(c["corner"]); base.update({k: v for k, v in c.items() if k != "corner"}); c = base
        cases.append(dict(c))
    if not cases:
        cases = [{}]
    ov = a.overrides or {}
    out = []
    for c in cases:
        nm = case_name(c) if "process" in c else (c.get("name") or "nominal")
        c = dict(c); c["name"] = nm
        extra = ov.get(nm) or {}
        for k, v in extra.items():
            if isinstance(v, dict):
                c[k] = {**(c.get(k) or {}), **v}
            elif k == "subs":
                c[k] = list(c.get(k) or []) + list(v)
            else:
                c[k] = v
        # common parameter values for every case (case values win)
        if a.common_params:
            c["params"] = {**a.common_params, **(c.get("params") or {})}
        out.append(c)
    names = [c["name"] for c in out]
    if len(set(names)) != len(names):
        raise SystemExit(f"duplicated case names: {names}")
    return out


def run_case(a, case, text0, cfg):
    rundir = os.path.join(a.outdir, case["name"])
    os.makedirs(rundir, exist_ok=True)
    rawname = "pll.raw"
    try:
        text = apply_case(text0, case, a.path_sub_pairs, a.tstop, a.tstep, a.threads, rawname, a.save)
    except ValueError as e:
        return {"case": case, "ok": False, "error": str(e)}
    miss = missing_includes(text)
    if miss:
        return {"case": case, "ok": False,
                "error": "file(s) not found in the netlist: " + ", ".join(miss) +
                         "  (fix the paths in the netlist, or use path_sub / --path-sub OLD=NEW; "
                         "a relative NEW in a JSON is relative to the JSON file)"}
    npath = os.path.join(rundir, "pll_case.spice")
    open(npath, "w").write(text)
    ok, info, dt = run_ngspice(npath, rundir, a.ngspice, a.timeout)
    raw = os.path.join(rundir, rawname)
    if not ok or not os.path.exists(raw):
        return {"case": case, "ok": False, "error": info if not ok else f"ngspice produced no .raw (see {info})"}
    ccfg = dict(cfg)
    if "vdd" in case:
        ccfg["vdd"] = case["vdd"]
    kv = (case.get("params") or {}).get("KVCO")
    if kv:
        ccfg["kvco"] = kv
    try:
        r = analyze_pll(raw, ccfg, label=case["name"])
    except Exception as e:
        return {"case": case, "ok": False, "error": f"analysis failed: {e}"}
    r["sim_seconds"] = dt
    r["_color"] = case_color(case)
    txt = report_text(r, f"- {case['name']}")
    open(os.path.join(rundir, "pll_summary.txt"), "w").write(txt + "\n")
    json.dump({"case": case, **clean(r)}, open(os.path.join(rundir, "pll_metrics.json"), "w"), indent=2)
    if not a.no_plots:
        make_plots(r, rundir)
        make_clock_plots(r, rundir)
    if not a.keep_raw:
        os.remove(raw)
    return {"case": case, "ok": True, "res": r}


def summary_rows(results):
    rows = []
    for x in results:
        row = {"case": x["case"]["name"], "ok": int(x["ok"])}
        if x["ok"]:
            r = x["res"]
            row.update({
                "f_clk_MHz": r["final"]["f_clk"] / 1e6, "err_ppm": r["final"]["err_ppm_clk"],
                "overshoot_pct": r["transient"]["f_fb_overshoot_pct"], "undershoot_pct": r["transient"]["f_fb_undershoot_after_peak_pct"],
                "phase_static_ps": r["phase"]["static_s"] * 1e12,
                "vctrl_final_V": r["vctrl"]["final_mean"], "vctrl_ripple_mV": r["vctrl"]["ripple_pp"] * 1e3,
                "vctrl_min_V": r["vctrl"]["min"], "vctrl_max_V": r["vctrl"]["max"],
                "t_phase_lock_us": r["phase"]["lock_time"] * 1e6,
            })
            for lk in r["lock_freq"]:
                row[f"t_lock_fb_{lk['label'].replace(' ', '')}_us"] = lk["fb"] * 1e6
            if "clock" in r:
                cj, ce, cs = r["clock"]["jitter"], r["clock"].get("eye", {}), r["clock"].get("spectrum", {})
                row.update({"tie_rms_ps": cj["tie_rms_rise"] * 1e12, "period_rms_ps": cj["period_rms"] * 1e12,
                            "c2c_rms_ps": cj["c2c_rms"] * 1e12, "duty_pct": cj["duty_mean"] * 100})
                if ce:
                    row.update({"eye_height_V": ce["height"], "eye_width_UI": ce["width_high_ui"],
                                "t_rise_ps": ce["t_rise_10_90"] * 1e12})
                if cs:
                    row.update({"thd_pct": cs["thd_pct"],
                                "spur_fref_dBc": max(cs["sidebands_dbc"]["1"]["lower_dbc"], cs["sidebands_dbc"]["1"]["upper_dbc"])})
            if "power" in r:
                row["P_uW"] = r["power"]["p_mean"] * 1e6
            row["warnings"] = len(r["warnings"])
        else:
            row["error"] = x["error"]
        rows.append(row)
    return rows


def cases_table(results):
    """One column per case, one row per metric."""
    names = [x["case"]["name"] for x in results]
    ok = [x for x in results if x["ok"]]
    rows = []
    def add_row(label, fn):
        rows.append([label] + [fn(x["res"]) if x["ok"] else "FAILED" for x in results])
    add_row("f_clk (MHz)", lambda r: f"{r['final']['f_clk'] / 1e6:.4f}")
    add_row("Error vs N*fref (ppm)", lambda r: f"{r['final']['err_ppm_clk']:+.2f}")
    if ok:
        for i, row in enumerate(ok[0]["res"]["lock_freq"]):
            add_row(f"Lock fb +-{row['label']}", lambda r, i=i: fmt_time(r["lock_freq"][i]["fb"]))
    add_row("Lock phase", lambda r: fmt_time(r["phase"]["lock_time"]))
    add_row("Overshoot (%)", lambda r: f"{r['transient']['f_fb_overshoot_pct']:+.3f}")
    add_row("Undershoot after peak (%)", lambda r: f"{r['transient']['f_fb_undershoot_after_peak_pct']:+.3f}")
    add_row("Static phase error (ps)", lambda r: f"{r['phase']['static_s'] * 1e12:+.1f}")
    add_row("vctrl final (V)", lambda r: f"{r['vctrl']['final_mean']:.4f}")
    add_row("vctrl ripple (mVpp)", lambda r: f"{r['vctrl']['ripple_pp'] * 1e3:.1f}")
    add_row("vctrl min / max (V)", lambda r: f"{r['vctrl']['min']:.3f} / {r['vctrl']['max']:.3f}")
    if ok and all("clock" in x["res"] for x in ok):
        add_row("TIE rms (ps)", lambda r: f"{r['clock']['jitter']['tie_rms_rise'] * 1e12:.3f}")
        add_row("Period jitter rms (ps)", lambda r: f"{r['clock']['jitter']['period_rms'] * 1e12:.3f}")
        add_row("Cycle-to-cycle rms (ps)", lambda r: f"{r['clock']['jitter']['c2c_rms'] * 1e12:.3f}")
        if all("spectrum" in x["res"]["clock"] for x in ok):
            add_row("THD (%)", lambda r: f"{r['clock']['spectrum']['thd_pct']:.1f}")
            add_row("Ref spur f_clk +- fref (dBc)", lambda r: "%.1f" % max(
                r["clock"]["spectrum"]["sidebands_dbc"]["1"]["lower_dbc"],
                r["clock"]["spectrum"]["sidebands_dbc"]["1"]["upper_dbc"]))
    if ok and all("power" in x["res"] for x in ok):
        add_row("Supply power, no VCO (mW)", lambda r: f"{r['power']['p_mean'] * 1e3:.2f}")
    add_row("Warnings", lambda r: str(len(r["warnings"])))
    return mk_table(["Metric"] + names, rows, left=(0,), title="CASE COMPARISON")


def cmd_run(a):
    cfg = cfg_from_args(a)
    text0 = open(a.netlist).read()
    cases = build_cases(a)
    os.makedirs(a.outdir, exist_ok=True)
    print(f"{len(cases)} case(s): {', '.join(c['name'] for c in cases)}   (jobs={a.jobs})")
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        futs = [(c, ex.submit(run_case, a, c, text0, cfg)) for c in cases]
        for c, f in futs:
            x = f.result()
            results.append(x)
            if x["ok"]:
                r = x["res"]
                lk = r["lock_freq"][0]
                print(f"  {c['name']:<22} f={r['final']['f_clk'] / 1e6:9.4f} MHz  lock({lk['label']}) fb="
                      f"{fmt_time(lk['fb'])}  overshoot={r['transient']['f_fb_overshoot_pct']:.2f} %  "
                      f"phase={r['phase']['static_s'] * 1e12:+.0f} ps  [{r['sim_seconds']:.0f} s]")
            else:
                print(f"  {c['name']:<22} FAILED: {x['error']}")
    rows = summary_rows(results)
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(os.path.join(a.outdir, "cases_summary.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    okc = [x for x in results if x["ok"]]
    if okc and not a.no_plots and len(okc) > 1:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
        seen = {}
        for x in okc:
            s_ = x["res"]["_series"]; nm = x["case"]["name"]; col = x["res"]["_color"]
            k_ = seen.get(col, 0); seen[col] = k_ + 1
            ls = ["-", "--", ":", "-."][k_ % 4]            # same process twice (different parameters): other line style
            ax[0].plot(s_["tmf"] * 1e6, s_["dev_fb"] * 100, lw=0.9, label=nm, color=col, ls=ls)
            ax[1].plot(s_["t"] * 1e6, s_["vctrl"], lw=0.7, color=col, ls=ls)
            ax[2].plot(s_["tpe"] * 1e6, s_["pe"] * 1e12, lw=0.9, color=col, ls=ls)
        ax[0].set_ylabel("f_fb / fref - 1 (%)"); ax[0].legend(); ax[1].set_ylabel("vctrl (V)")
        ax[2].set_ylabel("phase error (ps)"); ax[2].set_xlabel("time (us)")
        for q in ax:
            q.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(a.outdir, "cases_comparison.png"), dpi=130); plt.close(fig)
    json.dump([clean({"case": x["case"], **({"res": x["res"]} if x["ok"] else {"error": x["error"]})})
               for x in results], open(os.path.join(a.outdir, "cases_metrics.json"), "w"), indent=2)
    ct = cases_table(results)
    print(); print(ct)
    open(os.path.join(a.outdir, "cases_summary.txt"), "w").write(ct + "\n")
    print(f"Done in {time.time() - t0:.0f} s. Results in {a.outdir}/ (cases_summary.txt/.csv, cases_comparison.png)")
    return 0 if okc else 1


def cmd_selftest(a):
    here = os.path.dirname(os.path.abspath(__file__))
    raw = a.raw_path or os.path.join(here, "..", "osc_characterization", "CS_Pseudo_diff_N4.raw")
    if not os.path.exists(raw):
        print("selftest: example .raw not found:", raw); return 2
    t, tr = load_traces(raw, ["v(n1)", "v(n3)"])
    d = tr["v(n1)"] - tr["v(n3)"]
    edges = find_crossings(t, d, mid_level(d))
    edges = edges[edges >= 10e-9]                       # skip start-up
    _, T, _ = linear_fit(edges)
    f = 1 / T / 1e6
    ref = 597.29
    ok = abs(f - ref) < 0.05
    print(f"selftest: f = {f:.3f} MHz (osc_characterization reports {ref} MHz)  ->  {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


# ======================================================================
# Config / CLI
# ======================================================================

def read_json(path, depth=0):
    if depth > 8:
        raise SystemExit("config: 'extends' nested too deep")
    lines = [ln for ln in open(path).read().split("\n") if not ln.strip().startswith("//")]
    d = json.loads("\n".join(lines))
    ext = d.pop("extends", None)
    base = {}
    if ext:
        for e in ([ext] if isinstance(ext, str) else ext):
            base.update(read_json(os.path.join(os.path.dirname(os.path.abspath(path)), e), depth + 1))
    # paths in a parent are relative to the parent: resolve them now
    for k in ("netlist", "raw_path"):
        if k in d:
            d[k] = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), d[k]))
    if "path_sub" in d:
        here = os.path.dirname(os.path.abspath(path))
        d["path_sub"] = [f"{o}={os.path.normpath(os.path.join(here, n)) if not os.path.isabs(n) else n}"
                         for o, n in (d["path_sub"].items() if isinstance(d["path_sub"], dict)
                                      else (s.split("=", 1) for s in d["path_sub"]))]
    base.update({k: v for k, v in d.items() if not k.startswith("_")})
    return base


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="JSON with the options (command-line options take priority)")
    sp = p.add_subparsers(dest="command")

    def common(q):
        q.add_argument("--clk", default="v(clk)"); q.add_argument("--ref", default="v(ref)")
        q.add_argument("--fb", default="v(fb)"); q.add_argument("--vctrl", default="v(vctrl)")
        q.add_argument("--fref", help="nominal reference frequency (default: measured from ref)")
        q.add_argument("--n-div", dest="n_div", type=int, help="divider ratio (default: round(f_clk/fref))")
        q.add_argument("--vdd", type=float, help="supply (for power)")
        q.add_argument("--isupply", help="supply-current trace, e.g. i(v7)")
        q.add_argument("--final-frac", dest="final_frac", type=float, default=0.2,
                       help="fraction of the simulation (at the end) used as steady state (default 0.2)")
        q.add_argument("--t-final", dest="t_final", type=float, help="start of the steady-state window (s)")
        q.add_argument("--tols", nargs="+", help="lock tolerances as fractions (default 5e-3 1e-3 1e-4 1e-5)")
        q.add_argument("--phase-tol", dest="phase_tol", type=float, default=0.005,
                       help="phase-lock tolerance as a fraction of Tref (default 0.005)")
        q.add_argument("--skip-ref", dest="skip_ref", type=int, default=2,
                       help="ref periods ignored at the start for overshoot/ringing (divider start-up), default 2")
        q.add_argument("--kvco", help="VCO gain in Hz/V (to predict the reference spur from the vctrl ripple)")
        q.add_argument("--nharm", type=int, default=11, help="harmonics reported in the clk spectrum (default 11)")
        q.add_argument("--no-clock", dest="clock_quality", action="store_false", default=True,
                       help="skip the jitter/eye/spectrum analysis of clk")
        q.add_argument("--outdir"); q.add_argument("--no-plots", dest="no_plots", action="store_true")

    qa = sp.add_parser("analyze", help="characterize one .raw")
    qa.add_argument("raw_path", nargs="?", help="the .raw (or give raw_path in the JSON)"); common(qa)
    qr = sp.add_parser("run", help="simulate and analyze one or several cases")
    common(qr)
    qr.add_argument("--netlist"); qr.add_argument("--preset", action="append", choices=sorted(PRESETS))
    qr.add_argument("--corner", action="append", help="process:temp:vdd (repeatable)")
    qr.add_argument("--path-sub", dest="path_sub", action="append", help="OLD=NEW replacement in the netlist")
    qr.add_argument("--tstop"); qr.add_argument("--tstep")
    qr.add_argument("--jobs", type=int, default=1); qr.add_argument("--threads", type=int, default=1)
    qr.add_argument("--timeout", type=float, default=900)
    qr.add_argument("--ngspice", default="ngspice"); qr.add_argument("--keep-raw", dest="keep_raw", action="store_true")
    qr.add_argument("--save", nargs="+", help="replace 'save all' by this list of vectors (smaller .raw)")
    qs = sp.add_parser("selftest", help="check helpers against the osc_characterization example")
    qs.add_argument("raw_path", nargs="?")
    return p


def main():
    p = build_parser()
    pc = argparse.ArgumentParser(add_help=False)
    pc.add_argument("--config")
    pre, rest = pc.parse_known_args()
    cfg, cmd, extra = {}, None, {}
    if pre.config:
        cfg = read_json(pre.config)
        cmd = cfg.pop("command", None)
        extra = {k: cfg.pop(k) for k in ("cases", "overrides", "common_params") if k in cfg}
    argv = rest
    if cmd and not any(x in ("analyze", "run", "selftest") for x in argv):
        argv = [cmd] + argv
    # defaults from JSON go to the matching subparser
    for sub in p._subparsers._group_actions[0].choices.values():
        known = {a.dest for a in sub._actions}
        sub.set_defaults(**{k.replace("-", "_"): v for k, v in cfg.items() if k.replace("-", "_") in known})
    a = p.parse_args(argv)
    if not a.command:
        p.print_help(); return 2
    for k, v in extra.items():
        setattr(a, k, v)
    for k in ("cases", "overrides", "common_params"):
        if not hasattr(a, k):
            setattr(a, k, None)
    if a.command == "analyze":
        a.outdir = a.outdir or "pll_analysis"
        return cmd_analyze(a)
    if a.command == "run":
        if not a.netlist:
            raise SystemExit("run: --netlist is required")
        a.outdir = a.outdir or "pll_cases"
        subs = []
        for s in (a.path_sub or []):
            o, n = s.split("=", 1); subs.append((o, n))
        a.path_sub_pairs = subs
        if shutil.which(a.ngspice) is None and not os.path.exists(a.ngspice):
            raise SystemExit(f"ngspice not found ({a.ngspice})")
        return cmd_run(a)
    return cmd_selftest(a)


if __name__ == "__main__":
    sys.exit(main())
