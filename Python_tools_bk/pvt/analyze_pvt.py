#!/usr/bin/env python3
"""
analyze_pvt.py

Analiza los resultados de pvt_results.csv (generado por pvt_runner.py /
pvt_runner_plots.py) y:
  1. Imprime un resumen de peor/mejor caso por métrica, agrupadas por tipo
     de magnitud física (tiempo, corriente, eficiencia, o lo que definas en
     MEAS_GROUPS) para que cada una se muestre en su unidad natural.
  2. Genera gráficos para cada grupo de métricas, sin casos especiales por
     nombre de métrica ni de grupo:
     - Barras: peor caso por esquina de proceso (solo si el grupo agrupa
       más de una métrica, ej. trise/tfall/tplh/tphl juntas)
     - Heatmap: cada métrica individual, por esquina vs temperatura, uno
       por cada VDD
     - Boxplot: dispersión de cada métrica individual por esquina
       (across temp/vdd)

Para reutilizar este script con otro circuito: agregá/quitá nombres de
columnas en MEAS_GROUPS (abajo) según las mediciones que tenga tu netlist.
No hace falta tocar el resto del código.

Uso:
    python3 analyze_pvt.py [ruta_al_csv]

Si no se pasa ruta, usa 'pvt_results.csv' en el directorio actual.
Requiere: pandas, matplotlib
    pip install pandas matplotlib --break-system-packages
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# Grupos de métricas: cada una tiene su propia familia de unidades SI,
# porque no tiene sentido mezclar segundos con amperios en la misma escala.
# ----------------------------------------------------------------------

TIME_COLS = ["trise", "tfall", "tplh", "tphl", "tpd_avg"]
CURRENT_COLS = ["ivdd_rms"]
EFFICIENCY_COLS = ["effy"]  # ya viene en mW/GHz, no se reescala

_UNITS_TIME = [
    (1e0, "s"), (1e-3, "ms"), (1e-6, "us"), (1e-9, "ns"), (1e-12, "ps"), (1e-15, "fs"),
]
_UNITS_CURRENT = [
    (1e0, "A"), (1e-3, "mA"), (1e-6, "uA"), (1e-9, "nA"), (1e-12, "pA"),
]

# Definición de cada grupo: columnas presentes (se filtran contra el CSV real),
# tabla de unidades a usar (None = no reescalar), unidad por defecto si no hay datos,
# y si un valor más alto es mejor o peor para esa magnitud (para saber qué es
# "peor caso" y qué es "mejor caso" al agregar por esquina).
MEAS_GROUPS = {
    "time": {
        "cols": TIME_COLS,
        "units": _UNITS_TIME,
        "default": (1e-12, "ps"),
        "higher_is_better": False,   # menor tiempo = mejor
    },
    "current": {
        "cols": CURRENT_COLS,
        "units": _UNITS_CURRENT,
        "default": (1e-6, "uA"),
        "higher_is_better": False,   # menor corriente = mejor
    },
    "efficiency": {
        "cols": EFFICIENCY_COLS,
        "units": None,          # sin reescalado: ya está en mW/GHz
        "default": (1.0, "mW/GHz"),
        "higher_is_better": False,   # menor mW/GHz = mejor (más eficiente)
    },
}


def best_unit_for(values, units, default):
    """
    Elige la escala/unidad SI más legible para un conjunto de valores,
    usando la mediana como referencia de magnitud.
    Si units es None, no hay reescalado posible (se usa 'default' tal cual).
    """
    if units is None:
        return default

    clean = sorted(v for v in values if v is not None and not pd.isna(v) and v != 0)
    if not clean:
        return default

    median = clean[len(clean) // 2]
    for scale, name in units:
        if median >= scale:
            return scale, name
    return units[-1]


def fmt_val(value, scale, unit, decimals=2):
    """Formatea un valor ya en unidades base (s, A, mW/GHz) a la escala/unidad dadas."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value / scale:.{decimals}f} {unit}"


