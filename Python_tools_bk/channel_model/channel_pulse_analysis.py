#!/usr/bin/env python3
"""
channel_pulse_analysis.py

Analiza el channel_model.sp generado por channel_model_generator.py usando
respuesta al pulso, respuesta en AC, y el método de coeficientes de canal
para el Worst Case Eye Height (WC eye height) -- adaptado del código
serdes_functions.py del usuario, pero SIN depender de serdespy ni de
archivos de respuesta al impulso (.mat): como conocemos la función de
transferencia ANALÍTICA exacta del filtro shelving (una cascada de
secciones polo-cero), se puede calcular la respuesta al pulso directamente
con scipy.signal, sin necesidad de simular en ngspice ni de FFT/ventaneo.

MÉTODO DE COEFICIENTES DE CANAL (igual que serdes_functions.py):
  - Se calcula la respuesta al pulso (un pulso rectangular de 1 UI de
    ancho a través del canal).
  - Se muestrea esa respuesta en múltiplos de UI alrededor del pico
    (el cursor principal) -- eso da los "coeficientes de canal":
    n precursores, el cursor principal, n postcursores.
  - Worst Case Eye Height: se suman por separado todos los coeficientes
    NEGATIVOS (constructivos para el símbolo "1", ya que restan del "0")
    y todos los POSITIVOS (constructivos para el símbolo "0"), y se
    combinan con el cursor principal para estimar la apertura vertical
    en el peor patrón de bits posible. Positivo = ojo abierto,
    negativo = ojo cerrado.

Uso:
    python3 channel_pulse_analysis.py channel_model/channel_model.sp --datarate 1e9
    python3 channel_pulse_analysis.py channel_model/channel_model.sp --datarate 1e9 \
        --n-precursors 10 --n-postcursors 100

Si no se pasan fp1/fp2/loss-dc/n-stages explícitamente, se leen automáticamente
del encabezado de comentarios del archivo .sp (el que genera
channel_model_generator.py).

Requiere: numpy, scipy, matplotlib
"""

import argparse
import os
import re
import sys

import numpy as np
from scipy import signal
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
# Lectura de parámetros desde el .sp generado por channel_model_generator.py
# ----------------------------------------------------------------------

def parse_channel_sp(sp_path: str):
    with open(sp_path) as f:
        text = f.read()

    m_fp = re.search(r"fp1=([\d.]+)\s*GHz\s+fp2=([\d.]+)\s*GHz.*?x(\d+)\s*etapas", text)
    m_dc = re.search(r"Pérdida ajustada:\s*([\d.\-]+)\s*dB en DC", text)

    if not m_fp or not m_dc:
        raise ValueError(
            f"No se pudieron leer fp1/fp2/n_stages/loss_dc del encabezado de '{sp_path}'. "
            f"Pasalos explícitamente con --fp1/--fp2/--loss-dc/--n-stages."
        )

    fp1 = float(m_fp.group(1)) * 1e9
    fp2 = float(m_fp.group(2)) * 1e9
    n_stages = int(m_fp.group(3))
    loss_dc_db = float(m_dc.group(1))
    return fp1, fp2, loss_dc_db, n_stages


# ----------------------------------------------------------------------
# Función de transferencia analítica del canal
# ----------------------------------------------------------------------

def build_channel_tf(fp1: float, fp2: float, loss_dc_db: float, n_stages: int) -> signal.TransferFunction:
    """H_stage(s) = (1+s/wp2)/(1+s/wp1), cascadeada n_stages veces, con el
    pad de DC como ganancia escalar. Coincide exactamente con la topología
    SPICE que genera channel_model_generator.py (ver derivación verificada
    numéricamente contra la fórmula de pérdida)."""
    wp1, wp2 = 2 * np.pi * fp1, 2 * np.pi * fp2
    num_stage = [1 / wp2, 1]
    den_stage = [1 / wp1, 1]

    num_total = np.array([1.0])
    den_total = np.array([1.0])
    for _ in range(n_stages):
        num_total = np.polymul(num_total, num_stage)
        den_total = np.polymul(den_total, den_stage)

    pad_gain = 10 ** (-loss_dc_db / 20)
    num_total = num_total * pad_gain
    return signal.TransferFunction(num_total, den_total)


def build_ctle_tf(gmN: float, RL: float, CLtot: float, Rs: float, Cs: float, gdsN: float = 0.0):
    """
    CTLE de par diferencial con degeneración resistiva+capacitiva
    (Rs || Cs en la cola, RL || CLtot en la carga), con gdsN incluido
    (conductancia de salida del transistor, en paralelo con RL).

    H(s) = [n1*s + n0] / [d2*s^2 + d1*s + d0], con RL reemplazado por
    RL_eff = RL/(1+gdsN*RL) en todos los coeficientes -- verificado
    algebraicamente (sympy) que wp1 y wp2 siguen siendo raíces EXACTAS
    del denominador con esta sustitución:
        wz  = 1/(Rs*Cs)                              (sin cambios)
        wp1 = (1+gmN*Rs/2)/(Rs*Cs)                    (sin cambios, no depende de RL/gdsN)
        wp2 = (1+RL*gdsN)/(RL*CLtot)                  (antes 1/(RL*CLtot); gdsN lo empuja a mayor frecuencia)

    Devuelve (tf, info) donde info es un dict con wz, wp1, wp2 (en rad/s
    y Hz), dc_gain, ac_gain, boost_db, y cuál de wp1/wp2 es mayor.
    """
    RL_eff = RL / (1 + gdsN * RL)

    n1 = 2 * Cs * gmN * RL_eff * Rs
    n0 = 2 * gmN * RL_eff
    d2 = 2 * CLtot * Cs * RL_eff * Rs
    d1 = 2 * CLtot * RL_eff + 2 * Cs * Rs + CLtot * gmN * RL_eff * Rs
    d0 = 2 + gmN * Rs

    tf = signal.TransferFunction([n1, n0], [d2, d1, d0])

    wz = 1.0 / (Rs * Cs)
    wp1 = (1.0 + gmN * Rs / 2.0) / (Rs * Cs)
    wp2 = (1.0 + RL * gdsN) / (RL * CLtot)

    dc_gain = n0 / d0
    ac_gain = dc_gain * (wp1 / wz)
    boost_db = 20 * np.log10(wp1 / wz)

    info = {
        "wz": wz, "wp1": wp1, "wp2": wp2,
        "fz": wz / (2 * np.pi), "fp1": wp1 / (2 * np.pi), "fp2": wp2 / (2 * np.pi),
        "dc_gain": dc_gain, "ac_gain": ac_gain, "boost_db": boost_db,
        "wp2_gt_wp1": wp2 > wp1,
    }
    return tf, info


