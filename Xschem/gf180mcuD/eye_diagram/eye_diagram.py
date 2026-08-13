#!/usr/bin/env python3
"""
eye_diagram.py

Genera un diagrama de ojo a partir de un .raw de ngspice, plegando la señal
en ventanas de N*UI (UI = 1/freq) e interpolando cada ventana a una grilla
temporal comun antes de superponerlas.

CENTRADO AUTOMATICO DEL OJO: en vez de asumir que los cruces caen en un
punto fijo de la ventana, el script primero escanea la señal cruda para
encontrar TODOS los cruces por el umbral, calcula la fase promedio de esos
cruces respecto a la grilla ideal de bit (esto captura el retardo de
propagacion total del circuito, cualquiera que sea), y usa esa fase para
plegar las ventanas ya centradas: el CENTRO del ojo queda en 0 UI, el
cruce izquierdo idealmente en -0.5 UI, y el derecho en +0.5 UI. Esto
funciona sin importar cuanto delay tenga el circuito (una etapa, varias
etapas en cascada, etc.) porque el delay se mide de los datos, no se
asume.

UMBRAL DE DECISION OPTIMO: por default, en vez de asumir VDD/2 como
umbral de cruce, el script barre voltajes candidatos y se queda con el
que MINIMIZA el jitter de los cruces (dispersion temporal). Esto es
necesario porque VDD/2 (o el punto medio entre niveles alto/bajo) solo
coincide con el punto de cruce real cuando el circuito tiene flancos de
subida/bajada simetricos — en drivers con dinamica asimetrica entre
flancos, el cruce real de la señal puede estar lejos de ese punto medio.
Se puede desactivar con --no-refine-threshold para usar VDD/2 tal cual.

Uso:
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9 --signal v(out)
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9 --skip-ui 5 --ui-window 2
    python3 eye_diagram.py TB_not_PRBS.raw --freq 1e9 --vdd 3.3

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
    """
    Estimación INICIAL del umbral (el barrido de refine_threshold la
    corrige después, así que no hace falta que sea muy precisa):
      - Si se pasa center_voltage: se usa tal cual (para diferencial u
        otras señales donde el cruce no es VDD/2).
      - Si se pasa vdd: VDD/2 (para single-ended 0 a VDD).
      - Si no se pasa nada: (max+min)/2 de los datos — funciona para
        ambos casos sin necesidad de que el usuario indique el rango de
        voltajes explícitamente.
    """
    if center_voltage is not None:
        return center_voltage
    if vdd is not None:
        return vdd / 2.0
    return (values.max() + values.min()) / 2.0


def find_all_crossings(time: np.ndarray, values: np.ndarray, threshold: float, t_min: float):
    """Encuentra TODOS los cruces de 'values' por 'threshold' después de
    t_min, con interpolación lineal para precisión sub-muestra. Devuelve
    un array de tiempos absolutos de cruce (en segundos)."""
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
    Calcula la fase promedio (0 a 1, en unidades de UI) en la que ocurren
    los cruces, respecto a la grilla ideal de bit (múltiplos de UI desde
    t=0). Esto captura el retardo de propagación total del circuito,
    cualquiera que sea, midiéndolo de los datos en vez de asumirlo.

    Usa un promedio circular (vía vectores en el círculo unitario) porque
    la fase "envuelve" en 1.0 -> 0.0 y un promedio aritmético directo
    fallaría si las muestras están cerca de ese punto de wrap-around.

    Devuelve fase_centro_del_ojo = (fase_promedio_de_cruces + 0.5) mod 1.0
    — es decir, el punto medio entre dos cruces consecutivos, que es
    donde el ojo está más abierto (el mejor punto de muestreo).
    """
    if len(crossing_times) == 0:
        raise ValueError("No se detectó ningún cruce por el umbral en la señal; "
                          "no se puede centrar el ojo automáticamente.")

    phases = (crossing_times / ui) % 1.0
    angles = phases * 2 * np.pi
    mean_angle = np.arctan2(np.mean(np.sin(angles)), np.mean(np.cos(angles)))
    mean_phase = (mean_angle / (2 * np.pi)) % 1.0

    center_phase = (mean_phase + 0.5) % 1.0
    return center_phase, mean_phase


