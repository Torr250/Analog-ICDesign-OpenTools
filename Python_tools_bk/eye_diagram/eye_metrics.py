#!/usr/bin/env python3
"""
eye_metrics.py

Calcula metricas de un diagrama de ojo YA CENTRADO (ver eye_diagram.py) a
partir de eye_analysis/eye_folded_data.npz:

  - Jitter IZQUIERDO: dispersión de los cruces cerca de -0.5 UI
  - Jitter DERECHO: dispersión de los cruces cerca de +0.5 UI
  - Ruido ARRIBA: dispersión de voltaje del nivel alto, en el centro (0 UI)
  - Ruido ABAJO: dispersión de voltaje del nivel bajo, en el centro (0 UI)
  - Eye height (altura, en V) y eye width (anchura, en UI/s)
  - 4 histogramas: jitter izquierdo, jitter derecho, ruido arriba, ruido abajo

A diferencia de la version anterior, el jitter se reporta por POSICION en
la ventana (izquierda/derecha), no por direccion de la transicion
(subida/bajada) — es la convencion estandar de equipos de eye-diagram: en
cada posicion (izquierda o derecha) puede haber tanto transiciones de
subida como de bajada, dependiendo del patron de bits aleatorio.

Requiere haber corrido antes:
    python3 eye_diagram.py <archivo.raw> --freq <freq>

Uso:
    python3 eye_metrics.py
    python3 eye_metrics.py --npz eye_analysis/eye_folded_data.npz
"""

import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm


def load_folded(npz_path: str):
    if not os.path.isfile(npz_path):
        print(f"Error: no se encontró '{npz_path}'. Corré primero eye_diagram.py.", file=sys.stderr)
        sys.exit(1)
    data = np.load(npz_path, allow_pickle=True)
    return {
        "grid_in_ui": data["grid_in_ui"],
        "matrix": data["matrix"],
        "ui": float(data["ui"]),
        "signal": str(data["signal"]),
        "threshold": float(data["threshold"]),
    }


def compute_side_tie(grid_in_ui: np.ndarray, matrix: np.ndarray, ui: float, threshold: float,
                      side: str, search_half_width: float = 0.3):
    """
    Busca, en cada ventana, el cruce por 'threshold' cerca de -0.5 UI
    (side='left') o +0.5 UI (side='right'), dentro de una banda de
    busqueda de +/- search_half_width alrededor de ese punto ideal.
    Devuelve una lista de TIE (cruce_real - ideal) en segundos, junto con
    la posicion absoluta (en UI) de cada cruce detectado.
    """
    ideal = -0.5 if side == "left" else 0.5
    band_lo, band_hi = ideal - search_half_width, ideal + search_half_width
    mask = (grid_in_ui > band_lo) & (grid_in_ui < band_hi)
    sub_grid = grid_in_ui[mask]

    tie_list = []
    for row in matrix:
        sub_vals = row[mask]
        signs = np.sign(sub_vals - threshold)
        crossing_idx = np.where(np.diff(signs) != 0)[0]
        if len(crossing_idx) == 0:
            continue

        best = min(crossing_idx, key=lambda i: abs(sub_grid[i] - ideal))
        i0, i1 = best, best + 1
        x0, x1 = sub_grid[i0], sub_grid[i1]
        y0, y1 = sub_vals[i0], sub_vals[i1]
        if y1 == y0:
            continue
        frac = (threshold - y0) / (y1 - y0)
        cross_ui = x0 + frac * (x1 - x0)

        tie_list.append({
            "cross_ui": cross_ui,
            "tie_ui": cross_ui - ideal,
            "tie_s": (cross_ui - ideal) * ui,
        })

    return tie_list


def stats_of(values: np.ndarray) -> dict:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan"),
                "min": float("nan"), "max": float("nan"), "pp": float("nan")}
    return {
        "n": n,
        "mean": values.mean(),
        "std": values.std(ddof=1) if n > 1 else 0.0,
        "min": values.min(),
        "max": values.max(),
        "pp": values.max() - values.min(),
    }


