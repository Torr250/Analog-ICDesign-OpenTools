#!/usr/bin/env python3
"""
pvt_runner.py

Corre el barrido PVT completo (corner x temp x VDD): genera un netlist por
combinación a partir de un template, corre ngspice, recolecta los .meas
escalares en un CSV, y guarda un .raw único por combinación. También ofrece
comandos para comparar formas de onda entre esquinas.

Requiere:
    pip install spicelib --break-system-packages

Uso:
    # 1) Corre el barrido completo (genera CSV + .raw por combinación)
    python3 pvt_runner.py sweep
    python3 pvt_runner.py sweep --jobs 8      # 8 combinaciones en paralelo

    # 2) Genera una comparación de formas de onda entre esquinas, para una
    #    temperatura y VDD fijos (por defecto: temp nominal / vdd nominal)
    python3 pvt_runner.py compare
    python3 pvt_runner.py compare --temp 125 --vdd 3.0
    python3 pvt_runner.py compare --corners typical ss ff

    # 3) Grafica TODAS las combinaciones PVT juntas en una sola figura
    #    (color = corner, línea = VDD, opacidad = temperatura)
    python3 pvt_runner.py compare-all
    python3 pvt_runner.py compare-all --signals "v(outb)" "v(in)"
    python3 pvt_runner.py compare-all --corners typical ss ff --vdds 3.0 3.6
"""

import argparse
import csv
import itertools
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt

try:
    from spicelib.raw.raw_read import RawRead
except ImportError:
    RawRead = None

# ----------------------------------------------------------------------
# Configuración (igual que pvt_runner.py, mas el directorio de .raw)
# ----------------------------------------------------------------------

TEMPLATE = "TB_not_template.spice"
WORKDIR = "pvt_runs"
RAWDIR = "pvt_raws"
OUTPUT_CSV = "pvt_results.csv"
PLOTDIR = "pvt_analysis"

CORNERS = ["typical", "ff", "ss", "fs", "sf"]
TEMPS = [-40, 27, 125]
VDDS = [3.0, 3.3, 3.6]

MEAS_NAMES = ["trise", "tfall", "tplh", "tphl", "tpd_avg", "ivdd_rms", "effy"]

# Nombre del archivo .raw tal como aparece en el "write ..." del template original
TEMPLATE_RAW_NAME = "TB_not.raw"


# ----------------------------------------------------------------------
# Sweep: genera netlists, corre ngspice, guarda CSV + .raw
# ----------------------------------------------------------------------

def fmt_num(x: float) -> str:
    """Formatea un número igual sin importar si llega como int o float (27 y 27.0 -> '27')."""
    return str(int(x)) if float(x).is_integer() else str(x)


def raw_path_for(corner: str, temp: float, vdd: float) -> str:
    return os.path.join(RAWDIR, f"tb_not_{corner}_{fmt_num(temp)}C_{fmt_num(vdd)}V.raw")


def build_netlist(template_text: str, corner: str, temp: float, vdd: float, raw_path: str) -> str:
    """Sustituye corner, TEMP, VDD, y redirige el 'write' a un .raw único."""
    netlist = template_text.replace("__CORNER__", corner)
    netlist = re.sub(r"VDD=[\d.]+", f"VDD={vdd}", netlist)
    netlist = re.sub(r"TEMP=[\d.\-]+", f"TEMP={temp}", netlist)
    # Redirigimos el write TB_not.raw -> write pvt_raws/tb_not_<corner>_<temp>_<vdd>.raw
    netlist = netlist.replace(f"write {TEMPLATE_RAW_NAME}", f"write {raw_path}")
    return netlist


