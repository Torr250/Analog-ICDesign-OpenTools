#!/usr/bin/env python3
"""
analyze_mc.py

Analiza los resultados de mc_results.csv (generado por mc_runner.py) y:
  1. Imprime estadísticas por métrica: media, sigma, min, max, mediana,
     coeficiente de variación (%), y rango ±3sigma.
  2. Si se pasa un spec (--spec) para una métrica, calcula su YIELD
     (% de corridas que cumplen el límite) y marca el límite en el
     histograma. Las métricas SIN spec se siguen reportando igual que
     antes (media/sigma/histograma), simplemente sin yield.
  3. Genera un histograma por métrica.
  4. Guarda un resumen numérico en mc_summary.csv (yield_pct queda vacío
     para las métricas sin spec).

Usa el mismo esquema de grupos/unidades que analyze_pvt.py (tiempo,
corriente, eficiencia) para que las unidades se muestren de forma legible
(ps, uA, mW/GHz) en vez de notación científica.

Uso:
    python3 analyze_mc.py [ruta_al_csv]
    python3 analyze_mc.py mc_results.csv --spec tpd_avg:lt:1.3e-10
    python3 analyze_mc.py --spec tpd_avg:lt:1.3e-10 --spec ivdd_rms:lt:2.5e-4

Formato de --spec (repetible, uno por límite):
    metric:op:valor
    donde op es uno de: lt (<), le (<=), gt (>), ge (>=)
    y valor va en UNIDADES BASE (segundos, amperios, mW/GHz) — no en ps/uA.

    Una métrica con límite superior E inferior necesita dos --spec:
        --spec tpd_avg:gt:9e-11 --spec tpd_avg:lt:1.3e-10

Si no se pasa ningún --spec, el script funciona exactamente igual que
antes (sin yield). Las métricas que no aparecen en ningún --spec no
tienen yield, así que se puede especificar un subconjunto nada más.

Requiere: pandas, matplotlib
    pip install pandas matplotlib --break-system-packages
"""

import argparse
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# Mismo esquema de grupos/unidades que analyze_pvt.py
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

MEAS_GROUPS = {
    "time": {
        "cols": TIME_COLS,
        "units": _UNITS_TIME,
        "default": (1e-12, "ps"),
    },
    "current": {
        "cols": CURRENT_COLS,
        "units": _UNITS_CURRENT,
        "default": (1e-6, "uA"),
    },
    "efficiency": {
        "cols": EFFICIENCY_COLS,
        "units": None,
        "default": (1.0, "mW/GHz"),
    },
}

_OPS = {
    "lt": (lambda s, v: s < v, "<"),
    "le": (lambda s, v: s <= v, "<="),
    "gt": (lambda s, v: s > v, ">"),
    "ge": (lambda s, v: s >= v, ">="),
}


def best_unit_for(values, units, default):
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


def fmt_val(value, scale, unit, decimals=3):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value / scale:.{decimals}f} {unit}"


def parse_specs(spec_args):
    """
    Convierte una lista de strings 'metric:op:valor' en un dict:
        {metric: [(op_fn, op_label, valor), ...]}
    Varias entradas para la misma métrica se acumulan (ej. límite inferior
    Y superior a la vez).
    """
    specs = {}
    for raw in spec_args or []:
        parts = raw.split(":")
        if len(parts) != 3:
            print(f"Error: spec '{raw}' inválido, formato esperado metric:op:valor", file=sys.stderr)
            sys.exit(1)
        metric, op, value_str = parts
        if op not in _OPS:
            print(f"Error: operador '{op}' inválido en '{raw}'. Usar: {list(_OPS)}", file=sys.stderr)
            sys.exit(1)
        try:
            value = float(value_str)
        except ValueError:
            print(f"Error: valor '{value_str}' inválido en '{raw}'", file=sys.stderr)
            sys.exit(1)
        op_fn, op_label = _OPS[op]
        specs.setdefault(metric, []).append((op_fn, op_label, value))
    return specs


