# Analog-ICDesign-OpenTools

Analog integrated circuit design with open tools: models, examples and scripts for **ngspice**, **LTspice**,
**Xschem** and **Python**, using the open **sky130A** (SkyWater) and **gf180mcuD** (GlobalFoundries) PDKs.

The repository is maintained by Adán, PhD candidate in analog IC design (SerDes). It collects the material
developed while building simulation flows that are faster, portable between simulators and checked against the
official PDK files.

## Quick start: what do I need?

| I want to simulate with... | PDK | Use | Details |
|---|---|---|---|
| ngspice | sky130A | `ngspice/sky130A_min` (library from `sections/`) | `ngspice/sky130A_min/README_sky130A_min.md` |
| LTspice (Windows or macOS) | sky130A | `ngspice/sky130A_ltspice_min` | `ngspice/sky130A_ltspice_min/README_ltspice.md` |
| LTspice (Windows or macOS) | gf180mcuD | `ngspice/gf180mcuD_ltspice_min` | `ngspice/gf180mcuD_ltspice_min/README_gf180_ltspice.md` |
| ngspice | gf180mcuD | Native PDK in `ngspice/gf180mcuD` | There is no reduced package for it |
| gm/ID design | both | `gmID-Design/` | See below |

The overview of the reduced libraries (concepts, tools, license) is in [`ngspice/README.md`](ngspice/README.md).

## Repository structure

```
ngspice/        Reduced, segmented and translated PDK libraries, generators and tests
  sky130A_min/            ngspice, sky130A reduced to 6 FETs + one library per corner section
  sky130A_ltspice_min/    LTspice, sky130A
  gf180mcuD_ltspice_min/  LTspice, gf180mcuD (13 flat, self-contained libraries)
  tools/                  Generators, bin-edge checker, ngspice Monte Carlo wrapper, test generators
  sky130A/, gf180mcuD/    Native PDK files and ngspice examples
  Razavi/                 First-order MOSFET model (Razavi), DC and noise, ngspice (work in progress)
LTspice/        LTspice schematics and examples
  gf180mcuD/              SpiceLib (inverter: DC, PVT, MC, AC, noise, transient), Examples (DC sweeps, MC),
                          Example_Active_CLTE (active CTLE + channel)
  sky130A/Examples/       Inverter, DC sweeps, PVT, mc, mcmm
  Channel_Models/         Transmission-line / channel models
  Razavi/                 First-order model vs hand calculations in Jupyter (work in progress)
  Libraries/              Generic LTspice libraries
Xschem/         Xschem schematics
  sky130A/                Logic gates (not, buffer, nor) and testbenches
  gf180mcuD/gmID_Designs/ gm/ID designs: CML, active CTLE, course examples
gmID-Design/    gm/ID methodology
  Extraction/             techsweep and noise-test schematics, lookup examples (sky130A and gf180mcuD)
  PDKs/                   Lookup tables (.mat) per device and corner
  Scripts/                Jupyter notebooks: gm/ID course, CML, active CTLE
Python_tools/   channel_model (channel model generator) and eye_diagram (eye diagrams from ngspice .raw files)
```

Each `LTspice/**/` example folder that contains a `*_ltspice_min` folder holds a **local copy** of the library, so the
examples run as they are. The reference copy is the one in `ngspice/`.

## Highlights

**Faster simulations.** Loading the native sky130A library takes about 6 s for a small circuit. The reduced
library takes 2.7 s and the segmented one (a single corner section) 0.12 s. gf180mcuD goes from a 1.3 MB,
47 764-line file to 13 libraries of about 160 KB. Measured with ngspice-42, inverter, median of 7 runs.

| sky130A, small inverter | Time |
|---|---|
| Full library | 6.00 s |
| `min` | 2.74 s |
| Full, segmented | 0.14 s |
| `min`, segmented | 0.12 s |

**Same models in ngspice and LTspice.** The libraries only translate the PDK. The LTspice versions were checked
against ngspice: DC operating points agree within 0.03 % for all corners (gf180mcuD), and the sigma of Monte Carlo
and mismatch matches within the sampling noise, except for a small residual in `pfet_03v3` mismatch (-4.4 %, no
practical impact). Cases available: `tt ss ff sf fs`, `*_mm` (mismatch), `mc` (process), `mcmm` (process + mismatch).

**gm/ID.** Technology sweeps of the devices stored as lookup tables, and notebooks with the design flow applied to a
CML driver and an active CTLE.

**Channel and eye diagram tools.** A generator of SPICE channel models from loss-versus-frequency points, and a
script that folds an ngspice `.raw` into an eye diagram with automatic centering and decision threshold.

**Razavi (work in progress).** A first-order MOSFET model with DC and noise examples, compared with hand
calculations in Jupyter.

## Known limitations

* **Monte Carlo is not identical in both simulators.** ngspice re-evaluates `AGAUSS` per instance, so process
  variation acts as extra mismatch; use `mc_runner.py` for one draw per run. In LTspice, global `.param` values are
  drawn once per `.step` and mismatch once per instance.
* **LTspice has no `mulu0` and no `?:`**, so the gf180 k mismatch (`mis_k`) is not modelled and the SAB
  subcircuits (`*_dss`) are left out.
* **Bin edges.** If L is exactly on a bin edge the simulators can disagree (about 1.7 % in Id for gf180
  `nfet_06v0` at L = 0.7u). Use L = edge + 10 nm; `check_bin_edges.py` warns about it.
* **Flicker noise (gf180mcuD).** `fnoicor` (in `design.ngspice`) selects the flicker-noise parameters: 0 is the
  as-extracted set (default), 1 the worst case. It only affects noise analyses. The flicker noise model is
  computed differently in ngspice and LTspice.
* sky130 pfet models look non-physical in moderate and weak inversion; see `gmID-Design/Extraction/sky130A/README.md`.

## Requirements

* [ngspice](https://ngspice.sourceforge.io/) (tested with ngspice-42)
* [LTspice](https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html) (Windows or macOS)
* [Xschem](https://xschem.sourceforge.io/stefan/index.html) for the schematics in `Xschem/` and `gmID-Design/`
* Python 3.9+ with numpy, scipy, matplotlib and Jupyter for the tools and notebooks

## Roadmap

* More Python tools for the simulation flow (analysis, plotting, automation).
* Finish the Razavi examples (DC, noise, comparison with hand calculations).
* Keep extending the LTspice and ngspice examples for both PDKs.

## License and credits

The libraries are derived from the SkyWater sky130 PDK and the GlobalFoundries gf180mcu PDK, both under the Apache
License 2.0. The original license headers are kept in the copied files. The tools and examples are provided as they
are, with no warranty. The first-order model follows B. Razavi, *Design of Analog CMOS Integrated Circuits*.
