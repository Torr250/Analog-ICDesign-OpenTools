#!/usr/bin/env python3
"""
channel_model_generator.py

Genera un subcircuito SPICE que modela la PÉRDIDA del canal como un
filtro pasa-bajas "shelving" (0dB en DC por construcción, más el
rolloff necesario para pasar por dos puntos de pérdida/frecuencia).

NO incluye líneas de transmisión ni resistencias de acoplo (Z0, TD, Rs,
Rl) -- solo el efecto de pérdida en magnitud. Si en algún momento
volvés a necesitar reflexiones de Tx y/o Rx, se puede retomar la
versión con líneas T ideales que armamos antes.

FILTRO: loss_total(f) = loss_dc + [10*log10(1+(f/fp1)^2) - 10*log10(1+(f/fp2)^2)]
Con fp1 < fp2 esto crece monótonamente con la frecuencia, partiendo de
loss_dc en DC. Se resuelven fp1, fp2 a partir de los dos puntos de
pérdida en frecuencia (con loss_dc restado primero).

Uso:
    python3 channel_model_generator.py --loss-dc 0 --f1 1e9 --loss1-db 2 --f2 4e9 --loss2-db 6

Requiere: numpy, scipy, matplotlib. Si ngspice está en el PATH, corre
una validación .AC automática.
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
# Ajuste del filtro shelving (loss_dc + 2 puntos de frecuencia)
# ----------------------------------------------------------------------

def shelf_loss_db(fp1: float, fp2: float, f: float) -> float:
    """0dB en DC por construcción; crece con la frecuencia si fp2 > fp1."""
    return 10 * np.log10(1 + (f / fp1) ** 2) - 10 * np.log10(1 + (f / fp2) ** 2)


def fit_shelf(loss_dc_db: float, f1: float, loss1_db: float, f2: float, loss2_db: float, n_stages: int = 1):
    """
    Resuelve fp1, fp2 de UNA etapa tal que, al cascadear n_stages copias
    IDÉNTICAS de esa etapa (loss_dc_db aplicado una sola vez, como pad
    final), el total dé:
        loss_dc_db + n_stages*shelf_loss_db(fp1,fp2,f1) = loss1_db
        loss_dc_db + n_stages*shelf_loss_db(fp1,fp2,f2) = loss2_db

    Por qué hacen falta varias etapas: un solo par polo-cero tiene una
    pendiente MÁXIMA teórica de 20dB/década (6.02dB/octava) en la banda
    de transición. Si los puntos de pérdida pedidos implican una
    pendiente mayor a esa, un único shelf NO PUEDE ajustarlos sin
    importar qué fp1/fp2 se elijan -- hace falta cascadear n_stages
    etapas para multiplicar la pendiente máxima alcanzable por n_stages.

    Devuelve (fp1, fp2). Lanza ValueError si no converge o si el
    resultado no es físicamente válido (fp1 < fp2, ambos positivos),
    sugiriendo aumentar n_stages si la pendiente pedida parece excesiva.
    """
    if f2 <= f1:
        raise ValueError("f2 debe ser mayor que f1.")
    if loss2_db < loss1_db:
        raise ValueError("loss2_db debe ser >= loss1_db (la pérdida debe crecer con la frecuencia).")
    if loss1_db < loss_dc_db:
        raise ValueError("loss1_db debe ser >= loss_dc_db (la pérdida no puede bajar respecto a DC).")

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
    max_slope_per_stage = 20 * np.log10(2)  # ~6.02 dB/octava, límite teórico de UN shelf

    if best is None or best[0] > 1e-6 or (10 ** best[1][0] >= 10 ** best[1][1]):
        suggestion = ""
        if octave_slope > n_stages * max_slope_per_stage * 0.95:
            n_needed = int(np.ceil(octave_slope / max_slope_per_stage)) + 1
            suggestion = (
                f" La pendiente pedida entre f1 y f2 es ~{octave_slope:.2f} dB/octava; "
                f"un solo shelf alcanza como máximo ~{max_slope_per_stage:.2f} dB/octava por etapa "
                f"(con n_stages={n_stages} tenés ~{n_stages*max_slope_per_stage:.2f} dB/octava disponibles). "
                f"Probá con --n-stages {n_needed} o más."
            )
        raise ValueError(
            "No se encontró una solución para este filtro shelving con los puntos dados." + suggestion
        )

    fp1, fp2 = 10 ** best[1][0], 10 ** best[1][1]
    return fp1, fp2


# ----------------------------------------------------------------------
# Generación del subcircuito (solo filtro, sin líneas T ni Rs/Rl)
# ----------------------------------------------------------------------

def generate_filter_subckt(subckt_name: str, fp1: float, fp2: float, loss_dc_db: float,
                            f1: float, loss1_db: float, f2: float, loss2_db: float,
                            n_stages: int = 1, cap: float = 1e-12) -> str:
    K = fp1 / fp2
    R = 1.0 / (2 * np.pi * fp1 * cap)
    pad_gain = 10 ** (-loss_dc_db / 20)

    lines = [
        f"* ============================================================",
        f"* Modelo de canal: SOLO pérdida (filtro shelving, {n_stages} etapa(s) en",
        f"* cascada), sin líneas de transmisión ni reflexión",
        f"* generado por channel_model_generator.py",
        f"*",
        f"* Pérdida ajustada: {loss_dc_db:.3f} dB en DC, "
        f"{loss1_db:.3f} dB @ {f1/1e9:.4f} GHz, {loss2_db:.3f} dB @ {f2/1e9:.4f} GHz",
        f"* fp1={fp1/1e9:.6f} GHz   fp2={fp2/1e9:.6f} GHz   (por etapa, x{n_stages} etapas)",
        f"*",
        f"* Uso: X1 nodo_entrada nodo_salida {subckt_name}",
        f"* La entrada tiene impedancia infinita (sensa, no carga) y la",
        f"* salida es una fuente ideal (impedancia de salida cero) -- no",
        f"* representa Z0 ni reflexiones, solo la forma de pérdida en magnitud.",
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
    ax.plot(freqs / 1e9, -loss_db, color="steelblue", label=f"filtro ajustado ({n_stages} etapa(s))")

    for f_spec, loss_spec in [(0, loss_dc_db), (f1, loss1_db), (f2, loss2_db)]:
        ax.scatter([f_spec / 1e9], [-loss_spec], color="red", zorder=5)
        ax.axvline(f_spec / 1e9, color="red", linestyle=":", linewidth=0.8, alpha=0.6)
        ax.axhline(-loss_spec, color="red", linestyle=":", linewidth=0.8, alpha=0.6)
        label = "DC" if f_spec == 0 else f"{f_spec/1e9:.3f} GHz"
        ax.annotate(f"{loss_spec:.2f} dB @ {label}",
                    xy=(f_spec / 1e9, -loss_spec), xytext=(8, 8), textcoords="offset points",
                    fontsize=9, color="firebrick")

    ax.set_xlabel("Frecuencia (GHz)")
    ax.set_ylabel("|Vout/Vin| (dB)")
    ax.set_xlim(0, fmax / 1e9)
    ax.set_title(f"Respuesta teórica del filtro shelving  (fp1={fp1/1e9:.3f}GHz, fp2={fp2/1e9:.3f}GHz)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()


# ----------------------------------------------------------------------
# Validación automática con ngspice
# ----------------------------------------------------------------------

def validate_with_ngspice(outdir: str, subckt_name: str, fp1: float, fp2: float, loss_dc_db: float,
                           f1: float, loss1_db: float, f2: float, loss2_db: float, n_stages: int = 1):
    if shutil.which("ngspice") is None:
        print("\n(ngspice no está en el PATH — se omite la validación automática .AC)")
        return

    subckt_text = generate_filter_subckt(subckt_name, fp1, fp2, loss_dc_db, f1, loss1_db, f2, loss2_db, n_stages)

    test_sp = os.path.join(outdir, "_validation_ac.sp")
    with open(test_sp, "w") as f:
        f.write("* validacion interna (fuente ideal directa al filtro)\n")
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
        print("\n--- Validación automática (.AC) ---")
        for line in result.stdout.splitlines():
            if line.strip().startswith(("loss_dc", "loss1", "loss2")):
                print(" ", line.strip())
        print(f"  (objetivo: DC={-loss_dc_db:.3f}dB, f1={-loss1_db:.3f}dB @ {f1/1e9:.3f}GHz, "
              f"f2={-loss2_db:.3f}dB @ {f2/1e9:.3f}GHz)")
    except Exception as exc:
        print(f"\n(no se pudo correr la validación automática: {exc})")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--loss-dc", type=float, default=0.0, help="Pérdida en DC (dB, default 0)")
    parser.add_argument("--f1", type=str, required=True, help="Primera frecuencia de pérdida, ej. '1e9'")
    parser.add_argument("--loss1-db", type=float, required=True, help="Pérdida (dB) en f1")
    parser.add_argument("--f2", type=str, required=True, help="Segunda frecuencia de pérdida, ej. '4e9'")
    parser.add_argument("--loss2-db", type=float, required=True, help="Pérdida (dB) en f2 (>= loss1-db)")
    parser.add_argument("--n-stages", type=int, default=1,
                         help="Cuántas etapas de shelf cascadear (default: 1). Cada etapa agrega "
                              "hasta ~6.02 dB/octava de pendiente máxima -- si la pendiente pedida "
                              "entre f1 y f2 es muy empinada para 1 etapa, el script te va a "
                              "sugerir cuántas hacen falta.")
    parser.add_argument("--subckt-name", default="CHANNEL_MODEL", help="Nombre del subcircuito")
    parser.add_argument("--outdir", default="channel_model", help="Directorio de salida")
    parser.add_argument("--no-validate", action="store_true", help="No correr la validación automática con ngspice")
    args = parser.parse_args()

    f1 = parse_eng(args.f1)
    f2 = parse_eng(args.f2)

    os.makedirs(args.outdir, exist_ok=True)

    try:
        fp1, fp2 = fit_shelf(args.loss_dc, f1, args.loss1_db, f2, args.loss2_db, args.n_stages)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Filtro ajustado: fp1={fp1/1e9:.4f} GHz, fp2={fp2/1e9:.4f} GHz "
          f"(pad DC={args.loss_dc:.3f} dB, {args.n_stages} etapa(s) en cascada)")

    subckt_text = generate_filter_subckt(args.subckt_name, fp1, fp2, args.loss_dc, f1, args.loss1_db, f2,
                                          args.loss2_db, args.n_stages)
    subckt_path = os.path.join(args.outdir, "channel_model.sp")
    with open(subckt_path, "w") as f:
        f.write(subckt_text)
    print(f"Guardado: {subckt_path}")

    plot_path = os.path.join(args.outdir, "filter_response_theoretical.png")
    plot_theoretical_response(fp1, fp2, args.loss_dc, f1, args.loss1_db, f2, args.loss2_db, args.n_stages,
                               f2 * 1.5, plot_path)
    print(f"Guardado: {plot_path}")

    if not args.no_validate:
        validate_with_ngspice(args.outdir, args.subckt_name, fp1, fp2, args.loss_dc,
                               f1, args.loss1_db, f2, args.loss2_db, args.n_stages)


if __name__ == "__main__":
    main()
