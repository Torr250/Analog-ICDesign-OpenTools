#!/usr/bin/env python3
"""
mc_runner.py

Corre el testbench TB_not (inversor CMOS, gf180mcuD) con Monte Carlo
habilitado (sw_stat_global=1, sw_stat_mismatch=1) N veces, y recolecta:
  1. Los resultados escalares de los .meas (trise, tfall, tplh, tphl,
     tpd_avg, ivdd_rms, effy) en un CSV, una fila por corrida.
  2. Un .raw individual por corrida (para graficar/comparar formas de
     onda entre muestras de Monte Carlo).

A diferencia del runner de PVT, acá NO se sustituye nada del netlist entre
corridas (mismo corner, mismo VDD, misma temp) — cada invocación de
'ngspice -b' es un proceso independiente que arranca con su propia semilla
aleatoria del sistema, así que basta con correr el netlist N veces.

IMPORTANTE: no hay forma de fijar/reproducir la semilla de una corrida
puntual (ver nota en el netlist) — cada corrida es única e irrepetible.

Uso:
    # 1) Corre el barrido Monte Carlo (genera CSV + .raw por corrida)
    python3 mc_runner.py sweep                # 200 corridas (default), secuencial
    python3 mc_runner.py sweep --n 500
    python3 mc_runner.py sweep --n 500 --jobs 8   # 8 corridas de ngspice en paralelo

    # 2) Superpone las formas de onda de varias corridas en un solo plot
    python3 mc_runner.py plot                         # superpone todas las corridas disponibles
    python3 mc_runner.py plot --n-overlay 30          # superpone solo 30 (muestra aleatoria)
    python3 mc_runner.py plot --n-overlay 30 --mode first   # las primeras 30, sin azar
    python3 mc_runner.py plot --signals "v(outb)" "v(in)"
"""

import argparse
import csv
import os
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt

try:
    from spicelib.raw.raw_read import RawRead
except ImportError:
    RawRead = None

TEMPLATE = "TB_not_mc_template.spice"
WORKDIR = "mc_runs"
RAWDIR = "mc_raws"
OUTPUT_CSV = "mc_results.csv"
PLOTDIR = "mc_analysis"

N_RUNS = 200

MEAS_NAMES = ["trise", "tfall", "tplh", "tphl", "tpd_avg", "ivdd_rms", "effy"]

TEMPLATE_RAW_NAME = "TB_not.raw"

RAW_FILENAME_RE = re.compile(r"mc_run_(?P<idx>\d+)\.raw$")


# ----------------------------------------------------------------------
# sweep: corre N veces, guarda CSV + .raw por corrida (igual que antes)
# ----------------------------------------------------------------------

def raw_path_for(run_idx: int) -> str:
    return os.path.join(RAWDIR, f"mc_run_{run_idx:04d}.raw")


def build_netlist(template_text: str, run_idx: int) -> str:
    """Solo redirige el 'write' a un .raw único por corrida; nada más cambia."""
    raw_path = raw_path_for(run_idx)
    return template_text.replace(f"write {TEMPLATE_RAW_NAME}", f"write {raw_path}")


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


def run_one(template_text: str, run_idx: int) -> dict:
    """Ejecuta UNA corrida completa (netlist -> ngspice -> parseo) y devuelve
    todo lo necesario para reportar progreso y escribir el CSV. Esta función
    es la unidad de trabajo que se manda al pool de threads."""
    raw_path = raw_path_for(run_idx)
    netlist = build_netlist(template_text, run_idx)

    fname = os.path.join(WORKDIR, f"mc_run_{run_idx:04d}.spice")
    with open(fname, "w") as f:
        f.write(netlist)

    stdout = run_ngspice(fname)

    log_fname = fname.replace(".spice", ".log")
    with open(log_fname, "w") as f:
        f.write(stdout)

    row = {"run": run_idx}
    for meas in MEAS_NAMES:
        row[meas] = parse_meas(stdout, meas)
    missing = [m for m in MEAS_NAMES if row[m] is None]

    return {
        "run_idx": run_idx,
        "row": row,
        "missing": missing,
        "raw_path": raw_path,
        "log_fname": log_fname,
        "raw_ok": os.path.isfile(raw_path),
    }


