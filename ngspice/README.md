# Reduced, segmented and translated PDK libraries (sky130A and gf180mcuD)

This folder collects the tools and the libraries that make circuit simulation with the open PDKs
faster and portable between ngspice and LTspice (Windows and macOS). Nothing here changes the
transistor models: the libraries are built from the official PDK files, and every package is checked
against them.

## What is here

| Package | Simulator | PDK | What it is | README |
|---|---|---|---|---|
| `sky130A_min` | ngspice | sky130A | The PDK reduced to 6 FETs, plus one library per corner section. Cuts the library load time from 6 s to 0.12 s for a small circuit. | `README_sky130A_min.md` |
| `sky130A_ltspice_min` | LTspice | sky130A | The same 6 FETs translated to LTspice (meters, `gauss`, wrappers `xnfet_*` / `xpfet_*`), with all the corner sections, mismatch and Monte Carlo. | `README_ltspice.md` |
| `gf180mcuD_ltspice_min` | LTspice | gf180mcuD | 13 flat, self-contained libraries (about 160 KB each instead of the 1.3 MB, 47 764-line native file) with corners, mismatch and Monte Carlo. | `README_gf180_ltspice.md` |
| Tools and tests | both | both | Generators, bin-edge checker, ngspice Monte Carlo wrapper, test netlists, LTspice probes. | this file |

## Which one do I need?

| I want to simulate with... | Use |
|---|---|
| ngspice, sky130A | `sky130A_min` (use the library from `sections/`). |
| LTspice (Windows or macOS), sky130A | `sky130A_ltspice_min`. |
| LTspice (Windows or macOS), gf180mcuD | `gf180mcuD_ltspice_min`. |
| ngspice, gf180mcuD | The native PDK works in ngspice; there is no reduced package for it. The generated libraries are for LTspice. |
| ngspice Monte Carlo with a single process draw per run | `mc_runner.py` (below). |

## Common concepts

**Case / section names.** `tt ss ff sf fs` are the deterministic corners; the suffix `_mm` turns on the per-instance
mismatch; `mm` is mismatch on `tt`; `mc` is global process variation; `mcmm` is process + mismatch. In sky130 the
extra sections `ll hl lh hh` (resistor / capacitor corners) and their combinations exist with the same names, but they
do not change the FETs.

**Monte Carlo in ngspice and in LTspice are not the same thing.**

* In ngspice, the PDK draws the process parameters with `AGAUSS`, and ngspice evaluates it again for every instance. Two
  identical transistors then get different "process" values and the variation behaves like extra mismatch. With
  `mc_runner.py` one value per parameter is drawn per run, shared by all devices, as a real chip would.
* In LTspice, a global `.param` with `gauss()` is drawn once per `.step`, and a `.param` inside a subcircuit once per
  instance. The libraries use exactly that: process variation is global, mismatch is per instance. In LTspice
  `gauss(x)` is N(0, sigma = x).
* LTspice has no `mulu0` and no `?:` operator, so the k mismatch (`mis_k`, gf180) is not modelled, and the SAB
  subcircuits (`*_dss`) are left out.

**Bin edges.** The models are binned in L (and W). When L is exactly on a bin edge LTspice and ngspice can disagree
(sigma of the process Monte Carlo in sky130, about 1.7 % in Id for gf180 nfet_06v0 at L = 0.7u). Use L = edge + 10 nm.
`check_bin_edges.py` warns about it in your netlists.

## Tools

| File | What it does |
|---|---|
| `make_min_pdk.py` | Builds `sky130A_min` (ngspice, with `--split-sections`) and `sky130A_ltspice_min` (`--target ltspice`). Also `--check-netlist` and `--smoke-test`. |
| `make_min_gf180.py` | Builds the 13 gf180mcuD libraries for LTspice from the native `sm141064.ngspice`. It imports `make_min_pdk.py`. |
| `check_bin_edges.py` | Warns about L on a bin edge in `.cir` / `.net` / `.asc` files (sky130A). |
| `mc_runner.py` | Monte Carlo for sky130 in ngspice with global process variation; returns a DataFrame or a CSV. |
| `gf180_smoke.py` | ngspice check: native PDK vs generated libraries (draws replaced by constants). |
| `gf180_tests.py`, `gf180_tests2.py`, `gf180_tests3.py` | Generate the LTspice test netlists with reference values computed in ngspice. |
| `probes_ltspice/` | Five small netlists that were used to learn how LTspice behaves: sigma of `gauss()`, how often a random function is redrawn, local `.model`, `delvto` / `mulu0` in BSIM4, mismatch in a subcircuit. |