def load_data(csv_path: str) -> pd.DataFrame:
    if not os.path.isfile(csv_path):
        print(f"Error: no se encontró '{csv_path}'", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(csv_path)

    present_meas = [c for c in TIME_COLS + CURRENT_COLS + EFFICIENCY_COLS if c in df.columns]
    missing = df[present_meas].isna().sum()
    if missing.sum() > 0:
        print("Aviso: algunas corridas tienen mediciones vacías (posible falla de trigger/target):")
        print(missing[missing > 0].to_string())
        print()

    if "tpd_avg" not in df.columns and "tplh" in df.columns and "tphl" in df.columns:
        df["tpd_avg"] = df[["tplh", "tphl"]].mean(axis=1)

    return df


def active_groups(df: pd.DataFrame):
    groups = {}
    for name, cfg in MEAS_GROUPS.items():
        cols = [c for c in cfg["cols"] if c in df.columns]
        if not cols:
            continue
        all_values = df[cols].values.flatten()
        scale, unit = best_unit_for(all_values, cfg["units"], cfg["default"])
        groups[name] = {"cols": cols, "scale": scale, "unit": unit}
    return groups


def compute_stats(series: pd.Series) -> dict:
    valid = series.dropna()
    n = len(valid)
    mean = valid.mean() if n else float("nan")
    std = valid.std(ddof=1) if n > 1 else float("nan")
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "min": valid.min() if n else float("nan"),
        "max": valid.max() if n else float("nan"),
        "median": valid.median() if n else float("nan"),
        "cv_pct": (std / mean * 100.0) if mean else float("nan"),
        "min3sigma": mean - 3 * std if n > 1 else float("nan"),
        "max3sigma": mean + 3 * std if n > 1 else float("nan"),
    }


def compute_yield(series: pd.Series, constraints: list):
    """
    constraints: [(op_fn, op_label, value), ...] ya combinados con AND.
    Devuelve (yield_pct, n_fail, mask) o (None, None, None) si no hay constraints.
    """
    if not constraints:
        return None, None, None
    valid = series.dropna()
    mask = pd.Series(True, index=valid.index)
    for op_fn, _, value in constraints:
        mask &= op_fn(valid, value)
    yield_pct = mask.mean() * 100.0
    n_fail = (~mask).sum()
    return yield_pct, n_fail, mask


def spec_desc(constraints: list, scale: float, unit: str) -> str:
    parts = [f"{op_label} {value / scale:.3f} {unit}" for _, op_label, value in constraints]
    return " y ".join(parts)


def spec_desc_base(constraints: list, unit: str) -> str:
    """Igual que spec_desc pero para el CSV, en unidades base (usa notación
    científica para no truncar valores chicos como 1.1e-10 a '0.000')."""
    parts = [f"{op_label} {value:.4e} {unit}" for _, op_label, value in constraints]
    return " y ".join(parts)


def print_summary(df: pd.DataFrame, groups: dict, specs: dict):
    for gname, g in groups.items():
        cols, scale, unit = g["cols"], g["scale"], g["unit"]

        print("=" * 70)
        print(f"GRUPO: {gname.upper()}  (unidades: {unit})")
        print("=" * 70)

        for metric in cols:
            s = compute_stats(df[metric])
            print(f"\n{metric}  (n={s['n']}):")
            print(f"  Media    : {fmt_val(s['mean'], scale, unit)}")
            print(f"  Sigma    : {fmt_val(s['std'], scale, unit)}   (CV = {s['cv_pct']:.2f}%)")
            print(f"  Mediana  : {fmt_val(s['median'], scale, unit)}")
            print(f"  Min/Max  : {fmt_val(s['min'], scale, unit)} / {fmt_val(s['max'], scale, unit)}")
            print(f"  Rango ±3sigma: [{fmt_val(s['min3sigma'], scale, unit)}, {fmt_val(s['max3sigma'], scale, unit)}]")

            constraints = specs.get(metric)
            if constraints:
                yield_pct, n_fail, _ = compute_yield(df[metric], constraints)
                desc = spec_desc(constraints, scale, unit)
                print(f"  Spec     : {desc}")
                print(f"  Yield    : {yield_pct:.2f}%   ({n_fail} de {s['n']} corridas fuera de spec)")
            else:
                print(f"  Spec     : (sin definir — no se calcula yield para esta métrica)")
        print()

    # yield combinado: todas las métricas con spec deben cumplirse a la vez
    specced_metrics = [m for m in specs if m in df.columns]
    if len(specced_metrics) > 1:
        combined_mask = pd.Series(True, index=df.index)
        for metric in specced_metrics:
            valid_mask = df[metric].notna()
            combined_mask &= valid_mask
            for op_fn, _, value in specs[metric]:
                combined_mask &= op_fn(df[metric], value).reindex(df.index, fill_value=False)
        combined_yield = combined_mask.mean() * 100.0
        print("=" * 70)
        print(f"YIELD COMBINADO ({' + '.join(specced_metrics)}): {combined_yield:.2f}% "
              f"({(~combined_mask).sum()} de {len(df)} corridas fallan al menos un spec)")
        print("=" * 70)
        print()