def compute_top_bottom_noise(grid_in_ui: np.ndarray, matrix: np.ndarray, threshold: float):
    """Ruido de voltaje en el centro del ojo (0 UI): separa las muestras
    en nivel ARRIBA (top) y ABAJO (bottom)."""
    center_idx = np.argmin(np.abs(grid_in_ui - 0.0))
    center_vals = matrix[:, center_idx]

    top_vals = center_vals[center_vals > threshold]
    bottom_vals = center_vals[center_vals <= threshold]

    return {"top": stats_of(top_vals), "bottom": stats_of(bottom_vals)}, top_vals, bottom_vals


def print_summary(tie_left, tie_right, noise_stats, ui, threshold):
    left_ui = np.array([t["tie_ui"] for t in tie_left])
    right_ui = np.array([t["tie_ui"] for t in tie_right])
    left_s = left_ui * ui
    right_s = right_ui * ui

    print("=" * 60)
    print(f"JITTER IZQUIERDO Y DERECHO (respecto al cruce ideal en ±0.5 UI)")
    print("=" * 60)
    for label, arr_s in [("Izquierdo (-0.5 UI)", left_s), ("Derecho (+0.5 UI)", right_s)]:
        s = stats_of(arr_s)
        if s["n"] == 0:
            print(f"\n{label}: sin cruces detectados")
            continue
        print(f"\n{label}  (n={s['n']}):")
        print(f"  media = {s['mean']*1e12:+.2f} ps   pp = {s['pp']*1e12:.2f} ps   "
              f"rms = {s['std']*1e12:.2f} ps")

    print()
    print("=" * 60)
    print("RUIDO DE VOLTAJE (ARRIBA Y ABAJO, en el centro del ojo)")
    print("=" * 60)
    for name, label in [("top", "Arriba"), ("bottom", "Abajo")]:
        s = noise_stats[name]
        if s["n"] == 0:
            print(f"\n{label}: sin muestras")
            continue
        print(f"\n{label}  (n={s['n']}):")
        print(f"  media = {s['mean']:.4f} V   sigma = {s['std']*1e3:.2f} mV")
        print(f"  min/max = {s['min']:.4f} V / {s['max']:.4f} V")

    print()
    print("=" * 60)
    print("ALTURA Y ANCHURA DEL OJO")
    print("=" * 60)

    top, bottom = noise_stats["top"], noise_stats["bottom"]
    if top["n"] and bottom["n"]:
        raw_height = top["min"] - bottom["max"]
        sigma3_height = (top["mean"] - 3 * top["std"]) - (bottom["mean"] + 3 * bottom["std"])
        print(f"\nEye height (raw, min-max observado) : {raw_height:.4f} V")
        print(f"Eye height (estimado a 3-sigma)      : {sigma3_height:.4f} V")

    if len(left_s) and len(right_s):
        left_mean_ui = left_ui.mean() - 0.5  # posición absoluta real del cruce izq (en UI, centro=0)
        right_mean_ui = right_ui.mean() + 0.5
        raw_width_ui = (right_ui.min() + 0.5) - (left_ui.max() - 0.5)  # peor caso observado
        sigma3_width_ui = (right_mean_ui - 3 * right_s.std(ddof=1)) - (left_mean_ui + 3 * left_s.std(ddof=1)) \
            if len(right_s) > 1 and len(left_s) > 1 else float("nan")
        print(f"\nCruce izquierdo promedio  : {left_mean_ui:+.4f} UI  ({left_mean_ui*ui*1e12:+.2f} ps)")
        print(f"Cruce derecho promedio    : {right_mean_ui:+.4f} UI  ({right_mean_ui*ui*1e12:+.2f} ps)")
        print(f"Eye width (raw, peor caso observado) : {raw_width_ui:.4f} UI  ({raw_width_ui*ui*1e12:.2f} ps)")
        print(f"Eye width (estimado a 3-sigma)        : {sigma3_width_ui:.4f} UI  "
              f"({sigma3_width_ui*ui*1e12:.2f} ps)")
    print()


def q_factor_for_ber(ber: float) -> float:
    """
    Q tal que BER = Q-function(Q) = 0.5*erfc(Q/sqrt(2)), asumiendo
    distribución gaussiana. Usamos scipy.stats.norm.isf (inverse survival
    function), que es numéricamente estable incluso para BER extremos
    (1e-12, 1e-15, etc.) a diferencia de invertir 1-CDF directamente.

    NOTA IMPORTANTE: esta extrapolación asume que el jitter/ruido es
    gaussiano de cola infinita. Si el jitter es mayormente determinístico
    (ISI, sin ruido aleatorio real como Monte Carlo o trnoise), esta
    extrapolación a BER muy chicos es una aproximación estándar de la
    industria pero no está garantizada — el jitter determinístico suele
    estar acotado, no tiene colas infinitas reales.
    """
    return norm.isf(ber)


