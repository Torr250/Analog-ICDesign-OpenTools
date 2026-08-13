#!/usr/bin/env python3
"""
tline_model.py

Genera un modelo de línea de transmisión CON PÉRDIDA como un subcircuito
SPICE (cascada de secciones RLGC concentradas, topología Pi), a partir de
una especificación simple: impedancia característica (Z0), delay (TD), y
un punto de pérdida (loss_dB a freq_loss). Útil cuando ngspice no soporta
leer archivos .s2p/.s4p directamente.

Metodología:
  - L_total = Z0 * TD,  C_total = TD / Z0
    (de Z0 = sqrt(L'/C') y v = 1/sqrt(L'C'), integrados sobre toda la línea)
  - alpha_total [Np] = loss_dB / 8.686
  - R_total = 2 * Z0 * alpha_total * frac_conductor   (pérdida por conductor)
  - G_total = 2 * alpha_total * (1 - frac_conductor) / Z0   (pérdida dieléctrica)
    (aproximación de bajas pérdidas: alpha ~= R/(2*Z0) + G*Z0/2)

  Por default frac_conductor=1.0 (toda la pérdida se modela como R serie,
  el caso más común para trazas de PCB/interconexiones a frecuencias de
  hasta ~10-20 GHz). Ajustable con --dielectric-fraction si se quiere
  repartir parte de la pérdida como G en paralelo.

  IMPORTANTE — esto da un modelo de pérdida aproximadamente CONSTANTE en
  frecuencia (en Np/m), no el barrido real sqrt(f) (piel) o lineal (f,
  dieléctrico) de una línea física real. Es una aproximación de "banda
  angosta" centrada en freq_loss — buena cerca de esa frecuencia, menos
  precisa lejos de ella. Sirve perfectamente para ver el efecto
  cualitativo de la pérdida sobre el diagrama de ojo (ISI, cierre del
  ojo), que es lo que te interesa.

Uso:
    python3 tline_model.py --z0 50 --td 1n --loss-db 8 --freq-loss 2e9
    python3 tline_model.py --z0 50 --td 1n --loss-db 8 --freq-loss 2e9 --fmax 10e9 --n-sections auto
"""

import argparse
import sys

import numpy as np
import matplotlib.pyplot as plt


def parse_eng(s: str) -> float:
    """Convierte '1n', '2.5p', '3e9', etc. a float."""
    suffixes = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
                "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12}
    s = s.strip()
    for suf, mult in sorted(suffixes.items(), key=lambda x: -len(x[0])):
        if s.lower().endswith(suf):
            return float(s[:-len(suf)]) * mult
    return float(s)


def compute_rlgc_totals(z0: float, td: float, loss_db: float, dielectric_fraction: float = 0.0):
    alpha_total_np = loss_db / 8.686  # dB -> Np
    frac_conductor = 1.0 - dielectric_fraction

    l_total = z0 * td
    c_total = td / z0
    r_total = 2 * z0 * alpha_total_np * frac_conductor
    g_total = 2 * alpha_total_np * dielectric_fraction / z0 if dielectric_fraction > 0 else 0.0

    return {"R": r_total, "L": l_total, "G": g_total, "C": c_total}


def recommend_n_sections(td: float, fmax: float, points_per_wavelength: int = 20) -> int:
    """
    Regla práctica: cada sección de la escalera debe ser mucho más corta
    que la longitud de onda a la frecuencia máxima de interés, para que
    la aproximación concentrada siga pareciéndose a una línea distribuida.
    Con 'points_per_wavelength' secciones por período a fmax, el delay de
    cada sección (td/N) debe cumplir: N >= td * fmax * points_per_wavelength.
    """
    n = int(np.ceil(td * fmax * points_per_wavelength))
    return max(n, 4)


def generate_subckt(name: str, z0: float, td: float, loss_db: float, freq_loss: float,
                     n_sections: int, dielectric_fraction: float = 0.0) -> str:
    rlgc = compute_rlgc_totals(z0, td, loss_db, dielectric_fraction)
    R, L, G, C = rlgc["R"], rlgc["L"], rlgc["G"], rlgc["C"]

    r_seg, l_seg, g_seg, c_seg = R / n_sections, L / n_sections, G / n_sections, C / n_sections
    c_end = c_seg / 2.0  # los extremos de la escalera Pi llevan medio-C

    lines = []
    lines.append(f"* Modelo de linea de transmision con perdida, generado por tline_model.py")
    lines.append(f"* Especificacion: Z0={z0:.4f} Ohm, TD={td*1e9:.4f} ns, "
                 f"perdida={loss_db:.2f} dB @ {freq_loss/1e9:.3f} GHz")
    lines.append(f"* Totales:  R={R:.6f} Ohm  L={L*1e9:.6f} nH  "
                 f"G={G*1e6:.6f} uS  C={C*1e12:.6f} pF")
    lines.append(f"* {n_sections} secciones (topologia Pi): "
                 f"R_seg={r_seg:.6f} Ohm  L_seg={l_seg*1e12:.4f} pH  "
                 f"G_seg={g_seg*1e9:.4f} nS  C_seg={c_seg*1e15:.4f} fF")
    lines.append(f".subckt {name} in out")
    lines.append(f"Cend_in in 0 {c_end:.6e}")

    node_prev = "in"
    for i in range(1, n_sections + 1):
        node_next = "out" if i == n_sections else f"n{i}"
        lines.append(f"R{i} {node_prev} m{i} {r_seg:.6e}")
        lines.append(f"L{i} m{i} {node_next} {l_seg:.6e}")
        cap_val = c_end if i == n_sections else c_seg
        lines.append(f"C{i} {node_next} 0 {cap_val:.6e}")
        if g_seg > 0:
            lines.append(f"Rg{i} {node_next} 0 {1.0/g_seg:.6e}")
        node_prev = node_next

    lines.append(".ends")

    return "\n".join(lines) + "\n"