def cmd_sweep(args):
    n_runs = args.n
    jobs = args.jobs

    if not os.path.isfile(TEMPLATE):
        print(f"Error: no se encontró el template '{TEMPLATE}' en el directorio actual.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(WORKDIR, exist_ok=True)
    os.makedirs(RAWDIR, exist_ok=True)

    with open(TEMPLATE, "r") as f:
        template_text = f.read()

    # results indexado por posición para poder reordenar al final, ya que
    # las corridas paralelas no necesariamente terminan en orden
    results = [None] * n_runs
    done = 0

    print(f"Corriendo {n_runs} muestras de Monte Carlo con {jobs} worker(s) en paralelo...\n")

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(run_one, template_text, i): i for i in range(1, n_runs + 1)}

        for future in as_completed(futures):
            run_idx = futures[future]
            outcome = future.result()

            results[run_idx - 1] = outcome["row"]
            done += 1

            if not outcome["raw_ok"]:
                print(f"    [!] corrida {run_idx}: no se generó el .raw esperado "
                      f"({outcome['raw_path']}); revisar {outcome['log_fname']}")
            if outcome["missing"]:
                print(f"    [!] corrida {run_idx}: no se pudo extraer "
                      f"{', '.join(outcome['missing'])} (revisar {outcome['log_fname']})")

            if done % 10 == 0 or done == n_runs:
                print(f"[{done}/{n_runs}] corridas completadas")

    fieldnames = ["run"] + MEAS_NAMES
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nListo. {len(results)} corridas completadas.")
    print(f"  CSV de mediciones : {OUTPUT_CSV}")
    print(f"  Netlists + logs   : {WORKDIR}/")
    print(f"  Waveforms (.raw)  : {RAWDIR}/")


# ----------------------------------------------------------------------
# plot: superpone las formas de onda de N corridas en un solo gráfico
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


def discover_mc_raws(raw_dir: str):
    """Escanea raw_dir y devuelve [(run_idx, path), ...] ordenado por índice de corrida."""
    entries = []
    if not os.path.isdir(raw_dir):
        return entries
    for fname in os.listdir(raw_dir):
        m = RAW_FILENAME_RE.search(fname)
        if not m:
            continue
        entries.append((int(m.group("idx")), os.path.join(raw_dir, fname)))
    entries.sort(key=lambda e: e[0])
    return entries


def cmd_plot(args):
    raw_dir = args.raw_dir
    entries = discover_mc_raws(raw_dir)

    if not entries:
        print(f"Error: no se encontraron .raw en '{raw_dir}/'. ¿Corriste 'sweep' primero?", file=sys.stderr)
        sys.exit(1)

    total_available = len(entries)
    n_overlay = args.n_overlay if args.n_overlay is not None else total_available
    n_overlay = min(n_overlay, total_available)

    if n_overlay < total_available:
        if args.mode == "random":
            if args.seed is not None:
                random.seed(args.seed)
            selected = random.sample(entries, n_overlay)
            selected.sort(key=lambda e: e[0])
        else:  # "first"
            selected = entries[:n_overlay]
    else:
        selected = entries

    os.makedirs(PLOTDIR, exist_ok=True)

    print(f"Superponiendo {len(selected)} de {total_available} corridas disponibles "
          f"(modo: {args.mode if n_overlay < total_available else 'todas'})...")

    for signal in args.signals:
        fig, ax = plt.subplots(figsize=(10, 6))

        for run_idx, raw_path in selected:
            try:
                time, values = load_waveform(raw_path, signal=signal)
            except Exception as exc:
                print(f"  [!] no se pudo leer {raw_path} ({signal}): {exc}", file=sys.stderr)
                continue
            ax.plot(time * 1e9, values, color="steelblue", alpha=0.35, linewidth=0.9)

        ax.set_xlabel("Tiempo (ns)")
        ax.set_ylabel(f"{signal} (V)")
        ax.set_title(f"Monte Carlo — {signal}  ({len(selected)} corridas superpuestas)")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        safe_signal = signal.replace("(", "").replace(")", "")
        fname = os.path.join(PLOTDIR, f"mc_overlay_{safe_signal}_{len(selected)}runs.png")
        plt.savefig(fname, dpi=150)
        plt.close()
        print(f"Guardado: {fname}")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_sweep = subparsers.add_parser("sweep", help="Corre N muestras de Monte Carlo y guarda CSV + .raw por corrida")
    p_sweep.add_argument("--n", type=int, default=N_RUNS, help=f"Número de corridas (default: {N_RUNS})")
    p_sweep.add_argument("--jobs", "-j", type=int, default=1,
                          help="Corridas en paralelo (default: 1 = secuencial, como antes). "
                               "Usar ~os.cpu_count() para aprovechar todos los núcleos.")
    p_sweep.set_defaults(func=cmd_sweep)

    p_plot = subparsers.add_parser("plot", help="Superpone las formas de onda de varias corridas en un solo gráfico")
    p_plot.add_argument("--raw-dir", default=RAWDIR, help=f"Directorio con los .raw (default: {RAWDIR})")
    p_plot.add_argument("--n-overlay", type=int, default=None,
                         help="Cuántas corridas superponer (default: todas las disponibles)")
    p_plot.add_argument("--mode", choices=["random", "first"], default="random",
                         help="Si --n-overlay es menor al total: 'random' (muestra al azar, default) "
                              "o 'first' (las primeras N corridas, sin azar)")
    p_plot.add_argument("--seed", type=int, default=None,
                         help="Semilla para la selección aleatoria de corridas (reproducibilidad de QUÉ corridas "
                              "se grafican, no de la simulación en sí)")
    p_plot.add_argument("--signals", nargs="+", default=["v(outb)"],
                         help="Señales a graficar, una figura por señal (default: v(outb))")
    p_plot.set_defaults(func=cmd_plot)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