def compute_diamond_mask(tie_left, tie_right, noise_stats, ui, threshold, q):
    """
    Calcula los 4 vértices del rombo (mascara del ojo estadistico) a un
    BER dado (ya convertido a factor Q), usando el modelo gaussiano:
    cada borde del ojo (izq, der, arriba, abajo) se contrae hacia adentro
    en Q*sigma respecto a su valor medio.

    Devuelve un dict con los 4 vertices: left, right, top, bottom.
    """
    left_ui = np.array([t["tie_ui"] for t in tie_left])
    right_ui = np.array([t["tie_ui"] for t in tie_right])

    left_mean_ui = left_ui.mean() - 0.5
    left_sigma_ui = left_ui.std(ddof=1) if len(left_ui) > 1 else 0.0
    right_mean_ui = right_ui.mean() + 0.5
    right_sigma_ui = right_ui.std(ddof=1) if len(right_ui) > 1 else 0.0

    top, bottom = noise_stats["top"], noise_stats["bottom"]

    mask_left_ui = left_mean_ui + q * left_sigma_ui     # se mueve hacia adentro (hacia 0)
    mask_right_ui = right_mean_ui - q * right_sigma_ui   # se mueve hacia adentro (hacia 0)
    mask_top_v = top["mean"] - q * top["std"]            # se mueve hacia adentro (hacia el umbral)
    mask_bottom_v = bottom["mean"] + q * bottom["std"]    # se mueve hacia adentro (hacia el umbral)

    return {
        "left": (mask_left_ui, threshold),
        "right": (mask_right_ui, threshold),
        "top": (0.0, mask_top_v),
        "bottom": (0.0, mask_bottom_v),
        "left_sigma_ui": left_sigma_ui,
        "right_sigma_ui": right_sigma_ui,
        "top_sigma_v": top["std"],
        "bottom_sigma_v": bottom["std"],
    }


def print_diamond_mask(mask: dict, ber: float, q: float, ui: float):
    print("=" * 60)
    print(f"MÁSCARA DEL OJO ESTADÍSTICO A BER = {ber:.1e}  (Q = {q:.3f})")
    print("=" * 60)
    print("(extrapolación gaussiana — ver caveat en la documentación si el "
          "jitter es mayormente determinístico, sin ruido real habilitado)\n")
    lx, ly = mask["left"]
    rx, ry = mask["right"]
    tx, tvy = mask["top"]
    bx, bvy = mask["bottom"]
    print(f"Vértice izquierdo : {lx:+.4f} UI  ({lx*ui*1e12:+.2f} ps)  @ {ly:.4f} V")
    print(f"Vértice derecho   : {rx:+.4f} UI  ({rx*ui*1e12:+.2f} ps)  @ {ry:.4f} V")
    print(f"Vértice superior  : {tvy:.4f} V   @ {tx:+.4f} UI")
    print(f"Vértice inferior  : {bvy:.4f} V   @ {bx:+.4f} UI")
    print(f"\nApertura horizontal (ancho del rombo): {(rx-lx):.4f} UI  ({(rx-lx)*ui*1e12:.2f} ps)")
    print(f"Apertura vertical (alto del rombo)    : {(tvy-bvy):.4f} V")
    print()


def plot_diamond_mask(grid_in_ui, matrix, ui, signal, threshold, mask: dict, ber: float, outdir: str):
    fig, ax = plt.subplots(figsize=(10, 6.5))

    for row in matrix:
        ax.plot(grid_in_ui, row, color="steelblue", alpha=0.12, linewidth=0.8)

    lx, ly = mask["left"]
    rx, ry = mask["right"]
    tx, tvy = mask["top"]
    bx, bvy = mask["bottom"]

    diamond_x = [lx, tx, rx, bx, lx]
    diamond_y = [ly, tvy, ry, bvy, ly]
    ax.plot(diamond_x, diamond_y, color="red", linewidth=2, marker="o", markersize=4,
            label=f"máscara @ BER={ber:.0e}")
    ax.fill(diamond_x, diamond_y, color="red", alpha=0.1)

    ax.axhline(threshold, color="gray", linestyle=":", linewidth=1, alpha=0.6)
    ax.axvline(0.0, color="green", linestyle=":", linewidth=1, alpha=0.6)

    ax.set_xlabel("Tiempo (UI, 0 = centro del ojo)")
    ax.set_ylabel(f"{signal} (V)")
    ax.set_title(f"Diagrama de ojo con máscara estadística — {signal}  (BER = {ber:.0e})")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    fname = os.path.join(outdir, f"eye_mask_ber{ber:.0e}.png".replace("+", ""))
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Guardado: {fname}")