def cascade_tf(tf1: signal.TransferFunction, tf2: signal.TransferFunction) -> signal.TransferFunction:
    """Combina dos funciones de transferencia en cascada (multiplicación
    exacta de polinomios) -- válido porque ambas son sistemas LTI, sin
    necesidad de convolución en tiempo ni ninguna aproximación."""
    num = np.polymul(tf1.num, tf2.num)
    den = np.polymul(tf1.den, tf2.den)
    return signal.TransferFunction(num, den)


def print_ctle_info(info: dict):
    print("--- CTLE: polos, cero y ganancias ---")
    print(f"  fz  = {info['fz']/1e9:.4f} GHz")
    print(f"  fp1 = {info['fp1']/1e9:.4f} GHz")
    print(f"  fp2 = {info['fp2']/1e9:.4f} GHz")
    print(f"  DC gain = {info['dc_gain']:.4f} ({20*np.log10(info['dc_gain']):.2f} dB)")
    print(f"  AC gain (plateau) = {info['ac_gain']:.4f} ({20*np.log10(info['ac_gain']):.2f} dB)")
    print(f"  Boost = {info['boost_db']:.2f} dB")
    if info["wp2_gt_wp1"]:
        print(f"  fp2 > fp1 -> forma de peaking 'clásica': banda plana entre fz y fp1, "
              f"luego caída final en fp2. Esperable un único lóbulo de peaking bien definido.")
    else:
        print(f"  fp2 < fp1 -> fp2 empieza a atenuar ANTES de que fp1 termine de aplanar el boost -- "
              f"el peaking se ve recortado/reducido respecto al 'Boost' nominal calculado "
              f"(el plateau completo entre fz y fp1 nunca se alcanza del todo). Revisá si es lo que "
              f"buscás o si conviene ajustar los componentes para que fp2 quede por encima de fp1.")
    print()


def build_ctle_tf_from_gains(dc_gain_db: float, boost_db: float, f_nyquist: float, f_p2: float,
                              pole1_frac: float = 1.0):
    """
    Tercera forma de construir el CTLE: a partir de DC gain, Boost (=AC
    gain - DC gain, en dB), la frecuencia de Nyquist, y fp2 (el polo de
    salida) directamente.

    CORREGIDO: la primera versión colocaba el CERO en Nyquist -- está
    mal. Según Razavi ("The Design of an Equalizer, Part One", IEEE
    SSCS Magazine, Fall 2021, sección "CTLE Design" y Fig. 4b/6/Ec. 8),
    el criterio correcto es al revés: el POLO wp1 debe quedar POR DEBAJO
    de Nyquist (para que la curva ya esté aplanada -- en la meseta de
    ACgain -- cuando llega a Nyquist), y el cero wz queda todavía más
    abajo. wp2 (el polo de salida) queda DESPUÉS de Nyquist.

    OJO: DCgain + ACgain + Nyquist NO alcanzan para determinar wz y wp1
    por separado -- Boost = ACgain/DCgain = wp1/wz es UNA sola ecuación
    con DOS incógnitas (verificado con sympy). Hace falta anclar UNO de
    los dos a Nyquist; siguiendo el artículo, se ancla wp1:
        wp1 = pole1_frac * 2*pi*f_nyquist / boost_ratio
        wz  = wp1 / boost_ratio
        wp2 = 2*pi*f_p2                     (dado directamente)
    Con pole1_frac=1.0 (default) esto coincide exactamente con
    wp1 = 2*pi*fnyq/peaking_linear -- la fórmula que ya venías usando.
    Para un boost de 2-3x, esto da fp1 entre ~2 y 3 veces por debajo de
    fNyq, consistente con la Ec. 8 del artículo.

    H(s) = DCgain*(1+s/wz) / [(1+s/wp1)*(1+s/wp2)]
    (misma estructura que el modelo de transistores, verificada
    algebraicamente que es la forma exacta cuando gdsN=0).
    """
    dc_gain = 10 ** (dc_gain_db / 20)
    boost_ratio = 10 ** (boost_db / 20)  # = wp1/wz = ACgain/DCgain
    ac_gain = dc_gain * boost_ratio

    wp1 = pole1_frac * 2 * np.pi * f_nyquist / boost_ratio
    wz = wp1 / boost_ratio
    wp2 = 2 * np.pi * f_p2

    num = [dc_gain / wz, dc_gain]
    den = np.polymul([1 / wp1, 1], [1 / wp2, 1])
    tf = signal.TransferFunction(num, den)

    info = {
        "wz": wz, "wp1": wp1, "wp2": wp2,
        "fz": wz / (2 * np.pi), "fp1": wp1 / (2 * np.pi), "fp2": wp2 / (2 * np.pi),
        "dc_gain": dc_gain, "ac_gain": ac_gain, "boost_db": boost_db,
        "wp2_gt_wp1": wp2 > wp1,
    }
    return tf, info


def estimate_transistor_params(dc_gain: float, ac_gain: float, wz: float, wp1: float, wp2: float,
                                gmN_assumed: float):
    """
    Estima Rs, Cs, RL, CLtot del circuito de transistores a partir de
    (dc_gain, ac_gain, wz, wp1, wp2) -- los mismos 4 números que salen
    del modo 'gains' -- ASUMIENDO un valor de gmN.

    Por qué hace falta asumir gmN: el sistema tiene 4 ecuaciones
    (wz, wp1, DCgain, wp2) pero 5 incógnitas (gmN, RL, CLtot, Rs, Cs) --
    queda UN grado de libertad sin fijar. gmN es la elección natural,
    porque en un flujo de diseño real normalmente ya está determinado
    por el presupuesto de corriente de polarización y el overdrive del
    transistor (gm ~ 2*Itail/Vov), antes de elegir las resistencias.

    Fórmulas (verificadas con sympy, reconstruyen wp1 y DCgain exacto):
        Rs    = 2*(wp1-wz) / (gmN*wz)
        Cs    = 1 / (wz*Rs) = gmN / (2*(wp1-wz))
        RL    = ac_gain / gmN
        CLtot = 1 / (wp2*RL) = gmN / (ac_gain*wp2)

    NOTA: esto asume gdsN=0 (no se puede despejar gdsN de estos 4
    números sin otra ecuación independiente -- en la práctica gdsN se
    obtiene de la caracterización del transistor en su punto de
    polarización, no de este cálculo).
    """
    Rs = 2 * (wp1 - wz) / (gmN_assumed * wz)
    Cs = 1.0 / (wz * Rs)
    RL = ac_gain / gmN_assumed
    CLtot = 1.0 / (wp2 * RL)
    return {"Rs": Rs, "Cs": Cs, "RL": RL, "CLtot": CLtot, "gmN_assumed": gmN_assumed}