def plot_histogram(df: pd.DataFrame, metric: str, scale: float, unit: str, outdir: str, constraints: list):
    s = compute_stats(df[metric])
    values = (df[metric].dropna() / scale)
    mean = s["mean"] / scale
    std = s["std"] / scale if pd.notna(s["std"]) else 0

    fig, ax = plt.subplots(figsize=(8, 5))
    n_bins = max(5, min(30, len(values) // 2 or 5))
    ax.hist(values, bins=n_bins, color="steelblue", edgecolor="white", alpha=0.85)

    ax.axvline(mean, color="black", linestyle="-", linewidth=1.5, label=f"media = {mean:.3f} {unit}")
    if std > 0:
        ax.axvline(mean - 3 * std, color="red", linestyle="--", linewidth=1, label="±3σ")
        ax.axvline(mean + 3 * std, color="red", linestyle="--", linewidth=1)

    title_extra = ""
    if constraints:
        yield_pct, _, _ = compute_yield(df[metric], constraints)
        for _, op_label, value in constraints:
            ax.axvline(value / scale, color="darkorange", linestyle=":", linewidth=2,
                       label=f"spec {op_label} {value/scale:.3f} {unit}")
        title_extra = f", yield={yield_pct:.1f}%"

    ax.set_xlabel(f"{metric} ({unit})")
    ax.set_ylabel("Frecuencia (# corridas)")
    ax.set_title(f"Distribución Monte Carlo — {metric}  (n={s['n']}, CV={s['cv_pct']:.2f}%{title_extra})")
    ax.legend(fontsize=8)
    plt.tight_layout()

    fname = os.path.join(outdir, f"hist_{metric}.png")
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Guardado: {fname}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", nargs="?", default="mc_results.csv", help="Ruta al CSV de resultados MC")
    parser.add_argument("--spec", action="append", default=[],
                         help="Límite de spec: metric:op:valor (repetible). op en {lt,le,gt,ge}. "
                              "Valor en unidades base (s, A, mW/GHz).")
    args = parser.parse_args()

    outdir = "mc_analysis"
    os.makedirs(outdir, exist_ok=True)

    specs = parse_specs(args.spec)

    df = load_data(args.csv_path)
    groups = active_groups(df)

    unknown_specs = [m for m in specs if not any(m in g["cols"] for g in groups.values())]
    if unknown_specs:
        print(f"Aviso: --spec para métricas no presentes en el CSV (se ignoran): {unknown_specs}\n")

    print("Grupos de métricas detectados en el CSV:")
    for gname, g in groups.items():
        specced = [c for c in g["cols"] if c in specs]
        note = f"  (con spec: {specced})" if specced else ""
        print(f"  - {gname}: {g['cols']}  (unidad: {g['unit']}){note}")
    print()

    print_summary(df, groups, specs)

    print("Generando histogramas...")
    all_stats_rows = []
    for gname, g in groups.items():
        for metric in g["cols"]:
            constraints = specs.get(metric)
            plot_histogram(df, metric, g["scale"], g["unit"], outdir, constraints)
            s = compute_stats(df[metric])
            s["metric"] = metric
            s["unit_base"] = "s" if gname == "time" else ("A" if gname == "current" else "mW/GHz")
            if constraints:
                yield_pct, n_fail, _ = compute_yield(df[metric], constraints)
                s["yield_pct"] = yield_pct
                s["spec"] = spec_desc_base(constraints, s["unit_base"])
            else:
                s["yield_pct"] = float("nan")
                s["spec"] = ""
            all_stats_rows.append(s)

    summary_df = pd.DataFrame(all_stats_rows).set_index("metric")
    summary_df = summary_df[["n", "mean", "std", "median", "min", "max", "cv_pct",
                              "min3sigma", "max3sigma", "yield_pct", "spec", "unit_base"]]
    summary_path = os.path.join(outdir, "mc_summary.csv")
    summary_df.to_csv(summary_path)
    print(f"\nResumen numérico (unidades base) guardado en: {summary_path}")
    print(f"Histogramas guardados en: {outdir}/")


if __name__ == "__main__":
    main()