def compute_bathtub(tie_left, tie_right, ui: float, n_points: int = 400):
    """
    Calcula la curva de bathtub: para cada instante de muestreo candidato
    t (en UI, recorriendo el rango de la ventana), el BER estimado es la
    suma de las contribuciones de cola de las distribuciones de cruce
    izquierda y derecha (modelo gaussiano vía la funcion de supervivencia).
    """
    left_ui = np.array([t["tie_ui"] for t in tie_left])
    right_ui = np.array([t["tie_ui"] for t in tie_right])

    left_mean_ui = left_ui.mean() - 0.5
    left_sigma_ui = left_ui.std(ddof=1) if len(left_ui) > 1 else 1e-6
    right_mean_ui = right_ui.mean() + 0.5
    right_sigma_ui = right_ui.std(ddof=1) if len(right_ui) > 1 else 1e-6

    t_grid = np.linspace(-1.0, 1.0, n_points)

    # BER por el borde izquierdo: probabilidad de que el cruce izquierdo
    # (que en promedio está en left_mean_ui) jitteree hacia la derecha
    # más allá de t, invadiendo el punto de muestreo t
    ber_left = norm.sf((t_grid - left_mean_ui) / left_sigma_ui)
    # BER por el borde derecho: probabilidad de que el cruce derecho
    # jitteree hacia la izquierda más allá de t
    ber_right = norm.sf((right_mean_ui - t_grid) / right_sigma_ui)

    ber_total = ber_left + ber_right
    # el modelo satura en 0.5 (máxima incertidumbre posible por un borde)
    ber_total = np.clip(ber_total, 0, 1.0)

    return t_grid, ber_total, left_mean_ui, right_mean_ui


def plot_bathtub(t_grid, ber_total, ui, ber_target, left_mean_ui, right_mean_ui, outdir):
    fig, ax = plt.subplots(figsize=(9, 6))

    ax.semilogy(t_grid, ber_total, color="darkslateblue", linewidth=1.8)
    ax.axhline(ber_target, color="red", linestyle="--", linewidth=1.2,
               label=f"BER objetivo = {ber_target:.0e}")
    ax.axvline(0.0, color="green", linestyle=":", linewidth=1, alpha=0.7, label="centro del ojo")

    ax.set_xlabel("Tiempo de muestreo (UI, 0 = centro del ojo)")
    ax.set_ylabel("BER estimado")
    ax.set_title("Bathtub curve (extrapolación gaussiana desde el jitter medido)")
    ax.set_ylim(1e-18, 1.0)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    plt.tight_layout()

    fname = os.path.join(outdir, "bathtub_curve.png")
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Guardado: {fname}")


def plot_eye_with_metrics(grid_in_ui, matrix, ui, signal, threshold, tie_left, tie_right, outdir):
    fig, ax = plt.subplots(figsize=(10, 6.5))

    for row in matrix:
        ax.plot(grid_in_ui, row, color="steelblue", alpha=0.15, linewidth=0.8)

    ax.axhline(threshold, color="gray", linestyle=":", linewidth=1, label=f"umbral = {threshold:.3f} V")
    ax.axvline(0.0, color="green", linestyle=":", linewidth=1.2, label="centro del ojo (0 UI)")
    ax.axvline(-0.5, color="darkorange", linestyle="--", linewidth=1, label="cruce izq. ideal")
    ax.axvline(0.5, color="darkorange", linestyle="--", linewidth=1, label="cruce der. ideal")

    if tie_left:
        left_pos = [t["cross_ui"] for t in tie_left]
        ax.scatter(left_pos, [threshold] * len(left_pos), color="red", s=10, zorder=5,
                   label="cruces izquierdos")
    if tie_right:
        right_pos = [t["cross_ui"] for t in tie_right]
        ax.scatter(right_pos, [threshold] * len(right_pos), color="purple", s=10, zorder=5,
                   label="cruces derechos")

    ax.set_xlabel("Tiempo (UI, 0 = centro del ojo)")
    ax.set_ylabel(f"{signal} (V)")
    ax.set_title(f"Diagrama de ojo con métricas — {signal}  (UI = {ui*1e12:.1f} ps)")
    ax.legend(fontsize=7, loc="center left")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    fname = os.path.join(outdir, "eye_with_metrics.png")
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Guardado: {fname}")