def run_ngspice(netlist_path: str) -> str:
    result = subprocess.run(["ngspice", "-b", netlist_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [!] ngspice devolvió código {result.returncode} para {netlist_path}", file=sys.stderr)
        if result.stderr:
            print(f"      stderr: {result.stderr.strip()[:300]}", file=sys.stderr)
    return result.stdout


def parse_meas(stdout: str, meas_name: str):
    match = re.search(rf"\b{meas_name}\s*=\s*([\d.eE+\-]+)", stdout)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def run_one(template_text: str, combo: tuple) -> dict:
    """Ejecuta UNA combinación PVT completa (netlist -> ngspice -> parseo) y
    devuelve todo lo necesario para reportar progreso y escribir el CSV.
    Esta función es la unidad de trabajo que se manda al pool de threads."""
    corner, temp, vdd = combo
    raw_path = raw_path_for(corner, temp, vdd)
    netlist = build_netlist(template_text, corner, temp, vdd, raw_path)

    fname = os.path.join(WORKDIR, f"tb_not_{corner}_{fmt_num(temp)}C_{fmt_num(vdd)}V.spice")
    with open(fname, "w") as f:
        f.write(netlist)

    stdout = run_ngspice(fname)

    log_fname = fname.replace(".spice", ".log")
    with open(log_fname, "w") as f:
        f.write(stdout)

    row = {"corner": corner, "temp": temp, "vdd": vdd}
    for meas in MEAS_NAMES:
        row[meas] = parse_meas(stdout, meas)
    missing = [m for m in MEAS_NAMES if row[m] is None]

    return {
        "combo": combo,
        "row": row,
        "missing": missing,
        "raw_path": raw_path,
        "log_fname": log_fname,
        "raw_ok": os.path.isfile(raw_path),
    }


def cmd_sweep(args):
    jobs = args.jobs

    if not os.path.isfile(TEMPLATE):
        print(f"Error: no se encontró el template '{TEMPLATE}' en el directorio actual.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(WORKDIR, exist_ok=True)
    os.makedirs(RAWDIR, exist_ok=True)

    with open(TEMPLATE, "r") as f:
        template_text = f.read()

    combinations = list(itertools.product(CORNERS, TEMPS, VDDS))
    total = len(combinations)
    # results indexado por posición para poder reordenar al final, ya que las
    # combinaciones paralelas no necesariamente terminan en el orden en que
    # itertools.product las generó
    results = [None] * total
    done = 0

    print(f"Corriendo {total} combinaciones PVT con {jobs} worker(s) en paralelo "
          f"(guardando .raw individual por corrida)...\n")

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(run_one, template_text, combo): idx
                    for idx, combo in enumerate(combinations)}

        for future in as_completed(futures):
            idx = futures[future]
            combo = combinations[idx]
            outcome = future.result()

            results[idx] = outcome["row"]
            done += 1

            corner, temp, vdd = combo
            if not outcome["raw_ok"]:
                print(f"    [!] {corner}/{temp}C/{vdd}V: no se generó el .raw esperado "
                      f"({outcome['raw_path']}); revisar {outcome['log_fname']}")
            if outcome["missing"]:
                print(f"    [!] {corner}/{temp}C/{vdd}V: no se pudo extraer "
                      f"{', '.join(outcome['missing'])} (revisar {outcome['log_fname']})")

            print(f"[{done}/{total}] corner={corner:8s} temp={temp:>4}C vdd={vdd}V completado")

    fieldnames = ["corner", "temp", "vdd"] + MEAS_NAMES
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nListo. {len(results)} corridas completadas.")
    print(f"  CSV de mediciones : {OUTPUT_CSV}")
    print(f"  Netlists + logs   : {WORKDIR}/")
    print(f"  Waveforms (.raw)  : {RAWDIR}/")


# ----------------------------------------------------------------------
# Compare: lee los .raw de varias esquinas (misma temp/vdd) y las superpone
# ----------------------------------------------------------------------

def load_waveform(raw_path: str, signal: str = "v(outb)"):
    """Devuelve (time, values) de una señal dentro de un .raw generado por ngspice."""
    if RawRead is None:
        raise RuntimeError(
            "spicelib no está instalado. Instalalo con:\n"
            "    pip install spicelib --break-system-packages"
        )
    raw = RawRead(raw_path, dialect="ngspice")
    time = raw.get_trace("time").get_wave()
    values = raw.get_trace(signal).get_wave()
    return time, values


def cmd_compare(args):
    corners = args.corners if args.corners else CORNERS
    temp = args.temp
    vdd = args.vdd
    signals = args.signals

    os.makedirs(PLOTDIR, exist_ok=True)

    missing_raws = []
    for corner in corners:
        rp = raw_path_for(corner, temp, vdd)
        if not os.path.isfile(rp):
            missing_raws.append(rp)
    if missing_raws:
        print("Error: no se encontraron estos .raw (¿corriste 'sweep' primero con estos mismos temp/vdd?):",
              file=sys.stderr)
        for rp in missing_raws:
            print(f"  - {rp}", file=sys.stderr)
        sys.exit(1)

    for signal in signals:
        fig, ax = plt.subplots(figsize=(9, 5))
        for corner in corners:
            rp = raw_path_for(corner, temp, vdd)
            time, values = load_waveform(rp, signal=signal)
            # tiempo en ns para que el eje sea legible
            ax.plot(time * 1e9, values, label=corner)

        ax.set_xlabel("Tiempo (ns)")
        ax.set_ylabel(f"{signal} (V)")
        ax.set_title(f"Comparación entre esquinas — {signal}  (temp={temp}°C, vdd={vdd}V)")
        ax.legend(title="Corner")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_signal = signal.replace("(", "").replace(")", "")
        fname = os.path.join(PLOTDIR, f"waveform_compare_{safe_signal}_{temp}C_{vdd}V.png")
        plt.savefig(fname, dpi=150)
        plt.close()
        print(f"Guardado: {fname}")


# ----------------------------------------------------------------------
# Compare-all: superpone TODOS los .raw generados (todas las combinaciones
# corner/temp/vdd) en una sola figura, codificando cada variable visualmente
# ----------------------------------------------------------------------

RAW_FILENAME_RE = re.compile(r"tb_not_(?P<corner>.+?)_(?P<temp>-?\d+(?:\.\d+)?)C_(?P<vdd>\d+(?:\.\d+)?)V\.raw$")

_LINESTYLES = ["-", "--", "-.", ":"]


def discover_raws(raw_dir: str):
    """Escanea raw_dir y devuelve una lista de dicts {path, corner, temp, vdd}
    parseados directamente del nombre de archivo generado por 'sweep'."""
    entries = []
    if not os.path.isdir(raw_dir):
        return entries
    for fname in sorted(os.listdir(raw_dir)):
        m = RAW_FILENAME_RE.search(fname)
        if not m:
            continue
        entries.append({
            "path": os.path.join(raw_dir, fname),
            "corner": m.group("corner"),
            "temp": float(m.group("temp")),
            "vdd": float(m.group("vdd")),
        })
    return entries


def cmd_compare_all(args):
    signals = args.signals
    raw_dir = args.raw_dir

    entries = discover_raws(raw_dir)
    if not entries:
        print(f"Error: no se encontraron .raw en '{raw_dir}/'. ¿Corriste 'sweep' primero?", file=sys.stderr)
        sys.exit(1)

    # filtros opcionales, por si no querés TODAS las combinaciones en el plot
    if args.corners:
        entries = [e for e in entries if e["corner"] in args.corners]
    if args.temps:
        entries = [e for e in entries if e["temp"] in args.temps]
    if args.vdds:
        entries = [e for e in entries if e["vdd"] in args.vdds]

    if not entries:
        print("Error: los filtros --corners/--temps/--vdds no dejaron ningún .raw para graficar.", file=sys.stderr)
        sys.exit(1)

    corners_present = sorted({e["corner"] for e in entries})
    vdds_present = sorted({e["vdd"] for e in entries})

    cmap = plt.get_cmap("tab10")
    color_for_corner = {c: cmap(i % 10) for i, c in enumerate(corners_present)}
    style_for_vdd = {v: _LINESTYLES[i % len(_LINESTYLES)] for i, v in enumerate(vdds_present)}

    # alpha en función de la temperatura: más caliente -> más opaco
    temps_present = sorted({e["temp"] for e in entries})
    if len(temps_present) > 1:
        tmin, tmax = min(temps_present), max(temps_present)
        alpha_for_temp = {t: 0.35 + 0.65 * (t - tmin) / (tmax - tmin) for t in temps_present}
    else:
        alpha_for_temp = {temps_present[0]: 1.0}

    os.makedirs(PLOTDIR, exist_ok=True)

    print(f"Graficando {len(entries)} formas de onda "
          f"({len(corners_present)} corners x {len(temps_present)} temps x {len(vdds_present)} vdd)...")

    for signal in signals:
        fig, ax = plt.subplots(figsize=(11, 6))

        for e in entries:
            try:
                time, values = load_waveform(e["path"], signal=signal)
            except Exception as exc:
                print(f"  [!] no se pudo leer {e['path']} ({signal}): {exc}", file=sys.stderr)
                continue

            ax.plot(
                time * 1e9, values,
                color=color_for_corner[e["corner"]],
                linestyle=style_for_vdd[e["vdd"]],
                alpha=alpha_for_temp[e["temp"]],
                linewidth=1.2,
            )

        # Leyenda compuesta: un grupo de proxies por color (corner) y otro por linestyle (vdd)
        corner_handles = [
            plt.Line2D([0], [0], color=color_for_corner[c], lw=2, label=c)
            for c in corners_present
        ]
        vdd_handles = [
            plt.Line2D([0], [0], color="gray", lw=2, linestyle=style_for_vdd[v], label=f"{fmt_num(v)} V")
            for v in vdds_present
        ]

        legend1 = ax.legend(handles=corner_handles, title="Corner (color)", loc="upper left",
                             bbox_to_anchor=(1.01, 1.0))
        ax.add_artist(legend1)
        ax.legend(handles=vdd_handles, title="VDD (línea)", loc="lower left", bbox_to_anchor=(1.01, 0.0))

        ax.set_xlabel("Tiempo (ns)")
        ax.set_ylabel(f"{signal} (V)")
        temp_note = f"temp: más claro = más frío, más oscuro = más caliente ({fmt_num(min(temps_present))}°C a {fmt_num(max(temps_present))}°C)" \
            if len(temps_present) > 1 else f"temp={fmt_num(temps_present[0])}°C"
        ax.set_title(f"Todas las combinaciones PVT — {signal}\n{temp_note}")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_signal = signal.replace("(", "").replace(")", "")
        fname = os.path.join(PLOTDIR, f"waveform_compare_all_{safe_signal}.png")
        plt.savefig(fname, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Guardado: {fname}")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_sweep = subparsers.add_parser("sweep", help="Corre el barrido PVT completo y guarda CSV + .raw por corrida")
    p_sweep.add_argument("--jobs", "-j", type=int, default=1,
                          help="Combinaciones en paralelo (default: 1 = secuencial, como antes). "
                               "Usar ~os.cpu_count() para aprovechar todos los núcleos.")
    p_sweep.set_defaults(func=cmd_sweep)

    p_compare = subparsers.add_parser("compare", help="Compara formas de onda entre esquinas para un temp/vdd fijo")
    p_compare.add_argument("--temp", type=float, default=27, help="Temperatura fija a comparar (default: 27)")
    p_compare.add_argument("--vdd", type=float, default=3.3, help="VDD fijo a comparar (default: 3.3)")
    p_compare.add_argument("--corners", nargs="+", default=None,
                            help=f"Esquinas a comparar (default: todas: {CORNERS})")
    p_compare.add_argument("--signals", nargs="+", default=["v(outb)"],
                            help="Señales a graficar, una figura por señal (default: v(outb))")
    p_compare.set_defaults(func=cmd_compare)

    p_all = subparsers.add_parser("compare-all",
                                   help="Grafica TODAS las combinaciones PVT (todos los .raw) en un mismo plot")
    p_all.add_argument("--raw-dir", default=RAWDIR, help=f"Directorio con los .raw (default: {RAWDIR})")
    p_all.add_argument("--signals", nargs="+", default=["v(outb)"],
                        help="Señales a graficar, una figura por señal (default: v(outb))")
    p_all.add_argument("--corners", nargs="+", default=None, help="Filtrar solo estas esquinas (default: todas)")
    p_all.add_argument("--temps", nargs="+", type=float, default=None, help="Filtrar solo estas temperaturas")
    p_all.add_argument("--vdds", nargs="+", type=float, default=None, help="Filtrar solo estos VDD")
    p_all.set_defaults(func=cmd_compare_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
