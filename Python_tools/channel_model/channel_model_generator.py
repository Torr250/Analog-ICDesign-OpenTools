#!/usr/bin/env python3
"""
channel_model_generator.py

Generates a SPICE subcircuit that models the channel LOSS as a "shelving"
low-pass filter (0 dB at DC by construction, plus the rolloff needed to pass
through two loss/frequency points).

It does NOT include transmission lines or coupling resistors (Z0, TD, Rs,
Rl) -- only the magnitude loss effect. If at some point you need Tx and/or Rx
reflections again, the version with ideal T-lines that we built earlier can be
brought back.

FILTER: loss_total(f) = loss_dc + [10*log10(1+(f/fp1)^2) - 10*log10(1+(f/fp2)^2)]
With fp1 < fp2 this grows monotonically with frequency, starting from
loss_dc at DC. fp1 and fp2 are solved from the two loss-versus-frequency
points (after subtracting loss_dc first).

Usage:
    python3 channel_model_generator.py --loss-dc 0 --f1 1e9 --loss1-db 2 --f2 4e9 --loss2-db 6

Requires: numpy, scipy, matplotlib. If ngspice is in the PATH, it runs an
automatic .AC validation.
"""

import argparse
import os
import shutil
import subprocess
import sys

import numpy as np
from scipy.optimize import fsolve
import matplotlib.pyplot as plt


def parse_eng(s: str) -> float:
    suffixes = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
                "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12}
    s = str(s).strip()
    for suf, mult in sorted(suffixes.items(), key=lambda x: -len(x[0])):
        if s.lower().endswith(suf):
            return float(s[:-len(suf)]) * mult
    return float(s)


# ----------------------------------------------------------------------
# Shelving filter fit (loss_dc + 2 frequency points)
# ----------------------------------------------------------------------

def shelf_loss_db(fp1: float, fp2: float, f: float) -> float:
    """0 dB at DC by construction; grows with frequency if fp2 > fp1."""
    return 10 * np.log10(1 + (f / fp1) ** 2) - 10 * np.log10(1 + (f / fp2) ** 2)


def fit_shelf(loss_dc_db: float, f1: float, loss1_db: float, f2: float, loss2_db: float, n_stages: int = 1):
    """
    Solves fp1, fp2 of ONE stage such that, when cascading n_stages IDENTICAL
    copies of that stage (loss_dc_db applied only once, as a final pad), the
    total gives:
        loss_dc_db + n_stages*shelf_loss_db(fp1,fp2,f1) = loss1_db
        loss_dc_db + n_stages*shelf_loss_db(fp1,fp2,f2) = loss2_db

    Why several stages are needed: a single pole-zero pair has a theoretical
    MAXIMUM slope of 20 dB/decade (6.02 dB/octave) in the transition band.
    If the requested loss points imply a larger slope than that, a single
    shelf CANNOT fit them whatever fp1/fp2 are chosen -- n_stages stages must
    be cascaded to multiply the maximum reachable slope by n_stages.

    Returns (fp1, fp2). Raises ValueError if it does not converge or if the
    result is not physically valid (fp1 < fp2, both positive), suggesting an
    increase in n_stages if the requested slope looks excessive.
    """
    if f2 <= f1:
        raise ValueError("f2 must be greater than f1.")
    if loss2_db < loss1_db:
        raise ValueError("loss2_db must be >= loss1_db (the loss must grow with frequency).")
    if loss1_db < loss_dc_db:
        raise ValueError("loss1_db must be >= loss_dc_db (the loss cannot drop below its DC value).")

    target1 = (loss1_db - loss_dc_db) / n_stages
    target2 = (loss2_db - loss_dc_db) / n_stages

    def eqs(x):
        logfp1, logfp2 = x
        fp1, fp2 = 10 ** logfp1, 10 ** logfp2
        return [shelf_loss_db(fp1, fp2, f1) - target1, shelf_loss_db(fp1, fp2, f2) - target2]

    best = None
    for g1_ghz, g2_ghz in [(0.5, 5), (0.1, 10), (1, 3), (0.3, 8), (2, 20), (0.05, 50), (0.8, 1.5)]:
        x0 = [np.log10(g1_ghz * f1), np.log10(g2_ghz * f2)]
        sol, info, ier, msg = fsolve(eqs, x0, full_output=True)
        if ier == 1:
            err = np.sum(np.array(eqs(sol)) ** 2)
            if best is None or err < best[0]:
                best = (err, sol)

    octave_slope = (loss2_db - loss1_db) / np.log2(f2 / f1)
    max_slope_per_stage = 20 * np.log10(2)  # ~6.02 dB/octave, theoretical limit of ONE shelf

    if best is None or best[0] > 1e-6 or (10 ** best[1][0] >= 10 ** best[1][1]):
        suggestion = ""
        if octave_slope > n_stages * max_slope_per_stage * 0.95:
            n_needed = int(np.ceil(octave_slope / max_slope_per_stage)) + 1
            suggestion = (
                f" The requested slope between f1 and f2 is ~{octave_slope:.2f} dB/octave; "
                f"a single shelf reaches at most ~{max_slope_per_stage:.2f} dB/octave per stage "
                f"(with n_stages={n_stages} you have ~{n_stages*max_slope_per_stage:.2f} dB/octave available). "
                f"Try --n-stages {n_needed} or more."
            )
        raise ValueError(
            "No solution was found for this shelving filter with the given points." + suggestion
        )

    fp1, fp2 = 10 ** best[1][0], 10 ** best[1][1]
    return fp1, fp2