def plot_histogram(values_ps: np.ndarray, title: str, xlabel: str, color: str, fname: str, outdir: str):
    if len(values_ps) == 0:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    data_min, data_max = values_ps.min(), values_ps.max()
    span = max(data_max - data_min, 1e-6)
    pad = span * 0.3
    n_bins = max(5, min(25, len(values_ps) // 2 or 5))
    bin_edges = np.linspace(data_min - pad, data_max + pad, n_bins)

    mean = values_ps.mean()
    sigma = values_ps.std(ddof=1) if len(values_ps) > 1 else 0.0

    ax.hist(values_ps, bins=bin_edges, color=color, edgecolor="white", alpha=0.85)
    ax.axvline(mean, color="black", linestyle="--", linewidth=1.2,
               label=f"media = {mean:.3f}\nsigma = {sigma:.3f}")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Frecuencia (# muestras)")
    ax.set_title(f"{title}  (n={len(values_ps)})")
    ax.legend()
    plt.tight_layout()

    path = os.path.join(outdir, fname)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Guardado: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--npz", default="eye_analysis/eye_folded_data.npz",
                         help="Ruta al .npz generado por eye_diagram.py")
    parser.add_argument("--outdir", default="eye_analysis", help="Directorio de salida")
    parser.add_argument("--ber", type=float, default=1e-12,
                         help="BER objetivo para la máscara del ojo y el bathtub (default: 1e-12)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    d = load_folded(args.npz)
    grid_in_ui, matrix, ui, signal, threshold = d["grid_in_ui"], d["matrix"], d["ui"], d["signal"], d["threshold"]
    print(f"Señal: {signal}   UI: {ui*1e12:.2f} ps   Umbral de switching: {threshold:.4f} V\n")

    tie_left = compute_side_tie(grid_in_ui, matrix, ui, threshold, side="left")
    tie_right = compute_side_tie(grid_in_ui, matrix, ui, threshold, side="right")

    noise_stats, top_vals, bottom_vals = compute_top_bottom_noise(grid_in_ui, matrix, threshold)

    print_summary(tie_left, tie_right, noise_stats, ui, threshold)

    plot_eye_with_metrics(grid_in_ui, matrix, ui, signal, threshold, tie_left, tie_right, args.outdir)

    left_ps = np.array([t["tie_s"] for t in tie_left]) * 1e12
    right_ps = np.array([t["tie_s"] for t in tie_right]) * 1e12
    plot_histogram(left_ps, "Jitter izquierdo (TIE)", "TIE (ps)", "firebrick",
                    "hist_jitter_izquierdo.png", args.outdir)
    plot_histogram(right_ps, "Jitter derecho (TIE)", "TIE (ps)", "steelblue",
                    "hist_jitter_derecho.png", args.outdir)
    plot_histogram(top_vals, "Ruido de voltaje - Arriba", "Voltaje (V)", "seagreen",
                    "hist_ruido_arriba.png", args.outdir)
    plot_histogram(bottom_vals, "Ruido de voltaje - Abajo", "Voltaje (V)", "darkorange",
                    "hist_ruido_abajo.png", args.outdir)

    # --- máscara de rombo a la BER objetivo ---
    q = q_factor_for_ber(args.ber)
    mask = compute_diamond_mask(tie_left, tie_right, noise_stats, ui, threshold, q)
    print_diamond_mask(mask, args.ber, q, ui)
    plot_diamond_mask(grid_in_ui, matrix, ui, signal, threshold, mask, args.ber, args.outdir)

    # --- bathtub curve ---
    t_grid, ber_total, left_mean_ui, right_mean_ui = compute_bathtub(tie_left, tie_right, ui)
    plot_bathtub(t_grid, ber_total, ui, args.ber, left_mean_ui, right_mean_ui, args.outdir)


if __name__ == "__main__":
    main()
