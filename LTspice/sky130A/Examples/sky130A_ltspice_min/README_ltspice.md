# sky130A for LTspice (sky130A_ltspice_min)

## What it is and why it exists

The sky130A PDK is written for ngspice: geometry in micrometers through `.option scale`, random draws with
`AGAUSS`, a `.model` per bin inside the subcircuits and a different structure of corner sections. LTspice
cannot read it. `make_min_pdk.py --target ltspice` translates the 6 continuous FETs
(`nfet_01v8`, `pfet_01v8`, `nfet_01v8_lvt`, `pfet_01v8_lvt`, `nfet_g5v0d10v5`, `pfet_g5v0d10v5`) to LTspice
without needing ngspice or the original LTspice-edited files:

* geometry in METERS (`l=0.15u`, no `.option scale`), parameters `l w nf mult ad as pd ps nrd nrs sa sb sd`;
* per-instance mismatch: the PDK `delvto` is kept and `AGAUSS(0,1,1)` becomes `gauss(1)` in a `.param` inside the
  subcircuit (LTspice draws one value per instance);
* global process variation: `.param` with `gauss(sigma)` at global level (one draw per `.step`);
* `xnfet_*` / `xpfet_*` wrappers that compute `ad/as/pd/ps/nrd/nrs` from `w` and `nf`;
* the same 49 corner sections as `sky130.lib.spice` plus `MM` and `MCMM`, as one flat file per section
  (macOS friendly) and as a single `sky130A_ltspice.lib` with sections.

## Quick use

Put the `.lib` files and the `sky130A_ltspice/` folder together (next to your `.asc` / `.cir`), or give the
absolute path in quotes.

    .lib "sky130A_ltspice_tt.lib"        (tt ss ff sf fs: deterministic)
    .lib "sky130A_ltspice_mc.lib"        + .step param run 1 300 1   (global process variation)
    .lib "sky130A_ltspice_mm.lib"        (per-instance mismatch)
    .lib "sky130A_ltspice_mcmm.lib"      (both)

Sections: the same 49 of `sky130.lib.spice` (tt ss ff sf fs, ll hl lh hh, ss_ll ... ff_hh, all the `_mm` ones and
`mc`) plus `MM` and `MCMM` (mismatch only / process + mismatch with tt parameters). They are used the same way:

    .lib "sky130A_ltspice.lib" ss_hl      or the flat file   .lib "sky130A_ltspice_ss_hl.lib"

The res/cap suffixes (ll hl lh hh) only change resistors and capacitors, which are not translated: for these 6 FETs
they give EXACTLY the same as their base corner (`ss_hl == ss`). They exist so that a netlist can change section
without editing names. The `_mm` suffix means per-instance mismatch is on; `mc` is global process variation (use it
with `.step param run 1 N 1`). The original does not define `sf_lh` or `sf_lh_mm`; neither does this one.

## How to instantiate the transistors

Use the wrappers. Subcircuit parameters: `l w nf m` (default `l` depends on the device, `w=1u`, `nf=1`, `m=1`).
`ad as pd ps nrd nrs` are computed from `w` and `nf`. Units are SI: write `l=0.15u w=2u`.

    X1 d g s b xnfet_01v8 l=0.15u w=1u nf=1 m=1
    X2 d g s b xpfet_01v8 l=0.15u w=2u

| Wrapper | Device |
|---|---|
| `xnfet_01v8`, `xpfet_01v8` | 1.8 V |
| `xnfet_01v8_lvt`, `xpfet_01v8_lvt` | 1.8 V low-Vt |
| `xnfet_g5v0d10v5`, `xpfet_g5v0d10v5` | 5 V |

The core subcircuits `sky130_fd_pr__nfet_01v8`, ... are also available (they take `mult` instead of `m`, and
`ad as pd ps nrd nrs` must be given by you; `nrd = nrs = -1` means "PDK default").

In a schematic use the `xnch` / `xpch` symbols of the repository (`LTspice/sky130A/xnch.asy`, `xpch.asy`): set
`SpiceModel` to the wrapper name (for example `xnfet_01v8`), `Value` to `w=1u` and `Value2` to `l=0.15u`.

### Example: CMOS inverter

    * CMOS inverter - sky130A (LTspice)
    .lib "sky130A_ltspice_tt.lib"
    Xp out in vdd vdd xpfet_01v8 l=0.15u w=2u
    Xn out in 0 0     xnfet_01v8 l=0.15u w=1u
    Vdd vdd 0 1.8
    Vin in 0 pulse(0 1.8 0.2n 50p 50p 1n 2n)
    Cl out 0 10f
    .tran 10p 6n
    .meas tran tpHL TRIG V(in) VAL=0.9 RISE=1 TARG V(out) VAL=0.9 FALL=1
    .meas tran tpLH TRIG V(in) VAL=0.9 FALL=1 TARG V(out) VAL=0.9 RISE=1
    .end