# ----------------------------------------------------------------------
# Subcircuit generation (filter only, no T-lines or Rs/Rl)
# ----------------------------------------------------------------------

def generate_filter_subckt(subckt_name: str, fp1: float, fp2: float, loss_dc_db: float,
                            f1: float, loss1_db: float, f2: float, loss2_db: float,
                            n_stages: int = 1, cap: float = 1e-12) -> str:
    K = fp1 / fp2
    R = 1.0 / (2 * np.pi * fp1 * cap)
    pad_gain = 10 ** (-loss_dc_db / 20)

    # NOTE: channel_pulse_analysis.py reads "Fitted loss: ... dB at DC" and
    # "fp1=... GHz fp2=... GHz ... xN stages" from this header; keep both in sync.
    lines = [
        f"* ============================================================",
        f"* Channel model: LOSS ONLY (shelving filter, {n_stages} stage(s) in",
        f"* cascade), no transmission lines or reflection",
        f"* generated by channel_model_generator.py",
        f"*",
        f"* Fitted loss: {loss_dc_db:.3f} dB at DC, "
        f"{loss1_db:.3f} dB @ {f1/1e9:.4f} GHz, {loss2_db:.3f} dB @ {f2/1e9:.4f} GHz",
        f"* fp1={fp1/1e9:.6f} GHz   fp2={fp2/1e9:.6f} GHz   (per stage, x{n_stages} stages)",
        f"*",
        f"* Usage: X1 input_node output_node {subckt_name}",
        f"* The input has infinite impedance (senses, does not load) and the",
        f"* output is an ideal source (zero output impedance) -- it does not",
        f"* represent Z0 or reflections, only the magnitude loss shape.",
        f"* ============================================================",
        f".subckt {subckt_name} in out",
    ]

    node_prev = "in"
    for i in range(1, n_stages + 1):
        mid_in = f"mid_in{i}"
        mid_r = f"mid_r{i}"
        shelf_out = f"shelf_out{i}"
        lines.append(f"Ebuf_in{i} {mid_in} 0 {node_prev} 0 1")
        lines.append(f"R{i} {mid_in} {mid_r} {R:.6e}")
        lines.append(f"C{i} {mid_r} 0 {cap:.6e}")
        lines.append(f"Bshelf{i} {shelf_out} 0 V = V({mid_r}) + (V({mid_in})-V({mid_r}))*{K:.9f}")
        node_prev = shelf_out

    lines.append(f"Epad out 0 {node_prev} 0 {pad_gain:.9f}")
    lines.append(".ends")

    return "\n".join(lines) + "\n"