def ideal_line_s21_db(z0: float, td: float, loss_db_ref: float, freq_loss: float,
                       freqs: np.ndarray, dielectric_fraction: float = 0.0):
    """
    |S21| teorico (en dB) de la linea RLGC IDEAL (continua, no discretizada
    en secciones), asumiendo alpha constante en frecuencia (igual al
    supuesto del modelo). Sirve como referencia para comparar contra lo
    que de verdad va a medir ngspice sobre el subcircuito discretizado.
    Calculado con la matriz ABCD de una linea uniforme, terminada en Z0
    en ambos extremos (insertion loss verdadera).
    """
    rlgc = compute_rlgc_totals(z0, td, loss_db_ref, dielectric_fraction)
    R, L, G, C = rlgc["R"], rlgc["L"], rlgc["G"], rlgc["C"]

    omega = 2 * np.pi * freqs
    # parametros por-unidad no importan individualmente si usamos R,L,G,C
    # TOTALES junto con gamma*longitud_total = sqrt((R+jwL)(G+jwC)) evaluado
    # con los totales directamente (equivalente a longitud=1 normalizada)
    Zs = R + 1j * omega * L
    Ys = G + 1j * omega * C
    gamma_l = np.sqrt(Zs * Ys)  # gamma * longitud_total (ya que R,L,G,C son totales)
    Zc = np.sqrt(Zs / Ys)

    cosh_gl = np.cosh(gamma_l)
    sinh_gl = np.sinh(gamma_l)
    A = cosh_gl
    B = Zc * sinh_gl
    Cc = sinh_gl / Zc
    D = cosh_gl

    # S21 con terminaciones Z0 en ambos puertos (formula estandar ABCD->S)
    S21 = 2.0 / (A + B / z0 + Cc * z0 + D)
    return 20 * np.log10(np.abs(S21))


def plot_theoretical_response(z0, td, loss_db, freq_loss, dielectric_fraction, outpath, fmax_plot):
    freqs = np.linspace(1e6, fmax_plot, 500)
    s21_db = ideal_line_s21_db(z0, td, loss_db, freq_loss, freqs, dielectric_fraction)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(freqs / 1e9, s21_db, color="steelblue", label="modelo (alpha constante)")
    ax.scatter([freq_loss / 1e9], [-loss_db], color="red", zorder=5,
               label=f"spec: -{loss_db}dB @ {freq_loss/1e9:.2f}GHz")
    ax.set_xlabel("Frecuencia (GHz)")
    ax.set_ylabel("|S21| (dB)")
    ax.set_title("Respuesta teórica del modelo (línea ideal, terminada en Z0)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"Guardado: {outpath}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--z0", type=str, default="50", help="Impedancia característica (Ohm), default 50")
    parser.add_argument("--td", type=str, required=True, help="Delay eléctrico total, ej. '1n', '500p'")
    parser.add_argument("--loss-db", type=float, required=True, help="Pérdida (dB, positivo) a --freq-loss")
    parser.add_argument("--freq-loss", type=str, required=True, help="Frecuencia del punto de pérdida, ej. '2e9', '2g'")
    parser.add_argument("--dielectric-fraction", type=float, default=0.0,
                         help="Fracción de la pérdida atribuida a G (dieléctrico) en vez de R (conductor). "
                              "0.0 = toda la pérdida es R (default), 1.0 = toda es G.")
    parser.add_argument("--n-sections", type=str, default="auto",
                         help="Número de secciones de la escalera, o 'auto' para calcularlo (default: auto)")
    parser.add_argument("--fmax", type=str, default=None,
                         help="Frecuencia máxima de interés, para --n-sections auto y el gráfico "
                              "(default: 5x --freq-loss)")
    parser.add_argument("--name", default="LOSSY_TLINE", help="Nombre del subcircuito (default: LOSSY_TLINE)")
    parser.add_argument("--outfile", default="lossy_tline.sp", help="Archivo .sp de salida")
    parser.add_argument("--plot", default="tline_response_theoretical.png", help="Archivo del gráfico teórico")
    args = parser.parse_args()

    z0 = parse_eng(args.z0)
    td = parse_eng(args.td)
    freq_loss = parse_eng(args.freq_loss)
    fmax = parse_eng(args.fmax) if args.fmax else 5 * freq_loss

    if args.n_sections == "auto":
        n_sections = recommend_n_sections(td, fmax)
        print(f"N de secciones auto-calculado: {n_sections}  (para fmax={fmax/1e9:.2f}GHz)")
    else:
        n_sections = int(args.n_sections)

    subckt_text = generate_subckt(args.name, z0, td, args.loss_db, freq_loss,
                                   n_sections, args.dielectric_fraction)

    with open(args.outfile, "w") as f:
        f.write(subckt_text)
    print(f"\nSubcircuito guardado en: {args.outfile}")
    print(f"\n--- contenido ---\n{subckt_text}")

    plot_theoretical_response(z0, td, args.loss_db, freq_loss, args.dielectric_fraction,
                               args.plot, fmax)


if __name__ == "__main__":
    main()