def print_estimated_params(params: dict):
    print("--- Estimación de parámetros del circuito de transistores ---")
    print(f"  (asumiendo gmN = {params['gmN_assumed']*1e3:.4f} mS)")
    print(f"  Rs    = {params['Rs']:.4f} Ohm")
    print(f"  Cs    = {params['Cs']*1e15:.4f} fF")
    print(f"  RL    = {params['RL']:.4f} Ohm")
    print(f"  CLtot = {params['CLtot']*1e15:.4f} fF")
    print("  (nota: asume gdsN=0 -- no hay suficientes ecuaciones para despejarlo también; "
          "usá el valor real de gdsN de la caracterización del transistor en su punto de polarización)")
    print()
# ----------------------------------------------------------------------

def compute_ac_response(tf: signal.TransferFunction, freqs: np.ndarray):
    w = 2 * np.pi * freqs
    _, H = signal.freqresp(tf, w)
    return H


def plot_ac_response(tf, fmax, outpath):
    freqs = np.linspace(1e6, fmax, 1000)
    H = compute_ac_response(tf, freqs)
    loss_db = -20 * np.log10(np.abs(H))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(freqs / 1e9, -loss_db, color="steelblue")
    ax.set_xlabel("Frecuencia (GHz)")
    ax.set_ylabel("|H(f)| (dB)")
    ax.set_title("Respuesta en AC (desde la función de transferencia analítica)")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"Guardado: {outpath}")


# ----------------------------------------------------------------------
# Respuesta al pulso (exacta, vía step response analítico)
# ----------------------------------------------------------------------

def compute_pulse_response(tf: signal.TransferFunction, ui: float, dt: float, n_ui_total: int):
    """Respuesta a un pulso rectangular de amplitud 1 y ancho 'ui', usando
    linealidad: pulso(t) = escalón(t) - escalón(t-ui). El escalón se
    calcula EXACTAMENTE (sin discretización de simulación) con
    scipy.signal.step sobre la función de transferencia analítica."""
    t = np.arange(0, n_ui_total * ui, dt)
    t_step, y_step = signal.step(tf, T=t)

    shift_samples = int(round(ui / dt))
    y_shifted = np.zeros_like(y_step)
    y_shifted[shift_samples:] = y_step[:-shift_samples]

    pulse = y_step - y_shifted
    return t_step, pulse


def pulse_response_from_freq_response(response_fn, ui: float, dt: float, n_ui_total: int):
    """
    Igual que compute_pulse_response(), pero para una respuesta en
    frecuencia ARBITRARIA (no necesariamente una función de transferencia
    racional) -- necesario para el caso de un CTLE 'measured' (curva
    importada, sin polos/ceros conocidos). Vía FFT: se obtiene la
    respuesta al impulso por irfft, se integra para obtener la respuesta
    al escalón, y se resta desplazada 1 UI (mismo truco que la vía
    analítica) para obtener la respuesta al pulso.
    """
    n = int(n_ui_total * ui / dt)
    freqs = np.fft.rfftfreq(n, d=dt)
    H = response_fn(freqs)
    # el factor 1/dt convierte la respuesta en frecuencia CONTINUA (lo que
    # devuelve response_fn) a la respuesta al impulso DISCRETA muestreada
    # cada dt -- sin este factor, h sale sistematicamente chico por ~dt
    # (verificado numericamente contra compute_pulse_response via scipy.step)
    h = np.fft.irfft(H, n=n) / dt
    step = np.cumsum(h) * dt

    shift_samples = int(round(ui / dt))
    step_shifted = np.zeros_like(step)
    step_shifted[shift_samples:] = step[:-shift_samples]
    pulse = step - step_shifted

    t = np.arange(n) * dt
    return t, pulse


def plot_pulse_response(t, pulse, ui, outpath, label="Respuesta al pulso"):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(t * 1e9, pulse, color="steelblue")
    ax.set_xlabel("Tiempo (ns)")
    ax.set_ylabel("Respuesta al pulso")
    ax.set_title(f"{label} (ancho = 1 UI = {ui*1e12:.1f} ps)")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"Guardado: {outpath}")


# ----------------------------------------------------------------------
# FFE (Tx Feed-Forward Equalizer): pre-cursor(es) + main + post-cursor(es)
# ----------------------------------------------------------------------

def build_ffe_taps(pre_taps: list, post_taps: list) -> np.ndarray:
    """
    Construye el vector de coeficientes del FFE a partir de las magnitudes
    de pre y post cursor (positivas, las que elegís vos). El tap principal
    se calcula por NORMALIZACIÓN: main = 1 - sum(|pre|) - sum(|post|), y
    pre/post se aplican con signo NEGATIVO (de-énfasis) -- misma
    convención que serdes_functions.py (PCIe-style).

    Orden del vector devuelto: [-pre_n, ..., -pre_1, main, -post_1, ..., -post_m]
    """
    pre_taps = list(pre_taps)
    post_taps = list(post_taps)

    for tap in pre_taps + post_taps:
        if not (0 <= tap <= 0.4):
            raise ValueError(f"Tap FFE fuera de rango [0, 0.4]: {tap}")

    main_tap = 1.0 - sum(pre_taps) - sum(post_taps)
    if main_tap <= 0:
        raise ValueError(
            f"El tap principal calculado (1 - suma de pre/post) es {main_tap:.4f} <= 0 -- "
            f"la suma de tus taps pre/post cursor es demasiado grande."
        )

    taps = [-t for t in reversed(pre_taps)] + [main_tap] + [-t for t in post_taps]
    return np.array(taps)