def fold_eye_centered(time: np.ndarray, values: np.ndarray, ui: float, n_ui_window: float,
                       skip_time: float, oversample: int, center_phase: float):
    """
    Pliega la señal en ventanas de ancho n_ui_window*UI, YA CENTRADAS: el
    grid devuelto va de -n_ui_window/2 a +n_ui_window/2 (en UI), con 0
    correspondiendo al centro del ojo (punto de máxima apertura) y los
    cruces esperados cerca de -0.5 y +0.5.

    center_phase viene de detect_center_phase(): es el offset (0 a 1, en
    UI) que hay que sumarle a cada múltiplo de UI para ubicar el centro
    real del ojo (compensando el delay de propagación del circuito).
    """
    window_width = n_ui_window * ui
    t_end = time[-1]

    n_points_grid = int(oversample * n_ui_window) + 1
    grid_rel = np.linspace(-window_width / 2, window_width / 2, n_points_grid)  # segundos, centrado en 0
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
            "No se pudo generar ninguna ventana centrada: revisa que skip_time + "
            "n_ui_window*UI no supere la duracion total de la simulacion."
        )

    return grid_in_ui, np.array(rows)


def circular_jitter_std(crossing_times: np.ndarray, ui: float) -> float:
    """Dispersión circular (en segundos) de la fase de los cruces respecto
    a la grilla de UI. Menor valor = cruces más consistentes en el tiempo
    = mejor candidato de umbral de decisión."""
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
    Encuentra el umbral de decisión "verdadero" barriendo voltajes
    candidatos y quedándose con el que MINIMIZA el jitter de los cruces
    (dispersión temporal). Este es el criterio físicamente correcto y
    general: coincide con el punto medio entre niveles alto/bajo SOLO
    cuando el circuito tiene flancos de subida/bajada simétricos: en
    drivers con dinámica asimétrica entre flancos (ej. drivers
    segmentados con pull-up/pull-down desbalanceados), el punto de cruce
    real de la señal puede estar bastante lejos de ese punto medio, y
    tomar VDD/2 (o el punto medio de niveles) como umbral introduce un
    sesgo artificial en las mediciones de jitter.

    Hace una búsqueda en dos etapas (gruesa sobre todo el rango de la
    señal, fina alrededor del mejor candidato de la etapa gruesa).

    Devuelve (threshold_refinado, offset_respecto_al_inicial, historial).
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
        Entre los candidatos evaluados, descarta los que capturan MUCHOS
        MENOS cruces que el máximo observado (< min_count_frac del máximo).
        Esto evita que la búsqueda se enganche con un umbral que da jitter
        artificialmente bajo solo porque captura un subconjunto chico y no
        representativo de las transiciones (típico con ISI severo, donde
        aparecen varias "familias" de cruces a distintos niveles) -- el
        umbral real debe capturar TODAS las transiciones, no solo las más
        consistentes entre sí.
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
        # no se pudo evaluar ningún candidato (señal sin suficientes cruces);
        # devolvemos el umbral inicial sin cambios
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

    ax.axvline(-0.5, color="darkorange", linestyle="--", linewidth=1, label="cruce izq. ideal (-0.5 UI)")
    ax.axvline(0.5, color="darkorange", linestyle="--", linewidth=1, label="cruce der. ideal (+0.5 UI)")
    ax.axvline(0.0, color="green", linestyle=":", linewidth=1, label="centro del ojo (0 UI)")

    ax.set_xlabel("Tiempo (UI, 0 = centro del ojo)")
    ax.set_ylabel(f"{signal} (V)")
    ax.set_title(f"Diagrama de ojo — {signal}  (UI = {ui*1e12:.1f} ps, {n_windows} ventanas plegadas)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    safe_signal = signal.replace("(", "").replace(")", "")
    fname = os.path.join(outdir, f"eye_{safe_signal}.png")
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Guardado: {fname}")
    return fname


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_path", help="Ruta al archivo .raw de ngspice")
    parser.add_argument("--freq", type=float, required=True, help="Frecuencia de bit (Hz). UI = 1/freq")
    parser.add_argument("--signal", default="v(out)", help="Señal a graficar (default: v(out))")
    parser.add_argument("--vdd", type=float, default=None,
                         help="VDD del circuito (para señales SINGLE-ENDED de 0 a VDD), fija el umbral "
                              "inicial en VDD/2. NO usar para señales diferenciales — usar "
                              "--center-voltage en su lugar, o simplemente omitir ambos flags.")
    parser.add_argument("--center-voltage", type=float, default=None,
                         help="Umbral inicial explícito, en Volts, sin dividir por nada (útil para "
                              "señales DIFERENCIALES centradas cerca de 0V, o cualquier señal cuyo "
                              "cruce no sea VDD/2). Si se omite (junto con --vdd), se auto-detecta "
                              "como (max+min)/2 de los datos — funciona bien tanto para single-ended "
                              "como para diferencial, ya que no asume ningún rango de voltajes fijo.")
    parser.add_argument("--no-refine-threshold", action="store_true",
                         help="Desactiva la búsqueda del umbral óptimo (ver refine_threshold()). "
                              "Si se pasa, se usa VDD/2 (o el auto-detectado) tal cual, sin buscar "
                              "el voltaje que minimiza el jitter de los cruces.")
    parser.add_argument("--ui-window", type=float, default=2.0,
                         help="Ancho de cada ventana plegada, en UI (default: 2.0)")
    parser.add_argument("--skip-ui", type=float, default=2.0,
                         help="Cuántos UI iniciales descartar como transitorio de arranque (default: 2.0)")
    parser.add_argument("--oversample", type=int, default=200,
                         help="Puntos por UI en la grilla interpolada (default: 200)")
    parser.add_argument("--outdir", default="eye_analysis", help="Directorio de salida (default: eye_analysis)")
    args = parser.parse_args()

    if not os.path.isfile(args.raw_path):
        print(f"Error: no se encontró '{args.raw_path}'", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    ui = 1.0 / args.freq
    print(f"UI = {ui*1e12:.2f} ps  (freq = {args.freq:.3e} Hz)")

    time, values = load_waveform(args.raw_path, args.signal)
    print(f"Señal '{args.signal}' cargada: {len(time)} puntos, "
          f"de t={time[0]*1e9:.2f}ns a t={time[-1]*1e9:.2f}ns")

    threshold_initial = detect_threshold(values, args.vdd, args.center_voltage)
    skip_time = args.skip_ui * ui

    if args.no_refine_threshold:
        threshold, offset, history = threshold_initial, 0.0, [threshold_initial]
        print(f"Umbral usado (refinamiento desactivado): {threshold:.4f} V")
    else:
        threshold, offset, history = refine_threshold(time, values, ui, skip_time, threshold_initial)
        print(f"Umbral inicial (VDD/2 o auto)     : {threshold_initial:.4f} V")
        print(f"Umbral refinado (mínimo jitter)   : {threshold:.4f} V")
        print(f"Offset detectado                  : {offset*1e3:+.2f} mV")

    all_crossings = find_all_crossings(time, values, threshold, skip_time)
    center_phase, mean_phase = detect_center_phase(all_crossings, ui)
    print(f"Cruces detectados para auto-centrado: {len(all_crossings)}")
    print(f"Fase promedio de los cruces respecto a la grilla ideal: {mean_phase*ui*1e12:.2f} ps "
          f"({mean_phase:.4f} UI)  <- esto es el delay de propagación total detectado")
    print(f"Fase del centro del ojo (usada para plegar): {center_phase:.4f} UI")

    grid_in_ui, matrix = fold_eye_centered(time, values, ui, args.ui_window, skip_time,
                                            args.oversample, center_phase)
    n_windows = matrix.shape[0]
    print(f"Ventanas plegadas: {n_windows}  (ancho de ventana: {args.ui_window} UI, "
          f"{args.oversample} puntos/UI)")

    plot_eye(grid_in_ui, matrix, args.signal, ui, n_windows, args.outdir)

    npz_path = os.path.join(args.outdir, "eye_folded_data.npz")
    np.savez(npz_path, grid_in_ui=grid_in_ui, matrix=matrix, ui=ui, signal=args.signal,
             threshold=threshold, threshold_initial=threshold_initial, threshold_offset=offset,
             threshold_refined=not args.no_refine_threshold,
             center_phase=center_phase, mean_phase=mean_phase)
    print(f"Datos plegados guardados en: {npz_path}  (para el calculo de métricas más adelante)")


if __name__ == "__main__":
    main()
