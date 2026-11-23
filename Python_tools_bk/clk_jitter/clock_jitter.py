#!/usr/bin/env python3
"""
clock_jitter.py

Analiza jitter y genera el diagrama de ojo de una señal de RELOJ PERIÓDICA
(a diferencia de eye_diagram.py / eye_metrics.py, que son para datos PRBS
aleatorios). Las diferencias clave respecto al caso PRBS:

  - Los cruces se separan por DIRECCIÓN (subida/bajada), no por posición
    en la ventana — en un reloj cada dirección ocurre siempre en la misma
    fase del período, a diferencia de PRBS donde ambas direcciones pueden
    aparecer en cualquier posición según el patrón de bits.

  - El duty cycle se MIDE de los datos (distancia entre la fase de
    subida y la de bajada), no se asume 50%/±0.5 UI como en PRBS.

  - El TIE se calcula respecto a una grilla ideal ajustada por REGRESIÓN
    LINEAL sobre los tiempos de cruce reales (no respecto al parámetro
    'freq' nominal tal cual) — así, si la frecuencia real del reloj
    difiere levemente de 'freq' (osciladores reales rara vez calzan
    exacto), el TIE no muestra una deriva lineal espuria por ese
    descalce; el jitter de período y ciclo-a-ciclo (diferencias entre
    cruces consecutivos) son inmunes a esto por construcción, ya que
    solo comparan ciclos consecutivos entre sí.

Métricas que calcula:
  - Frecuencia/período medido vs. nominal
  - Duty cycle medido
  - TIE de subida y de bajada (respecto a la grilla ajustada por
    regresión lineal, por separado para cada dirección)
  - Jitter de período (T_n) y jitter ciclo-a-ciclo (T_n - T_(n-1)),
    para subida y para bajada
  - Ruido de voltaje en el nivel alto y bajo (muestreado en el punto
    medio real de cada pulso, según el duty cycle medido)
  - Diagrama de ojo plegado y centrado en el flanco de subida

Uso:
    python3 clock_jitter.py clock.raw --freq 1e9 --signal v(clk)
    python3 clock_jitter.py clock.raw --freq 1e9 --signal v(clk) --vdd 1.8

Requiere: spicelib, numpy, matplotlib
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
# Carga y detección de cruces (con dirección)
# ----------------------------------------------------------------------

def load_waveform(raw_path: str, signal: str):
    if RawRead is None:
        raise RuntimeError(
            "spicelib no está instalado. Instalalo con:\n"
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
    """Encuentra los cruces por 'threshold' después de skip_time, separados
    en subida (rising) y bajada (falling), con interpolación lineal para
    precisión sub-muestra. Devuelve dos arrays de tiempos absolutos."""
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
    """Fase promedio (0 a 1, en UI) de un conjunto de cruces, vía
    promedio circular (robusto al wrap-around en 0/1)."""
    phases = (crossing_times / ui) % 1.0
    angles = phases * 2 * np.pi
    mean_angle = np.arctan2(np.mean(np.sin(angles)), np.mean(np.cos(angles)))
    return (mean_angle / (2 * np.pi)) % 1.0


# ----------------------------------------------------------------------
# Umbral óptimo (igual criterio que eye_diagram.py: minimizar jitter)
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
    """Igual que en eye_diagram.py: barre voltajes candidatos y se queda
    con el que minimiza el jitter COMBINADO (subida+bajada) de los cruces."""
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
# Métricas de jitter: TIE (por regresión lineal), período, ciclo-a-ciclo
# ----------------------------------------------------------------------

def linear_fit_tie(crossing_times: np.ndarray):
    """
    Ajusta t_n ~ n*T_fit + t0_fit por mínimos cuadrados, y devuelve el TIE
    de cada cruce respecto a esa grilla ajustada (no respecto al 'freq'
    nominal) — así el resultado no se contamina si la frecuencia real del
    reloj difiere levemente de la nominal.
    """
    n = len(crossing_times)
    if n < 3:
        return np.array([]), None, None

    idx = np.arange(n)
    # ajuste lineal: crossing_times = T_fit * idx + t0_fit
    A = np.vstack([idx, np.ones(n)]).T
    T_fit, t0_fit = np.linalg.lstsq(A, crossing_times, rcond=None)[0]

    ideal = t0_fit + idx * T_fit
    tie = crossing_times - ideal
    return tie, T_fit, t0_fit


def period_and_cycle_jitter(crossing_times: np.ndarray):
    """Jitter de período (T_n = t_n - t_(n-1)) y ciclo-a-ciclo
    (T_n - T_(n-1)), a partir de cruces consecutivos de la MISMA
    dirección. Ambos son inmunes a un posible descalce entre la
    frecuencia real y la nominal, porque solo comparan ciclos vecinos."""
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
# Folding del ojo, centrado en el flanco de SUBIDA
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
        raise ValueError("No se pudo generar ninguna ventana centrada — revisa skip_time/n_ui_window.")

    return grid_in_ui, np.array(rows)


def compute_top_bottom_noise(grid_in_ui: np.ndarray, matrix: np.ndarray, threshold: float,
                              duty_cycle: float):
    """Muestrea el nivel alto en el punto medio del pulso alto (a
    duty_cycle/2 UI del flanco de subida, que es grid=0) y el nivel bajo
    en el punto medio del pulso bajo — usando el duty cycle MEDIDO, no
    asumiendo 50%."""
    top_center_ui = duty_cycle / 2.0
    bottom_center_ui = duty_cycle + (1.0 - duty_cycle) / 2.0
    if bottom_center_ui > grid_in_ui.max():
        bottom_center_ui -= 1.0  # cae en la mitad "izquierda" de la ventana

    top_idx = np.argmin(np.abs(grid_in_ui - top_center_ui))
    bottom_idx = np.argmin(np.abs(grid_in_ui - bottom_center_ui))

    top_vals = matrix[:, top_idx]
    bottom_vals = matrix[:, bottom_idx]
    return stats_of(top_vals), stats_of(bottom_vals), top_vals, bottom_vals, top_center_ui, bottom_center_ui


# ----------------------------------------------------------------------
# Gráficos
# ----------------------------------------------------------------------

def plot_eye(grid_in_ui, matrix, signal, ui, duty_cycle, top_center_ui, bottom_center_ui, outdir):
    fig, ax = plt.subplots(figsize=(10, 6))
    for row in matrix:
        ax.plot(grid_in_ui, row, color="steelblue", alpha=0.15, linewidth=0.8)

    ax.axvline(0.0, color="green", linestyle=":", linewidth=1.2, label="flanco de subida (0 UI)")
    ax.axvline(duty_cycle, color="darkorange", linestyle="--", linewidth=1.2,
               label=f"flanco de bajada ({duty_cycle:.3f} UI)")
    ax.axvline(top_center_ui, color="seagreen", linestyle=":", linewidth=1, alpha=0.7, label="muestreo alto")
    ax.axvline(bottom_center_ui, color="chocolate", linestyle=":", linewidth=1, alpha=0.7, label="muestreo bajo")

    ax.set_xlabel("Tiempo (UI, 0 = flanco de subida)")
    ax.set_ylabel(f"{signal} (V)")
    ax.set_title(f"Diagrama de ojo — reloj  ({signal}, duty cycle medido = {duty_cycle*100:.2f}%)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fname = os.path.join(outdir, "clock_eye.png")
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Guardado: {fname}")


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
               label=f"media = {mean:.3f}\nsigma = {sigma:.3f}")
    ax.set_xlabel(f"{xlabel} ({unit_label})")
    ax.set_ylabel("Frecuencia (# muestras)")
    ax.set_title(f"{title}  (n={len(vals)})")
    ax.legend()
    plt.tight_layout()
    path = os.path.join(outdir, fname)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Guardado: {path}")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_path", help="Ruta al archivo .raw de ngspice")
    parser.add_argument("--freq", type=float, required=True, help="Frecuencia NOMINAL del reloj (Hz)")
    parser.add_argument("--signal", default="v(clk)", help="Señal a analizar (default: v(clk))")
    parser.add_argument("--vdd", type=float, default=None, help="VDD, para umbral inicial VDD/2")
    parser.add_argument("--center-voltage", type=float, default=None, help="Umbral inicial explícito")
    parser.add_argument("--no-refine-threshold", action="store_true",
                         help="Desactiva la búsqueda del umbral óptimo (usa VDD/2 o el auto-detectado tal cual)")
    parser.add_argument("--ui-window", type=float, default=2.0, help="Ancho de la ventana plegada, en UI (default: 2.0)")
    parser.add_argument("--skip-ui", type=float, default=2.0, help="UI iniciales a descartar (default: 2.0)")
    parser.add_argument("--oversample", type=int, default=200, help="Puntos por UI en la grilla (default: 200)")
    parser.add_argument("--outdir", default="clock_analysis", help="Directorio de salida")
    args = parser.parse_args()

    if not os.path.isfile(args.raw_path):
        print(f"Error: no se encontró '{args.raw_path}'", file=sys.stderr)
        sys.exit(1)
    os.makedirs(args.outdir, exist_ok=True)

    ui_nominal = 1.0 / args.freq
    time, values = load_waveform(args.raw_path, args.signal)
    print(f"Señal '{args.signal}' cargada: {len(time)} puntos, t=0 a {time[-1]*1e9:.2f}ns")
    print(f"UI nominal (1/freq): {ui_nominal*1e12:.2f} ps\n")

    threshold_initial = detect_threshold(values, args.vdd, args.center_voltage)
    skip_time = args.skip_ui * ui_nominal

    if args.no_refine_threshold:
        threshold = threshold_initial
        print(f"Umbral usado (sin refinar): {threshold:.4f} V\n")
    else:
        threshold, offset = refine_threshold(time, values, ui_nominal, skip_time, threshold_initial)
        print(f"Umbral inicial: {threshold_initial:.4f} V   Umbral refinado: {threshold:.4f} V   "
              f"Offset: {offset*1e3:+.2f} mV\n")

    rising, falling = find_crossings_by_direction(time, values, threshold, skip_time)
    print(f"Cruces detectados: {len(rising)} de subida, {len(falling)} de bajada\n")
    if len(rising) < 3 or len(falling) < 3:
        print("Error: no hay suficientes cruces de cada dirección para el análisis.", file=sys.stderr)
        sys.exit(1)

    # --- frecuencia/período medido, duty cycle ---
    rising_phase = circular_mean_phase(rising, ui_nominal)
    falling_phase = circular_mean_phase(falling, ui_nominal)
    duty_cycle = (falling_phase - rising_phase) % 1.0

    tie_rise, T_rise_fit, t0_rise_fit = linear_fit_tie(rising)
    tie_fall, T_fall_fit, _ = linear_fit_tie(falling)

    freq_measured = 1.0 / T_rise_fit if T_rise_fit else float("nan")

    print("=" * 60)
    print("FRECUENCIA Y DUTY CYCLE")
    print("=" * 60)
    print(f"Frecuencia nominal : {args.freq:.6e} Hz")
    print(f"Frecuencia medida  : {freq_measured:.6e} Hz  (ajuste lineal sobre flancos de subida)")
    print(f"Desvío             : {(freq_measured-args.freq)/args.freq*100:+.4f} %")
    print(f"Duty cycle medido  : {duty_cycle*100:.3f} %")
    print()

    # --- TIE ---
    print("=" * 60)
    print("TIE (respecto a la grilla ajustada por regresión lineal)")
    print("=" * 60)
    for label, tie in [("Subida", tie_rise), ("Bajada", tie_fall)]:
        s = stats_of(tie)
        print(f"\n{label}  (n={s['n']}):")
        print(f"  pp = {s['pp']*1e12:.2f} ps   rms = {s['std']*1e12:.2f} ps")
    print()

    # --- jitter de período y ciclo-a-ciclo ---
    period_rise, cc_rise = period_and_cycle_jitter(rising)
    period_fall, cc_fall = period_and_cycle_jitter(falling)

    print("=" * 60)
    print("JITTER DE PERÍODO Y CICLO-A-CICLO")
    print("=" * 60)
    for label, periods, cc in [("Subida", period_rise, cc_rise), ("Bajada", period_fall, cc_fall)]:
        sp, sc = stats_of(periods), stats_of(cc)
        print(f"\n{label}:")
        print(f"  Período  (n={sp['n']}): media={sp['mean']*1e12:.2f}ps  pp={sp['pp']*1e12:.2f}ps  "
              f"rms={sp['std']*1e12:.2f}ps")
        print(f"  Ciclo-a-ciclo (n={sc['n']}): pp={sc['pp']*1e12:.2f}ps  rms={sc['std']*1e12:.2f}ps")
    print()

    # --- eye diagram plegado ---
    grid_in_ui, matrix = fold_eye_on_rising(time, values, ui_nominal, args.ui_window,
                                             skip_time, args.oversample, rising_phase)
    n_windows = matrix.shape[0]
    print(f"Ventanas plegadas para el diagrama de ojo: {n_windows}\n")

    top_stats, bottom_stats, top_vals, bottom_vals, top_c, bottom_c = compute_top_bottom_noise(
        grid_in_ui, matrix, threshold, duty_cycle)

    print("=" * 60)
    print("RUIDO DE VOLTAJE (alto y bajo)")
    print("=" * 60)
    for label, s in [("Alto", top_stats), ("Bajo", bottom_stats)]:
        print(f"\n{label}  (n={s['n']}): media={s['mean']:.4f}V  sigma={s['std']*1e3:.2f}mV")
    print()

    plot_eye(grid_in_ui, matrix, args.signal, ui_nominal, duty_cycle, top_c, bottom_c, args.outdir)

    plot_histogram(tie_rise, "TIE - Subida", "TIE", "firebrick", "hist_tie_subida.png", args.outdir)
    plot_histogram(tie_fall, "TIE - Bajada", "TIE", "steelblue", "hist_tie_bajada.png", args.outdir)
    plot_histogram(period_rise, "Jitter de período - Subida", "Período", "darkorange",
                    "hist_periodo_subida.png", args.outdir)
    plot_histogram(cc_rise, "Jitter ciclo-a-ciclo - Subida", "T_n - T_(n-1)", "purple",
                    "hist_ciclo_a_ciclo_subida.png", args.outdir)
    plot_histogram(top_vals, "Ruido de voltaje - Alto", "Voltaje", "seagreen",
                    "hist_ruido_alto.png", args.outdir, unit_scale=1e3, unit_label="mV")
    plot_histogram(bottom_vals, "Ruido de voltaje - Bajo", "Voltaje", "chocolate",
                    "hist_ruido_bajo.png", args.outdir, unit_scale=1e3, unit_label="mV")

    print(f"Todos los gráficos guardados en: {args.outdir}/")


if __name__ == "__main__":
    main()