def apply_ffe(pulse_response: np.ndarray, samples_per_symbol: int, ffe_taps: np.ndarray) -> np.ndarray:
    """
    Aplica el FFE convolucionando su secuencia de taps (cada uno separado
    por 1 UI = samples_per_symbol muestras) con la respuesta al pulso del
    canal -- equivalente exacto a pre-distorsionar la señal de entrada con
    el FFE antes de pasar por el canal (el canal es LTI, así que da lo
    mismo el orden), y es la misma operación que hace serdes_functions.py
    (fftconvolve(ir, taps_repetidos)).

    No hace falta realinear el resultado a mano: channel_coefficients()
    y wc_eye_height() ubican el cursor principal buscando el máximo,
    así que funcionan igual sobre la respuesta ecualizada.
    """
    taps_upsampled = np.zeros((len(ffe_taps) - 1) * samples_per_symbol + 1)
    taps_upsampled[::samples_per_symbol] = ffe_taps
    return signal.fftconvolve(pulse_response, taps_upsampled, mode="full")


def compute_ffe_response(ffe_taps: np.ndarray, n_pre_taps: int, ui: float, freqs: np.ndarray) -> np.ndarray:
    """
    Respuesta en frecuencia del FFE: como es un FIR discreto (cada tap
    separado 1 UI), su respuesta es la DTFT de los coeficientes --
    H_FFE(f) = sum_k tap[k] * exp(-j*2*pi*f*k*UI), con k=0 en el tap
    principal (positivo hacia postcursores, negativo hacia precursores).
    Esto es lo que genera el peaking cerca de Nyquist según los valores
    de pre/post que elijas -- coeficientes de-énfasis (pre/post
    negativos) típicamente realzan las frecuencias altas.
    """
    k = np.arange(len(ffe_taps)) - n_pre_taps
    # exp(-j*2*pi*f*k*UI) para cada combinación (freqs x k), sumado sobre k
    phase = -2j * np.pi * np.outer(freqs, k) * ui
    return np.sum(ffe_taps[np.newaxis, :] * np.exp(phase), axis=1)


# ----------------------------------------------------------------------
# CTLE: fuente de la respuesta -- analítica (2 polos + 1 cero) o medida
# (por ejemplo, extraída de un .AC de ngspice sobre el circuito real de
# transistores) -- ambas terminan siendo simplemente H(f), así que se
# combinan igual sin importar el origen.
# ----------------------------------------------------------------------

def load_measured_response(csv_path: str):
    """
    Carga una respuesta en frecuencia MEDIDA/SIMULADA desde un CSV con
    columnas: freq_hz, mag_db, phase_deg (una fila de encabezado, en ese
    orden). Pensado para pegar directo la salida de un .AC de ngspice
    sobre el circuito real de transistores del CTLE.

    Devuelve una función freqs -> H(freqs) (complejo), por interpolación
    lineal de magnitud (dB) y fase (grados) sobre la grilla medida.

    IMPORTANTE: fuera del rango de frecuencias del CSV, la respuesta se
    lleva a CERO (no se mantiene constante el último valor) -- si no,
    al usar esto con la síntesis vía FFT (que necesita frecuencias hasta
    el Nyquist de la grilla temporal, típicamente cientos de GHz) se
    fabricaría energía de alta frecuencia no física, contaminando la
    respuesta al pulso resultante.
    """
    data = np.genfromtxt(csv_path, delimiter=",", skip_header=1)
    freq_meas, mag_db_meas, phase_deg_meas = data[:, 0], data[:, 1], data[:, 2]
    f_min, f_max = freq_meas.min(), freq_meas.max()

    def response_fn(freqs: np.ndarray) -> np.ndarray:
        mag_db = np.interp(freqs, freq_meas, mag_db_meas)
        phase_deg = np.interp(freqs, freq_meas, phase_deg_meas)
        mag = 10 ** (mag_db / 20)
        phase = np.deg2rad(phase_deg)
        H = mag * np.exp(1j * phase)
        H = np.where(freqs > f_max, 0.0, H)
        return H

    return response_fn


def get_ctle_response_fn(args, f_nyquist: float):
    """
    Dispatcher: devuelve (response_fn, info_o_None, descripcion) según
    --ctle-model.
      'analytic' usa build_ctle_tf (parámetros gmN/RL/CLtot/Rs/Cs/gdsN)
      'measured' carga --ctle-response-csv
      'gains'    usa build_ctle_tf_from_gains (DC gain, Boost, fp2,
                 con wp1 en --ctle-pole1-frac * Nyquist/boost)
    info es el dict de wz/wp1/wp2/etc si es analítico o gains, None si
    es medido (no tiene sentido reportar polos/ceros de una curva medida).
    """
    if args.ctle_model == "measured":
        if not args.ctle_response_csv:
            raise ValueError("--ctle-model measured requiere --ctle-response-csv")
        response_fn = load_measured_response(args.ctle_response_csv)
        return response_fn, None, f"medido ({args.ctle_response_csv})"
    elif args.ctle_model == "gains":
        if None in (args.ctle_dcgain_db, args.ctle_boost_db, args.ctle_fp2):
            raise ValueError("--ctle-model gains requiere --ctle-dcgain-db, --ctle-boost-db y --ctle-fp2")
        ctle_tf, info = build_ctle_tf_from_gains(args.ctle_dcgain_db, args.ctle_boost_db,
                                                  f_nyquist, args.ctle_fp2, args.ctle_pole1_frac)

        def response_fn(freqs):
            return compute_ac_response(ctle_tf, freqs)

        return response_fn, info, "por ganancias (DCgain + Boost + fp2, wp1 por debajo de Nyquist)"
    else:
        ctle_tf, info = build_ctle_tf(args.ctle_gmn, args.ctle_rl, args.ctle_cltot,
                                       args.ctle_rs, args.ctle_cs, args.ctle_gdsn)

        def response_fn(freqs):
            return compute_ac_response(ctle_tf, freqs)

        return response_fn, info, "analítico (2 polos + 1 cero, componentes)"