Keep the scripts in the same folder: they import each other.

### `mc_runner.py` (ngspice, sky130)

    python mc_runner.py my_inverter.cir --pdk sky130A_min -n 200 --corner tt --process global --no-mismatch --seed 1 --jobs 4 --out mc.csv

or from Python:

    from mc_runner import run_mc
    df = run_mc("my_inverter.cir", "sky130A_min", n=200, corner="tt", process="global", mismatch=False, seed=1, jobs=4)
    df[["tphl", "tplh"]].describe()

The netlist must contain a line `.lib <...>/sky130.lib.spice <section>`. Modes: `global` (default), `instance` (original PDK
behaviour) and `off`. The seed makes the run reproducible. It builds a one-section library for each run, so it is fast
even when it points to the full PDK. It needs Python 3.9+, numpy and (optionally) pandas.

## How the libraries were validated

| Package | Check | Result |
|---|---|---|
| `sky130A_min` | Id in 5 corners, full vs reduced PDK (ngspice); sections identical line by line | difference 0 |
| `sky130A_ltspice_min` | Id and Cgg of 23 geometries in 24 deterministic sections, full PDK vs translation (ngspice) | difference 0 |
| `sky130A_ltspice_min` | Deterministic OP in LTspice vs ngspice | max 0.0005 % |
| `sky130A_ltspice_min` | Monte Carlo sigma/mean in LTspice vs ngspice (L = 0.55u) | nfet 0.59 % vs 0.61 %, pfet 0.74 % vs 0.76 % |
| `gf180mcuD_ltspice_min` | Id and Cgg of 22 devices in 12 cases, native vs generated (ngspice) | difference 0 |
| `gf180mcuD_ltspice_min` | Deterministic OP in LTspice, 5 corners vs ngspice | max 0.032 % |
| `gf180mcuD_ltspice_min` | MC / mismatch in LTspice vs ngspice, 7 cases | means within 0.45 %, sigma within the sampling uncertainty |

The details, the tables and the small deviations that were found (and explained) are in each package's README.

## Known limitations (all packages)

| Limitation | Where |
|---|---|
| Only FETs; no resistors, capacitors, BJTs or diodes | all |
| `mis_k` (`mulu0`) mismatch of gf180 is not modelled | gf180 LTspice |
| `*_dss` (SAB) subcircuits are omitted (`--keep-dss` keeps them) | gf180 LTspice |
| Mismatch with `nf` or `m` different from 1 not validated in LTspice | sky130 LTspice |
| L exactly on a bin edge gives different results | all LTspice |
| Validated in LTspice 26.0.1 for Windows; macOS expected to work, not run | all LTspice |
| LTspice transients (delays, etc.) have not been compared against ngspice | all LTspice |
| Timing data are for one inverter and one machine | `sky130A_min` |

## Requirements

* Python 3.9 or newer for the generators; numpy (and optionally pandas) for `mc_runner.py`.
* ngspice (42 was used) for the smoke tests, the tests' reference values and `mc_runner.py`.
* The original PDK: a full `sky130A` directory (as installed by open_pdks / volare) and the native gf180mcuD
  `sm141064.ngspice` (and `design.ngspice`).
* LTspice 26.0.1 (Windows) was used for validation.

## Regenerating everything

    python make_min_pdk.py --src PATH/sky130A --dst sky130A_min --split-sections --force --smoke-test
    python make_min_pdk.py --target ltspice --src PATH/sky130A --dst sky130A_ltspice_min --force --smoke-test
    python make_min_gf180.py --src FOLDER_WITH_sm141064.ngspice --dst gf180mcuD_ltspice_min --force --smoke-test --write-tests

Every output has a `MANIFEST` with the sha256 of each file, so you can tell whether a copy is the one you expect.

## License

The libraries are derived from the SkyWater sky130 PDK (Apache License 2.0, Copyright The SkyWater PDK
Authors) and the GlobalFoundries gf180mcu PDK (Apache License 2.0, Copyright GlobalFoundries PDK Authors).
The original license headers are kept in the copied files. The tools are provided as they are, with no warranty.