Reference values from ngspice with the original PDK and the same geometry and the same `ad/as/pd/ps/nrd/nrs`
that the wrapper computes: `tpHL = 40.55 ps`, `tpLH = 50.88 ps` (the same values come out of the translated
libs run in ngspice). The LTspice transient of this exact circuit has not been compared; for DC the agreement is
shown in the next section.

### Example: Monte Carlo (300 runs)

    .lib "sky130A_ltspice_mcmm.lib"
    .step param run 1 300 1
    * circuit as above, plus a measurement of interest, e.g. .meas tran tpHL ...

To measure DC quantities under `.step`, use a dummy sweep and `.meas DC`; `.meas OP` fails with `.step`:

    V9 x9 0 0
    R9 x9 0 1k
    .dc V9 0 1 1
    .meas DC id1 FIND I(Vd1) AT 0

## ngspice vs LTspice comparison

| Check | Result |
|---|---|
| Translated libs vs full PDK, both in ngspice (`--smoke-test`): 24 deterministic sections, Id and Cgg of 23 geometries (bins, `nf`, `mult`), core and wrapper | difference 0 |
| Deterministic OP in LTspice (`test1_op_tt.cir`), 23 geometries incl. `nf=2 m=2` and W bin edges | max 0.0005 % vs ngspice |
| `gauss(x)` in LTspice | N(0, sigma = x) (checked in LTspice with gf180 `test0`, sigma 0.326 for `gauss(1/3)` and 0.972 for `(1/3)*gauss(3)`) |

Monte Carlo, sigma/mean of Id (LTspice measured / ngspice reference), W = 2u, nfet and pfet:

| Case | Runs | nfet | pfet | Notes |
|---|---|---|---|---|
| `mc`, L = 0.55u (inside a bin) | 300 | 0.59 % / 0.61 % | 0.74 % / 0.76 % | identical pairs: correlation 1.000 |
| `mc`, L = 0.5u (bin edge) | 1000 | 0.60 % / 0.70 % | 0.84 % / 0.76 % | edge effect, see below |
| `mm`, L = 0.5u | 300 | 1.67 % / 1.65 % | 2.01 % / 2.06 % | correlation 0.05, sd(di)/sd(i) = 1.38 (1.41 expected) |
| `mcmm`, L = 0.5u | 300 | 1.80 % / 1.94 % | 2.11 % / 2.23 % | correlation 0.18, sd(di)/sd(i) = 1.27 |

With 300 runs the sigma has about 4 % relative uncertainty on each side. The `mismatch` with `nf` or `m`
different from 1 has NOT been validated in LTspice (the area formula is the one from the PDK).

## WARNING: do not use L exactly on a bin edge

The models are binned in L. With L exactly equal to an edge, the response to global process variation
(`sw_polycd`) differs between LTspice and ngspice (in ngspice there is also a change of slope near the edge). With
L = edge + 10 nm they agree to three decimals on the 45 edges measured. It affects ONLY the sigma of the process
Monte Carlo; the nominal operating point and the corners agree to ~1e-5 on the edge as well.

Recommendation: use L >= edge + 10 nm (0.51u instead of 0.5u, 1.01u instead of 1u, ...). If you need L exactly on
the edge, compare with ngspice before trusting the sigma.