def load_data(csv_path: str) -> pd.DataFrame:
    if not os.path.isfile(csv_path):
        print(f"Error: no se encontró '{csv_path}'", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(csv_path)

    present_meas = [c for c in TIME_COLS + CURRENT_COLS + EFFICIENCY_COLS if c in df.columns]
    missing_before = df[present_meas].isna().sum()
    if missing_before.sum() > 0:
        print("Aviso: algunas mediciones vinieron vacías (posible falla de trigger/target/param):")
        print(missing_before[missing_before > 0].to_string())
        print()

    if "tpd_avg" not in df.columns and "tplh" in df.columns and "tphl" in df.columns:
        # fallback por compatibilidad con netlists viejos que no calculaban tpd_avg ellos mismos
        df["tpd_avg"] = df[["tplh", "tphl"]].mean(axis=1)

    return df


def active_groups(df: pd.DataFrame):
    """Devuelve {nombre_grupo: {cols, scale, unit, higher_is_better}} solo para
    columnas presentes en el CSV."""
    groups = {}
    for name, cfg in MEAS_GROUPS.items():
        cols = [c for c in cfg["cols"] if c in df.columns]
        if not cols:
            continue
        all_values = df[cols].values.flatten()
        scale, unit = best_unit_for(all_values, cfg["units"], cfg["default"])
        groups[name] = {
            "cols": cols,
            "scale": scale,
            "unit": unit,
            "higher_is_better": cfg.get("higher_is_better", False),
        }
    return groups


def print_worst_case_summary(df: pd.DataFrame, groups: dict):
    corners_order = ["ff", "typical", "ss", "fs", "sf"]
    corners_order = [c for c in corners_order if c in df["corner"].unique()]
    corners_order += [c for c in df["corner"].unique() if c not in corners_order]

    for gname, g in groups.items():
        cols, scale, unit = g["cols"], g["scale"], g["unit"]
        higher_is_better = g["higher_is_better"]
        # si un valor más alto es mejor, el peor caso es el mínimo y viceversa
        worst_fn, best_fn = ("idxmin", "idxmax") if higher_is_better else ("idxmax", "idxmin")
        worst_agg, best_agg = ("min", "max") if higher_is_better else ("max", "min")

        print("=" * 70)
        print(f"GRUPO: {gname.upper()}  (unidades: {unit}, "
              f"{'mayor = mejor' if higher_is_better else 'menor = mejor'})")
        print("=" * 70)

        for meas in cols:
            valid = df.dropna(subset=[meas])
            if valid.empty:
                print(f"\n{meas}: sin datos válidos")
                continue

            worst_row = valid.loc[getattr(valid[meas], worst_fn)()]
            best_row = valid.loc[getattr(valid[meas], best_fn)()]

            print(f"\n{meas}:")
            print(f"  Peor caso : {fmt_val(worst_row[meas], scale, unit)}  "
                  f"(corner={worst_row['corner']}, temp={worst_row['temp']}C, vdd={worst_row['vdd']}V)")
            print(f"  Mejor caso: {fmt_val(best_row[meas], scale, unit)}  "
                  f"(corner={best_row['corner']}, temp={best_row['temp']}C, vdd={best_row['vdd']}V)")
            if best_row[meas] != 0:
                ratio = worst_row[meas] / best_row[meas] if not higher_is_better else best_row[meas] / worst_row[meas]
                print(f"  Rango (peor/mejor): {ratio:.2f}x")

        print(f"\n--- Peor caso por esquina de proceso — {gname} ({unit}) ---")
        corner_worst_series = getattr(df.groupby("corner")[cols], worst_agg)().reindex(corners_order)
        print((corner_worst_series / scale).to_string(float_format=lambda x: f"{x:.2f}"))

        if len(cols) == 1:
            per_corner = getattr(df.groupby("corner")[cols[0]], worst_agg)()
            overall_worst_corner = per_corner.idxmin() if higher_is_better else per_corner.idxmax()
            print(f"\n>> Esquina con el peor {cols[0]} en general: '{overall_worst_corner}'")
        print()


# ----------------------------------------------------------------------
# Gráficos genéricos: se reutilizan para cualquier grupo de métricas
# ----------------------------------------------------------------------

def plot_bar_by_corner(df: pd.DataFrame, cols: list, scale: float, unit: str,
                        agg: str, title: str, fname: str, outdir: str):
    """Barras: valor agregado (agg='max' o 'min') de cada métrica del grupo, por esquina."""
    corner_agg = getattr(df.groupby("corner")[cols], agg)() / scale

    ax = corner_agg.plot(kind="bar", figsize=(9, 5))
    ax.set_ylabel(f"Valor ({unit})")
    ax.set_xlabel("Esquina de proceso")
    ax.set_title(title)
    ax.legend(title="Métrica")
    plt.xticks(rotation=0)
    plt.tight_layout()
    path = os.path.join(outdir, fname)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Guardado: {path}")


def plot_heatmap_by_vdd(df: pd.DataFrame, metric: str, scale: float, unit: str,
                         title: str, fname: str, outdir: str):
    """Heatmap de una métrica (corner x temp) por cada valor de VDD."""
    vdds = sorted(df["vdd"].unique())
    fig, axes = plt.subplots(1, len(vdds), figsize=(5 * len(vdds), 4.5), sharey=True)
    if len(vdds) == 1:
        axes = [axes]

    corners_order = ["ff", "typical", "ss", "fs", "sf"]
    corners_order = [c for c in corners_order if c in df["corner"].unique()]
    corners_order += [c for c in df["corner"].unique() if c not in corners_order]

    for ax, vdd in zip(axes, vdds):
        sub = df[df["vdd"] == vdd]
        pivot = sub.pivot_table(index="corner", columns="temp", values=metric) / scale
        pivot = pivot.reindex(corners_order)

        im = ax.imshow(pivot.values, cmap="RdYlGn_r", aspect="auto")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_xlabel("Temp (°C)")
        ax.set_title(f"VDD = {vdd} V")

        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                val = pivot.values[i, j]
                if pd.notna(val):
                    ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8)

        fig.colorbar(im, ax=ax, label=f"{metric} ({unit})", shrink=0.8)

    axes[0].set_ylabel("Esquina de proceso")
    fig.suptitle(title)
    plt.tight_layout()
    path = os.path.join(outdir, fname)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Guardado: {path}")