def plot_combined_ac_response(freqs: np.ndarray, curves: dict, nyquist_freq: float, outpath: str):
    """curves: dict {etiqueta: H(freqs) complejo} -- grafica todas juntas
    en dB, marcando Nyquist."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for label, H in curves.items():
        ax.plot(freqs / 1e9, 20 * np.log10(np.abs(H) + 1e-30), label=label)

    ax.axvline(nyquist_freq / 1e9, color="gray", linestyle=":", linewidth=1,
               label=f"Nyquist ({nyquist_freq/1e9:.3f} GHz)")
    ax.set_xlabel("Frecuencia (GHz)")
    ax.set_ylabel("|H(f)| (dB)")
    ax.set_title("Respuesta en AC combinada: Canal, +FFE, +FFE+CTLE")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"Guardado: {outpath}")


# ----------------------------------------------------------------------
# Coeficientes de canal y Worst Case Eye Height
# (portado 1:1 de serdes_functions.py, sin dependencias externas)
# ----------------------------------------------------------------------

def channel_coefficients(pulse_response: np.ndarray, samples_per_symbol: int,
                          n_precursors: int, n_postcursors: int) -> np.ndarray:
    """Muestrea la respuesta al pulso en múltiplos de UI alrededor del
    cursor principal (el pico). Devuelve n_precursors + 1 + n_postcursors
    coeficientes."""
    n_cursors = n_precursors + n_postcursors + 1
    coeffs = np.zeros(n_cursors)

    max_idx = int(np.argmax(pulse_response))

    for cursor in range(n_cursors):
        a = cursor - n_precursors
        idx = max_idx + a * samples_per_symbol
        coeffs[cursor] = pulse_response[idx] if 0 <= idx < len(pulse_response) else 0.0

    return coeffs


def wc_eye_height(pulse_response: np.ndarray, samples_per_symbol: int,
                   n_precursors: int, n_postcursors: int) -> float:
    """Worst Case Eye Height por el método de coeficientes: agrupa todos
    los coeficientes de ISI negativos (que cierran el '1') por un lado, y
    los positivos (que cierran el '0') por otro, y calcula la apertura
    resultante en el peor patrón de bits posible. Positivo = ojo abierto,
    negativo = ojo cerrado.

    CORREGIDO respecto a la primera versión: antes se pedían
    n_precursors+1 coeficientes pero solo se sumaban n_precursors,
    excluyendo sin querer el precursor más cercano al cursor principal
    de la cuenta. Ahora se usan y suman TODOS los n_precursors +
    n_postcursors coeficientes, sin excluir ninguno."""
    ch_coeff = channel_coefficients(pulse_response, samples_per_symbol,
                                     n_precursors, n_postcursors)

    pulse_peak = ch_coeff[n_precursors]
    WC0, WC1 = 0.0, 0.0

    for x in range(n_precursors):
        if ch_coeff[x] < 0:
            WC1 += ch_coeff[x]
        else:
            WC0 += ch_coeff[x]

    for x in range(n_postcursors):
        val = ch_coeff[n_precursors + 1 + x]
        if val < 0:
            WC1 += val
        else:
            WC0 += val

    return 2 * (pulse_peak + WC1 - WC0)


def build_worst_case_bit_pattern(pulse_response: np.ndarray, samples_per_symbol: int,
                                  n_precursors: int, n_postcursors: int):
    """
    Construye la secuencia de bits (bipolar, +-1) que genera EXACTAMENTE
    el Worst Case Eye Height calculado por wc_eye_height().

    DETALLE IMPORTANTE (no trivial): la contribución del bit transmitido
    en la posición j al valor muestreado en la posición principal NO es
    ch_coeff[j] -- es ch_coeff[2*main_idx - j] (el coeficiente
    "espejado"). Esto sale de la superposición: r(t_main) = sum_j b[j] *
    p(t_main - T_j), y p evaluado 'hacia atrás' desde su propio pico es
    el coeficiente con el índice reflejado, no el mismo. Como
    n_precursors y n_postcursors suelen ser distintos (asimétrico), para
    poder espejar sin salirnos de rango se recalculan los coeficientes
    con un rango SIMÉTRICO (usando el máximo de ambos a cada lado) antes
    de construir el patrón -- el cálculo NUMÉRICO de wc_eye_height() no
    se toca, esto es solo para la síntesis de la forma de onda.

    Devuelve (bit_pattern, ch_coeff, main_idx) -- bit_pattern y ch_coeff
    tienen la MISMA longitud e indexado (útil para sintetizar la forma
    de onda con synthesize_worst_case_waveform).
    """
    n_sym = max(n_precursors, n_postcursors)
    ch_coeff = channel_coefficients(pulse_response, samples_per_symbol, n_sym, n_sym)
    main_idx = n_sym

    bit_pattern = np.zeros(len(ch_coeff))
    bit_pattern[main_idx] = 1.0
    for j in range(len(ch_coeff)):
        if j == main_idx:
            continue
        mirrored_idx = 2 * main_idx - j
        coeff_val = ch_coeff[mirrored_idx]
        bit_pattern[j] = 1.0 if coeff_val < 0 else -1.0

    return bit_pattern, ch_coeff, main_idx


def synthesize_worst_case_waveform(pulse_response: np.ndarray, samples_per_symbol: int,
                                    bit_pattern: np.ndarray, main_idx: int, ui_window: float = 2.0):
    """
    Sintetiza la forma de onda continua para la secuencia de bits dada,
    por superposición de copias desplazadas y escaladas de la respuesta
    al pulso (el canal es LTI) -- sin necesidad de ngspice. Devuelve
    (grid_in_ui, waveform) recortado a +-ui_window/2 UI alrededor del
    cursor principal, mismo formato que usa eye_diagram.py.
    """
    n = len(pulse_response)
    n_precursors_in_array = main_idx
    n_postcursors_in_array = len(bit_pattern) - main_idx - 1

    pad_left = n_precursors_in_array * samples_per_symbol
    pad_right = n_postcursors_in_array * samples_per_symbol
    total = np.zeros(pad_left + n + pad_right)

    for k, bit in enumerate(bit_pattern):
        a = k - main_idx
        shift = pad_left + a * samples_per_symbol
        total[shift:shift + n] += bit * pulse_response

    max_idx_local = int(np.argmax(pulse_response))
    center = pad_left + max_idx_local

    half_win = int(round(ui_window / 2 * samples_per_symbol))
    lo, hi = center - half_win, center + half_win
    window = total[max(lo, 0):min(hi, len(total))]

    grid_in_ui = (np.arange(len(window)) - (center - max(lo, 0))) / samples_per_symbol
    return grid_in_ui, window


def plot_worst_case_eye(pulse_response: np.ndarray, samples_per_symbol: int,
                         n_precursors: int, n_postcursors: int, wceh: float, outpath: str,
                         overlay_npz: str = None, vdd: float = None):
    """
    Si se pasa 'vdd', reescala las trazas (que salen en convención BIPOLAR
    +-1, la misma que usa la síntesis) a la convención UNIPOLAR 0..VDD que
    usan las simulaciones reales de ngspice (mapeo: unipolar = VDD/2*(1+
    bipolar), la misma transformación que hace 'sgn(V)*VDD/2+VDD/2' en
    los netlists) -- necesario para que la superposición con un eye_*.npz
    real tenga sentido visual (si no, quedan en escalas distintas).
    """
    bit_pattern_1, ch_coeff, main_idx = build_worst_case_bit_pattern(
        pulse_response, samples_per_symbol, n_precursors, n_postcursors)
    bit_pattern_0 = -bit_pattern_1  # simetría bipolar: el peor '0' es el complemento del peor '1'

    grid1, wave1 = synthesize_worst_case_waveform(pulse_response, samples_per_symbol, bit_pattern_1, main_idx)
    grid0, wave0 = synthesize_worst_case_waveform(pulse_response, samples_per_symbol, bit_pattern_0, main_idx)

    scale = 1.0
    if vdd is not None:
        wave1 = vdd / 2 * (1 + wave1)
        wave0 = vdd / 2 * (1 + wave0)
        scale = vdd / 2  # el gap/WCEH tambien se reescala (sin el offset de +1, que se cancela al restar)

    fig, ax = plt.subplots(figsize=(10, 6))

    if overlay_npz and os.path.isfile(overlay_npz):
        data = np.load(overlay_npz, allow_pickle=True)
        grid_bg, matrix_bg = data["grid_in_ui"], data["matrix"]
        for row in matrix_bg:
            ax.plot(grid_bg, row, color="lightgray", alpha=0.25, linewidth=0.6, zorder=1)
        ax.plot([], [], color="gray", alpha=0.6, label="PRBS real (ngspice, referencia)")
        if vdd is None:
            print("Aviso: superponiendo sobre datos de ngspice (0..VDD) sin pasar --vdd -- "
                  "las escalas probablemente no coincidan. Pasá --vdd para reescalar.")

    ax.plot(grid1, wave1, color="firebrick", linewidth=2, label="Peor caso '1'", zorder=3)
    ax.plot(grid0, wave0, color="steelblue", linewidth=2, label="Peor caso '0'", zorder=3)

    ax.axvline(0.0, color="green", linestyle=":", linewidth=1, alpha=0.7, label="centro (instante de muestreo)")

    level_1 = wave1[np.argmin(np.abs(grid1))]
    level_0 = wave0[np.argmin(np.abs(grid0))]
    full_gap = level_1 - level_0
    wceh_scaled = wceh * scale
    ax.scatter([0, 0], [level_1, level_0], color="black", zorder=5)
    units = "V" if vdd is not None else "(unidades del pulso)"
    ax.annotate(
        f"gap medido = {full_gap:.4f} {units}\n"
        f"WC eye height (fórmula) = {wceh_scaled:.4f} {units}",
        xy=(0, (level_1 + level_0) / 2), xytext=(15, 0), textcoords="offset points",
        fontsize=8, va="center")

    ax.set_xlabel("Tiempo (UI, 0 = cursor principal)")
    ax.set_ylabel("Amplitud (V)" if vdd is not None else "Amplitud (unidades del pulso de entrada)")
    ax.set_title(f"Ojo de peor caso (determinístico) — WC eye height = {wceh_scaled:.4f} {units}")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"Guardado: {outpath}")


def plot_channel_coefficients(coeffs: np.ndarray, n_precursors: int, outpath: str):
    idx = np.arange(-n_precursors, len(coeffs) - n_precursors)
    colors = ["firebrick" if i == 0 else ("steelblue" if c >= 0 else "darkorange")
              for i, c in zip(idx, coeffs)]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(idx, coeffs, color=colors, width=0.6)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Cursor (n, en UI relativo al pico)")
    ax.set_ylabel("Coeficiente de canal")
    ax.set_title("Coeficientes de canal (rojo = principal, naranja = ISI negativa, azul = ISI positiva)")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"Guardado: {outpath}")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sp_path", help="Ruta al channel_model.sp generado por channel_model_generator.py")
    parser.add_argument("--datarate", type=str, required=True, help="Datarate NRZ, ej. '1e9' (1Gbps)")
    parser.add_argument("--fp1", type=str, default=None, help="Override manual de fp1 (si no se puede leer del .sp)")
    parser.add_argument("--fp2", type=str, default=None, help="Override manual de fp2")
    parser.add_argument("--loss-dc", type=float, default=None, help="Override manual de loss_dc (dB)")
    parser.add_argument("--n-stages", type=int, default=None, help="Override manual de n_stages")
    parser.add_argument("--n-precursors", type=int, default=10, help="Cantidad de precursores a considerar (default: 10)")
    parser.add_argument("--n-postcursors", type=int, default=100, help="Cantidad de postcursores a considerar (default: 100)")
    parser.add_argument("--ffe-pre", type=float, nargs="*", default=[],
                         help="Magnitudes (positivas, 0 a 0.4) de los taps FFE pre-cursor, de más lejano a más "
                              "cercano al cursor principal. Ej: --ffe-pre 0.05 0.15 para 2 precursores.")
    parser.add_argument("--ffe-post", type=float, nargs="*", default=[],
                         help="Magnitudes (positivas, 0 a 0.4) de los taps FFE post-cursor, del más cercano al "
                              "más lejano. Ej: --ffe-post 0.25 para 1 postcursor.")
    parser.add_argument("--outdir", default="pulse_analysis", help="Directorio de salida")
    parser.add_argument("--plot-worst-case-eye", action="store_true",
                         help="Genera el diagrama de ojo de peor caso determinístico (la secuencia de bits "
                              "exacta que produce el WC eye height calculado)")
    parser.add_argument("--overlay-eye-npz", type=str, default=None,
                         help="Ruta a un eye_folded_data.npz generado por eye_diagram.py (PRBS real vía "
                              "ngspice), para superponerlo de fondo como referencia visual del caso típico")
    parser.add_argument("--vdd", type=float, default=None,
                         help="VDD real del circuito (V). Si se pasa, reescala las trazas de bipolar +-1 a "
                              "unipolar 0..VDD -- necesario para que --overlay-eye-npz (datos de ngspice, "
                              "en Volts reales) se superponga en la misma escala.")
    parser.add_argument("--ctle-gmn", type=float, default=None, help="CTLE: gm del transistor NMOS (S)")
    parser.add_argument("--ctle-rl", type=float, default=None, help="CTLE: resistencia de carga RL (Ohm)")
    parser.add_argument("--ctle-cltot", type=float, default=None, help="CTLE: capacidad total de carga CLtot (F)")
    parser.add_argument("--ctle-rs", type=float, default=None, help="CTLE: resistencia de degeneración Rs (Ohm)")
    parser.add_argument("--ctle-cs", type=float, default=None, help="CTLE: capacidad de degeneración Cs (F)")
    parser.add_argument("--ctle-gdsn", type=float, default=0.0,
                         help="CTLE: conductancia de salida del NMOS gdsN (S). Default: 0 (ideal, sin gdsN)")
    parser.add_argument("--ctle-model", choices=["analytic", "measured", "gains"], default="analytic",
                         help="Fuente de la respuesta del CTLE: 'analytic' (2 polos+1 cero, parámetros "
                              "--ctle-gmn/rl/cltot/rs/cs/gdsn), 'measured' (CSV externo), o 'gains' "
                              "(DC gain + Boost + fp2, con wp1 por debajo de Nyquist). Default: analytic.")
    parser.add_argument("--ctle-response-csv", type=str, default=None,
                         help="Ruta al CSV (freq_hz,mag_db,phase_deg) con la respuesta medida/simulada del "
                              "CTLE. Requerido si --ctle-model measured.")
    parser.add_argument("--ctle-dcgain-db", type=float, default=None,
                         help="CTLE (modo 'gains'): ganancia de DC, en dB")
    parser.add_argument("--ctle-boost-db", type=float, default=None,
                         help="CTLE (modo 'gains'): Boost = AC gain - DC gain, en dB")
    parser.add_argument("--ctle-fp2", type=float, default=None,
                         help="CTLE (modo 'gains'): frecuencia del polo de salida fp2, en Hz")
    parser.add_argument("--ctle-pole1-frac", type=float, default=1.0,
                         help="CTLE (modo 'gains'): wp1 se coloca en pole1_frac * (2*pi*f_nyquist/boost_ratio). "
                              "Default: 1.0 (coincide con la fórmula wp1=2*pi*fnyq/boost_ratio).")
    parser.add_argument("--ctle-estimate-gmn", type=float, default=None,
                         help="Si se pasa (junto con --ctle-model gains), estima Rs/Cs/RL/CLtot del circuito "
                              "de transistores asumiendo este valor de gmN (S). Ver print_estimated_params "
                              "para la explicación de por qué hace falta asumir gmN.")
    args = parser.parse_args()


    os.makedirs(args.outdir, exist_ok=True)
    datarate = parse_eng(args.datarate)
    ui = 1.0 / datarate

    if None in (args.fp1, args.fp2, args.loss_dc, args.n_stages):
        try:
            fp1_auto, fp2_auto, loss_dc_auto, n_stages_auto = parse_channel_sp(args.sp_path)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        fp1 = parse_eng(args.fp1) if args.fp1 is not None else fp1_auto
        fp2 = parse_eng(args.fp2) if args.fp2 is not None else fp2_auto
        loss_dc_db = args.loss_dc if args.loss_dc is not None else loss_dc_auto
        n_stages = args.n_stages if args.n_stages is not None else n_stages_auto
    else:
        fp1, fp2 = parse_eng(args.fp1), parse_eng(args.fp2)
        loss_dc_db, n_stages = args.loss_dc, args.n_stages

    print(f"Canal: fp1={fp1/1e9:.4f}GHz  fp2={fp2/1e9:.4f}GHz  loss_dc={loss_dc_db:.3f}dB  "
          f"n_stages={n_stages}  UI={ui*1e12:.2f}ps (datarate={datarate:.3e})\n")

    tf = build_channel_tf(fp1, fp2, loss_dc_db, n_stages)

    # --- respuesta en AC (del canal solo, el FFE no se puede ver acá sin
    # convertirlo tambien a una funcion de transferencia -- se deja para
    # cuando agreguemos CTLE, que sí es más natural verlo en AC) ---
    plot_ac_response(tf, fp2 * 3, os.path.join(args.outdir, "ac_response.png"))

    # --- respuesta al pulso del canal solo ---
    dt = ui / 200  # 200 muestras por UI, suficiente resolución
    n_ui_total = args.n_precursors + args.n_postcursors + 20
    t, pulse = compute_pulse_response(tf, ui, dt, n_ui_total)
    plot_pulse_response(t, pulse, ui, os.path.join(args.outdir, "pulse_response.png"))
    samples_per_symbol = int(round(ui / dt))

    def report(pulse_response, label, fname_suffix):
        coeffs = channel_coefficients(pulse_response, samples_per_symbol, args.n_precursors, args.n_postcursors)
        plot_channel_coefficients(coeffs, args.n_precursors,
                                   os.path.join(args.outdir, f"channel_coefficients{fname_suffix}.png"))
        wceh = wc_eye_height(pulse_response, samples_per_symbol, args.n_precursors, args.n_postcursors)
        print(f"--- {label} ---")
        print(f"Cursor principal (n=0): {coeffs[args.n_precursors]:.6f}")
        print(f"Suma |precursores|+|postcursores| (ISI total): "
              f"{np.sum(np.abs(coeffs)) - abs(coeffs[args.n_precursors]):.6f}")
        print(f"WORST CASE EYE HEIGHT: {wceh:.6f}  ({'OJO ABIERTO' if wceh > 0 else 'OJO CERRADO'})\n")

        if args.plot_worst_case_eye:
            plot_worst_case_eye(pulse_response, samples_per_symbol, args.n_precursors, args.n_postcursors,
                                 wceh, os.path.join(args.outdir, f"worst_case_eye{fname_suffix}.png"),
                                 overlay_npz=args.overlay_eye_npz, vdd=args.vdd)
        return wceh

    print("=" * 60)
    print("SOLO CANAL (sin ecualizar)")
    print("=" * 60)
    report(pulse, "Canal solo", "")

    ffe_given = bool(args.ffe_pre or args.ffe_post)
    ctle_given = (
        (args.ctle_model == "measured" and args.ctle_response_csv is not None) or
        (args.ctle_model == "gains" and
         None not in (args.ctle_dcgain_db, args.ctle_boost_db, args.ctle_fp2)) or
        (args.ctle_model == "analytic" and
         None not in (args.ctle_gmn, args.ctle_rl, args.ctle_cltot, args.ctle_rs, args.ctle_cs))
    )

    ffe_taps = None
    if ffe_given:
        try:
            ffe_taps = build_ffe_taps(args.ffe_pre, args.ffe_post)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Taps FFE aplicados: {ffe_taps}  (orden: [pre...  main  ...post])\n")

    ctle_response_fn, ctle_info, ctle_desc = (None, None, None)
    if ctle_given:
        ctle_response_fn, ctle_info, ctle_desc = get_ctle_response_fn(args, datarate / 2)
        print("=" * 60)
        print(f"CTLE ({ctle_desc})")
        print("=" * 60)
        if ctle_info is not None:
            print_ctle_info(ctle_info)
        else:
            print("(respuesta importada, sin polos/ceros analíticos que reportar)\n")

        if args.ctle_model == "gains" and args.ctle_estimate_gmn is not None:
            est = estimate_transistor_params(ctle_info["dc_gain"], ctle_info["ac_gain"],
                                              ctle_info["wz"], ctle_info["wp1"], ctle_info["wp2"],
                                              args.ctle_estimate_gmn)
            print_estimated_params(est)

    # --- respuesta en AC combinada: Canal, +FFE, +FFE+CTLE (o +CTLE si no hay FFE) ---
    if ffe_given or ctle_given:
        freqs_ac = np.linspace(1e6, fp2 * 3, 2000)
        H_channel = compute_ac_response(tf, freqs_ac)
        curves = {"Canal": H_channel}
        H_running = H_channel

        if ffe_given:
            H_ffe = compute_ffe_response(ffe_taps, len(args.ffe_pre), ui, freqs_ac)
            H_running = H_running * H_ffe
            curves["Canal + FFE"] = H_running

        if ctle_given:
            H_ctle = ctle_response_fn(freqs_ac)
            H_running = H_running * H_ctle
            label = "Canal + FFE + CTLE" if ffe_given else "Canal + CTLE"
            curves[label] = H_running

        plot_combined_ac_response(freqs_ac, curves, datarate / 2,
                                   os.path.join(args.outdir, "ac_response_combined.png"))

    # --- Canal + CTLE (sin FFE) en el dominio del tiempo ---
    pulse_channel_ctle = pulse
    if ctle_given:
        if args.ctle_model == "analytic":
            ctle_tf, _ = build_ctle_tf(args.ctle_gmn, args.ctle_rl, args.ctle_cltot,
                                        args.ctle_rs, args.ctle_cs, args.ctle_gdsn)
            tf_channel_ctle = cascade_tf(tf, ctle_tf)
            t_ctle, pulse_channel_ctle = compute_pulse_response(tf_channel_ctle, ui, dt, n_ui_total)
        elif args.ctle_model == "gains":
            ctle_tf, _ = build_ctle_tf_from_gains(args.ctle_dcgain_db, args.ctle_boost_db,
                                                   datarate / 2, args.ctle_fp2, args.ctle_pole1_frac)
            tf_channel_ctle = cascade_tf(tf, ctle_tf)
            t_ctle, pulse_channel_ctle = compute_pulse_response(tf_channel_ctle, ui, dt, n_ui_total)
        else:
            def combined_fn(freqs):
                return compute_ac_response(tf, freqs) * ctle_response_fn(freqs)
            t_ctle, pulse_channel_ctle = pulse_response_from_freq_response(combined_fn, ui, dt, n_ui_total)

        plot_pulse_response(t_ctle, pulse_channel_ctle, ui,
                             os.path.join(args.outdir, "pulse_response_ctle.png"),
                             label="Respuesta al pulso — Canal + CTLE")

        print("=" * 60)
        print("CANAL + CTLE")
        print("=" * 60)
        report(pulse_channel_ctle, "Canal + CTLE", "_ctle")

    # --- Canal + FFE (y +CTLE si corresponde) en el dominio del tiempo ---
    if ffe_given:
        pulse_ffe = apply_ffe(pulse, samples_per_symbol, ffe_taps)
        plot_pulse_response(t[:len(pulse_ffe)] if len(t) >= len(pulse_ffe) else
                             np.arange(len(pulse_ffe)) * dt,
                             pulse_ffe, ui, os.path.join(args.outdir, "pulse_response_ffe.png"),
                             label="Respuesta al pulso — Canal + FFE")

        print("=" * 60)
        print("CANAL + FFE")
        print("=" * 60)
        report(pulse_ffe, "Canal + FFE", "_ffe")

        if ctle_given:
            pulse_ffe_ctle = apply_ffe(pulse_channel_ctle, samples_per_symbol, ffe_taps)
            plot_pulse_response(np.arange(len(pulse_ffe_ctle)) * dt, pulse_ffe_ctle, ui,
                                 os.path.join(args.outdir, "pulse_response_ffe_ctle.png"),
                                 label="Respuesta al pulso — Canal + FFE + CTLE")

            print("=" * 60)
            print("CANAL + FFE + CTLE")
            print("=" * 60)
            report(pulse_ffe_ctle, "Canal + FFE + CTLE", "_ffe_ctle")

    print("(los valores de WC eye height están en las mismas unidades que la amplitud del pulso de entrada -- ")
    print(" si tu señal real tiene swing +/-A, multiplicá el resultado por A)")


if __name__ == "__main__":
    main()