L edges (um) and LT/ng ratio of the sensitivity to `sw_polycd` measured AT the edge
(high: >25 % or opposite sign; medium: 5-25 %; low: <5 %):

    device             L_edge(um)   LT/ng(sens. sw_polycd)  severity
    nfet_01v8               0.15                    1.00  low
    nfet_01v8               0.18                    1.08  medium
    nfet_01v8               0.25                    0.35  high
    nfet_01v8                0.5                    0.69  high
    nfet_01v8                  1                    1.06  medium
    nfet_01v8                  2                    0.94  medium
    nfet_01v8                  4                    1.00  low
    nfet_01v8                  8                    1.01  low
    nfet_01v8_lvt           0.15                    1.00  low
    nfet_01v8_lvt           0.18                    0.66  high
    nfet_01v8_lvt           0.25                    0.58  high
    nfet_01v8_lvt            0.5                    1.00  low
    nfet_01v8_lvt              1                    1.07  medium
    nfet_01v8_lvt              2                   -0.58  high
    nfet_01v8_lvt              4                    0.84  medium
    nfet_01v8_lvt              8                    1.00  low
    pfet_01v8               0.15                    1.00  low
    pfet_01v8               0.18                    1.21  medium
    pfet_01v8               0.25                    1.54  high
    pfet_01v8                0.5                    1.36  high
    pfet_01v8                  1                    1.06  medium
    pfet_01v8                  2                    0.92  medium
    pfet_01v8                  4                    1.05  medium
    pfet_01v8                  8                    0.94  medium
    pfet_01v8_lvt           0.35                    1.00  low
    pfet_01v8_lvt            0.5                    1.07  medium
    pfet_01v8_lvt              1                    1.14  medium
    pfet_01v8_lvt            1.5                    0.93  medium
    pfet_01v8_lvt              2                    0.99  low
    pfet_01v8_lvt              4                    1.00  low
    pfet_01v8_lvt              8                    0.97  low
    nfet_g5v0d10v5           0.5                    1.00  low
    nfet_g5v0d10v5           0.6                    0.91  medium
    nfet_g5v0d10v5           0.8                    0.90  medium
    nfet_g5v0d10v5             1                    1.03  low
    nfet_g5v0d10v5             2                    1.02  low
    nfet_g5v0d10v5             4                    1.01  low
    nfet_g5v0d10v5             8                    0.99  low
    pfet_g5v0d10v5           0.5                    1.00  low
    pfet_g5v0d10v5           0.6                    0.98  low
    pfet_g5v0d10v5           0.8                    0.84  medium
    pfet_g5v0d10v5             1                    0.47  high
    pfet_g5v0d10v5             2                    1.02  low
    pfet_g5v0d10v5             4                    1.02  low
    pfet_g5v0d10v5             8                    0.95  medium

W edges (um), not measured in MC: 0.42, 0.55 (depending on the device), 0.75 (5 V), 1, 3, 5, 7, 15, 20.

Detail: measured only at L = edge and L = edge + 10 nm (not below the edge), with W = 2u, sweeping
`sw_polycd` = -3, 0, +3 nm (`test4_bin_edges.cir`).

Automatic warning:

    python check_bin_edges.py my_circuit.cir other.net schematic.asc

It checks lines `X.. xnfet_01v8 l=0.5u ..` (and `.asc` files with SYMBOL / SpiceLine); tolerance 5 nm; exit code 2 if
there is an L on an edge. L values given by `.param` or expressions appear as "note": check them by hand. With the
generator: `python make_min_pdk.py --target ltspice ... --check-netlist my_circuit.cir`.

## Limitations

* Only the 6 FETs. No resistors, capacitors, BJTs or diodes.
* `ll hl lh hh` do not change anything for these FETs (see above).
* Mismatch with `nf`/`m` different from 1: not validated in LTspice.
* Validated in LTspice 26.0.1 for Windows. It is built to work in LTspice for macOS (flat files, no relative
  includes beyond the `sky130A_ltspice/` folder) but it has not been run there.
* The random sequence of LTspice is reproducible: different netlists with the same structure show almost the same
  sampling deviation, so do not treat different cases as independent samples.

## Files

    sky130A_ltspice_<section>.lib     flat file per section (+ sky130A_ltspice.lib with all of them)
    sky130A_ltspice/                  models_fet.inc, wrappers.inc, globals.inc, params_<corner>.inc
    check_bin_edges.py                bin-edge warning
    test1_op_tt.cir                   deterministic OP vs ngspice
    test2_mc_*.cir                    Monte Carlo (mc, mm, mcmm, L = 0.5u and 0.55u, 1000 runs)
    test3_polycd_diag.cir, test4_bin_edges.cir, sky130A_ltspice_diag.lib   bin-edge diagnostics
    MANIFEST_ltspice.txt              sha256 of every generated file

## Regenerate

Requires Python 3.9+ (ngspice only for `--smoke-test`). Input: a complete `sky130A` directory.

    python make_min_pdk.py --target ltspice --src PATH/sky130A --dst sky130A_ltspice_min --force [--smoke-test]

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Unknown subcircuit called in: xnfet_01v8` | The library was not found or not loaded. Check the `.lib` path (absolute path in quotes) and that `sky130A_ltspice/` is next to the `.lib`. |
| `.meas OP` FAILS with `.step` | Use the dummy `.dc V9 0 1 1` and `.meas DC ... AT 0`. |
| Sigma of an MC run differs from ngspice by tens of % | Check L for a bin edge (`check_bin_edges.py`). |

## License

Derived from the SkyWater sky130 PDK (Apache License 2.0, Copyright The SkyWater PDK Authors). The
tools are provided as they are, with no warranty.