def plot_boxplot_by_corner(df: pd.DataFrame, metric: str, scale: float, unit: str,
                            title: str, fname: str, outdir: str):
    """Boxplot de una métrica por corner, para ver dispersión across temp/vdd."""
    corners_order = ["ff", "typical", "ss", "fs", "sf"]
    corners_order = [c for c in corners_order if c in df["corner"].unique()]
    corners_order += [c for c in df["corner"].unique() if c not in corners_order]

    data = [(df[df["corner"] == c][metric].dropna() / scale).values for c in corners_order]

    fig, ax = plt.subplots(figsize=(8, 5))
    try:
        ax.boxplot(data, tick_labels=corners_order, showmeans=True)
    except TypeError:
        ax.boxplot(data, labels=corners_order, showmeans=True)
    ax.set_ylabel(f"{metric} ({unit})")
    ax.set_xlabel("Esquina de proceso")
    ax.set_title(title)
    plt.tight_layout()
    path = os.path.join(outdir, fname)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Guardado: {path}")


def generate_plots(df: pd.DataFrame, groups: dict, outdir: str):
    for gname, g in groups.items():
        cols, scale, unit = g["cols"], g["scale"], g["unit"]
        higher_is_better = g["higher_is_better"]
        worst_agg, best_agg = ("min", "max") if higher_is_better else ("max", "min")

        # Barras comparativas: solo tiene sentido si el grupo agrupa más de una métrica
        # (ej. trise/tfall/tplh/tphl juntas); un grupo de una sola métrica no necesita barra.
        if len(cols) > 1:
            plot_bar_by_corner(
                df, cols, scale, unit, agg=worst_agg,
                title=f"Peor caso por métrica del grupo '{gname}' y esquina (todas las temp/VDD)",
                fname=f"worst_by_corner_{gname}.png", outdir=outdir,
            )
            plot_bar_by_corner(
                df, cols, scale, unit, agg=best_agg,
                title=f"Mejor caso por métrica del grupo '{gname}' y esquina (todas las temp/VDD)",
                fname=f"best_by_corner_{gname}.png", outdir=outdir,
            )

        # Heatmap + boxplot individual para CADA métrica del grupo (sin excepciones)
        for metric in cols:
            plot_heatmap_by_vdd(
                df, metric, scale, unit,
                title=f"{metric} por esquina y temperatura, por VDD — en {unit}",
                fname=f"heatmap_{metric}_by_vdd.png", outdir=outdir,
            )
            plot_boxplot_by_corner(
                df, metric, scale, unit,
                title=f"Dispersión de {metric} por esquina (across temp x VDD)",
                fname=f"boxplot_{metric}_by_corner.png", outdir=outdir,
            )


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "pvt_results.csv"
    outdir = "pvt_analysis"
    os.makedirs(outdir, exist_ok=True)

    df = load_data(csv_path)
    groups = active_groups(df)

    print("Grupos de métricas detectados en el CSV:")
    for gname, g in groups.items():
        print(f"  - {gname}: {g['cols']}  (unidad: {g['unit']})")
    print()

    print_worst_case_summary(df, groups)

    print("Generando gráficos...")
    generate_plots(df, groups, outdir)

    # resumen numérico completo (todas las columnas, en unidades base sin reescalar),
    # respetando el criterio higher_is_better de cada grupo por separado
    worst_parts, best_parts = [], []
    for g in groups.values():
        cols = g["cols"]
        worst_agg, best_agg = ("min", "max") if g["higher_is_better"] else ("max", "min")
        worst_parts.append(getattr(df.groupby("corner")[cols], worst_agg)())
        best_parts.append(getattr(df.groupby("corner")[cols], best_agg)())

    worst_summary_path = os.path.join(outdir, "worst_case_summary.csv")
    pd.concat(worst_parts, axis=1).to_csv(worst_summary_path)
    print(f"\nResumen numérico de peor caso (unidades base) guardado en: {worst_summary_path}")

    best_summary_path = os.path.join(outdir, "best_case_summary.csv")
    pd.concat(best_parts, axis=1).to_csv(best_summary_path)
    print(f"Resumen numérico de mejor caso (unidades base) guardado en: {best_summary_path}")

    print(f"Gráficos guardados en: {outdir}/")


if __name__ == "__main__":
    main()