def plot_theoretical_response(fp1, fp2, loss_dc_db, f1, loss1_db, f2, loss2_db, n_stages, fmax, outpath):
    freqs = np.linspace(0, fmax, 1000)
    freqs[0] = 1e3
    loss_db = loss_dc_db + n_stages * shelf_loss_db(fp1, fp2, freqs)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(freqs / 1e9, -loss_db, color="steelblue", label=f"fitted filter ({n_stages} stage(s))")

    for f_spec, loss_spec in [(0, loss_dc_db), (f1, loss1_db), (f2, loss2_db)]:
        ax.scatter([f_spec / 1e9], [-loss_spec], color="red", zorder=5)
        ax.axvline(f_spec / 1e9, color="red", linestyle=":", linewidth=0.8, alpha=0.6)
        ax.axhline(-loss_spec, color="red", linestyle=":", linewidth=0.8, alpha=0.6)
        label = "DC" if f_spec == 0 else f"{f_spec/1e9:.3f} GHz"
        ax.annotate(f"{loss_spec:.2f} dB @ {label}",
                    xy=(f_spec / 1e9, -loss_spec), xytext=(8, 8), textcoords="offset points",
                    fontsize=9, color="firebrick")

    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("|Vout/Vin| (dB)")
    ax.set_xlim(0, fmax / 1e9)
    ax.set_title(f"Theoretical response of the shelving filter  (fp1={fp1/1e9:.3f}GHz, fp2={fp2/1e9:.3f}GHz)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()


# ----------------------------------------------------------------------
# Automatic validation with ngspice
# ----------------------------------------------------------------------

def validate_with_ngspice(outdir: str, subckt_name: str, fp1: float, fp2: float, loss_dc_db: float,
                           f1: float, loss1_db: float, f2: float, loss2_db: float, n_stages: int = 1):
    if shutil.which("ngspice") is None:
        print("\n(ngspice is not in the PATH -- the automatic .AC validation is skipped)")
        return

    subckt_text = generate_filter_subckt(subckt_name, fp1, fp2, loss_dc_db, f1, loss1_db, f2, loss2_db, n_stages)

    test_sp = os.path.join(outdir, "_validation_ac.sp")
    with open(test_sp, "w") as f:
        f.write("* internal validation (ideal source directly into the filter)\n")
        f.write(subckt_text)
        f.write("Vin in_src 0 AC 1\n")
        f.write(f"X1 in_src out {subckt_name}\n")
        f.write(".control\n")
        f.write(f"  ac dec 50 1e6 {max(f1,f2)*2}\n")
        f.write("  let loss_db = 20*log10(abs(v(out)))\n")
        f.write("  meas ac loss_dc FIND loss_db AT=1e6\n")
        f.write(f"  meas ac loss1 FIND loss_db AT={f1}\n")
        f.write(f"  meas ac loss2 FIND loss_db AT={f2}\n")
        f.write("  print loss_dc\n  print loss1\n  print loss2\n")
        f.write(".endc\n.end\n")

    try:
        result = subprocess.run(["ngspice", "-b", os.path.basename(test_sp)], capture_output=True, text=True,
                                 timeout=30, cwd=outdir)
        print("\n--- Automatic validation (.AC) ---")
        for line in result.stdout.splitlines():
            if line.strip().startswith(("loss_dc", "loss1", "loss2")):
                print(" ", line.strip())
        print(f"  (target: DC={-loss_dc_db:.3f}dB, f1={-loss1_db:.3f}dB @ {f1/1e9:.3f}GHz, "
              f"f2={-loss2_db:.3f}dB @ {f2/1e9:.3f}GHz)")
    except Exception as exc:
        print(f"\n(could not run the automatic validation: {exc})")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--loss-dc", type=float, default=0.0, help="Loss at DC (dB, default 0)")
    parser.add_argument("--f1", type=str, required=True, help="First loss frequency, e.g. '1e9'")
    parser.add_argument("--loss1-db", type=float, required=True, help="Loss (dB) at f1")
    parser.add_argument("--f2", type=str, required=True, help="Second loss frequency, e.g. '4e9'")
    parser.add_argument("--loss2-db", type=float, required=True, help="Loss (dB) at f2 (>= loss1-db)")
    parser.add_argument("--n-stages", type=int, default=1,
                         help="How many shelf stages to cascade (default: 1). Each stage adds "
                              "up to ~6.02 dB/octave of maximum slope -- if the requested slope "
                              "between f1 and f2 is too steep for 1 stage, the script will "
                              "suggest how many are needed.")
    parser.add_argument("--subckt-name", default="CHANNEL_MODEL", help="Subcircuit name")
    parser.add_argument("--outdir", default="channel_model", help="Output directory")
    parser.add_argument("--no-validate", action="store_true", help="Do not run the automatic validation with ngspice")
    args = parser.parse_args()

    f1 = parse_eng(args.f1)
    f2 = parse_eng(args.f2)

    os.makedirs(args.outdir, exist_ok=True)

    try:
        fp1, fp2 = fit_shelf(args.loss_dc, f1, args.loss1_db, f2, args.loss2_db, args.n_stages)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Fitted filter: fp1={fp1/1e9:.4f} GHz, fp2={fp2/1e9:.4f} GHz "
          f"(DC pad={args.loss_dc:.3f} dB, {args.n_stages} stage(s) in cascade)")

    subckt_text = generate_filter_subckt(args.subckt_name, fp1, fp2, args.loss_dc, f1, args.loss1_db, f2,
                                          args.loss2_db, args.n_stages)
    subckt_path = os.path.join(args.outdir, "channel_model.sp")
    with open(subckt_path, "w") as f:
        f.write(subckt_text)
    print(f"Saved: {subckt_path}")

    plot_path = os.path.join(args.outdir, "filter_response_theoretical.png")
    plot_theoretical_response(fp1, fp2, args.loss_dc, f1, args.loss1_db, f2, args.loss2_db, args.n_stages,
                               f2 * 1.5, plot_path)
    print(f"Saved: {plot_path}")

    if not args.no_validate:
        validate_with_ngspice(args.outdir, args.subckt_name, fp1, fp2, args.loss_dc,
                               f1, args.loss1_db, f2, args.loss2_db, args.n_stages)


if __name__ == "__main__":
    main()
