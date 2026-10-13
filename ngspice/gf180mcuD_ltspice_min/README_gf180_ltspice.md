# gf180mcuD for LTspice (macOS and Windows): flat, segmented libraries

## What it is and why it exists

The native gf180mcuD model file (`sm141064.ngspice`, 47 764 lines, 1.3 MB) is written for ngspice: nested
`.lib 'sm141064.ngspice' <section>` calls, parameters that come from a separate `design.ngspice`, random draws
with `AGAUSS`, the `?:` operator in the SAB subcircuits and the instance parameter `mulu0` for the k mismatch.
LTspice cannot read it as it is, and editing the file by hand every time the PDK changes is error prone.

`make_min_gf180.py` generates, from the NATIVE file, one library per case:

* **flat and self-contained** (about 160 KB, 7 700 lines instead of 47 764): no nested `.lib`, no relative paths,
  no dependence on `design.ngspice`;
* **segmented**: one file per corner / Monte Carlo case, so LTspice only reads what the simulation needs;
* **reduced**: only the requested devices (by default the 3.3 V and 6 V nfet/pfet, with the 5 V ones taken from the
  6 V models) and only the global parameters those models use;
* **translated to LTspice**: `AGAUSS(nom,abs,sig)` becomes `gauss(abs/sig)`; a global parameter is drawn once
  per `.step`; mismatch is drawn per instance;
* **ASCII, LF line endings, one file per case**: it works the same on macOS and Windows.

## Cases (files `gf180mcuD_ltspice_<case>.lib`)

| Case | Native section | sw_stat_global | sw_stat_mismatch | Use |
|---|---|---|---|---|
| `tt`, `ss`, `ff`, `sf`, `fs` | typical, ss, ff, sf, fs | 0 | 0 | deterministic corners |
| `tt_mm`, `ss_mm`, `ff_mm`, `sf_mm`, `fs_mm` (`mm` = `tt_mm`) | same | 0 | 1 | per-instance mismatch on that corner |
| `mc` | statistical | 1 | 0 | global process variation |
| `mcmm` | statistical | 1 | 1 | process + mismatch |

`mc_skew`, `res_mc_skew`, `cap_mc_skew` = 3 and `fnoicor` = 0 (values from `design.ngspice`) are at the top of each file.

## How to use it

One line in the netlist or in the schematic (the lib has no sections, so `.lib "file"` works):

    .lib "gf180mcuD_ltspice_tt.lib"

* Put the `.lib` files in the same folder as your `.asc` / `.cir`, or use the absolute path in quotes
  (for example `.lib "gf180mcuD_PDK/gf180mcuD_ltspice_tt.lib"`).
* Switching case is a change of file name: `..._ss.lib`, `..._mcmm.lib`, ...
* Monte Carlo: `.lib "gf180mcuD_ltspice_mcmm.lib"` and `.step param run 1 300 1`.

### Instantiating the transistors

Wrappers `xnfet_03v3`, `xpfet_03v3`, `xnfet_06v0`, `xpfet_06v0`, `xnfet_05v0`, `xpfet_05v0`
(and `xnfet_06v0_nvt` if generated with it). Parameters: `l w nf m`. `ad as pd ps nrd nrs` are computed from `w` and `nf`.
Units are SI (`l=0.28u w=2u`).

    X1 d g s b xnfet_03v3 l=0.28u w=2u nf=1 m=1

Default `l` / `w` of the wrappers: 03v3: 0.28u / 2u; 05v0: nfet 0.6u, pfet 0.5u / 2u; 06v0: nfet 0.7u, pfet 0.55u / 2u.

In a schematic use the `xnch` / `xpch` symbols of the repository (`LTspice/gf180mcuD/xnch.asy`, `xpch.asy`):
`SpiceModel` = `xnfet_03v3`, `Value` = `w=2u`, `Value2` = `l=0.28u`. See `DC_Sweep_03V3.asc`.

### Example: CMOS inverter

    * CMOS inverter - gf180mcuD (LTspice)
    .lib "gf180mcuD_ltspice_tt.lib"
    Xp out in vdd vdd xpfet_03v3 l=0.28u w=4u
    Xn out in 0 0     xnfet_03v3 l=0.28u w=2u
    Vdd vdd 0 3.3
    Vin in 0 pulse(0 3.3 0.2n 100p 100p 1n 2n)
    Cl out 0 20f
    .tran 10p 6n
    .meas tran tpHL TRIG V(in) VAL=1.65 RISE=1 TARG V(out) VAL=1.65 FALL=1
    .meas tran tpLH TRIG V(in) VAL=1.65 FALL=1 TARG V(out) VAL=1.65 RISE=1
    .end

Reference from ngspice with the native PDK (`design.ngspice` + `sm141064.ngspice`, section `typical`) and the same
geometry and `ad/as/pd/ps/nrd/nrs`: `tpHL = 63.73 ps`, `tpLH = 69.53 ps` (the generated library run in ngspice gives
exactly the same). The LTspice transient of this circuit has not been compared; the DC comparisons are below.

To measure DC quantities under `.step`, use a dummy sweep and `.meas DC` (`.meas OP` fails with `.step`):

    V9 x9 0 0
    R9 x9 0 1k
    .dc V9 0 1 1
    .meas DC id0 FIND I(Vd0) AT 0

## What changes with respect to the native PDK / to a hand-edited sm141064

1. **Random draws:** `agauss(0,1,3)` -> `gauss((1)/(3))`. In LTspice `gauss(x)` is N(0, sigma = x), so sigma = 1/3, the
   same as ngspice (`{(1/3)*gauss(3)}` would give sigma = 1; `test0_gauss_sigma.cir` checks it).
2. **Mismatch:** `delvto='mis_vth*sw_stat_mismatch'` is kept and drawn per instance. **`mulu0` is omitted**
   (LTspice does not support it), so the mobility mismatch `mis_k` is not modelled. In ngspice, with and without
   `mulu0`, the sigma of Id is practically the same (1.29 % vs 1.33 %, 500 samples).
3. **pd / ps:** the wrappers use the perimeter `2*int((nf+1)/2)*(W/nf+0.18u)` (convention of the gf180mcu xschem
   symbols). In the old `gf180mcuD_ltspice.lib`, pd/ps were like ad/as (an area, not a perimeter), which cancelled the
   sidewall capacitances of the junctions: Cdd changes by ~20-30 % (nfet L = 0.28u W = 2u: 1.93 fF -> 2.30 fF at
   Vds = 0); Id and Cgg do not change. `--legacy-wrapper` reproduces the old behaviour.
4. **Omitted:** the `*_dss` subcircuits (SAB, they use the `?:` operator) and the resistors, capacitors, BJTs and
   diodes. `--keep-dss` keeps the SAB ones (with `?:` -> `if()`).
5. **nf:** the old wrapper did not pass `nf` to the model (always `nf=1`, although ad/as/pd/ps did use it); now it does.
   Effect on Id (nfet L = 0.6u): nf = 2, W = 4u: +2.3 %; nf = 4, W = 10u: +0.6 %; nf = 8, W = 20u: +0.7 %.
6. Only the global parameters used by the selected models are kept.

## ngspice vs LTspice comparison

**Libraries vs native PDK, both in ngspice (`--smoke-test`):** with the random draws replaced by constants, Id (2
biases) and Cgg of 22 devices / geometries (several bins, `nf`, `m`, L and W) in the 12 deterministic and mismatch
cases: maximum relative difference 0 (identical). It validates corners, `nf`/`m`, mismatch (`delvto`) and the wiring of
the statistical parameters. It does not validate the LTspice engine; that is what the tests below do.

**Deterministic OP in LTspice 26.0.1 (`test1_op_<case>.cir`)**, Id of 12 devices / geometries (including `nf=2 m=2`)
against ngspice with the native PDK:

| Case | tt | ss | ff | sf | fs |
|---|---|---|---|---|---|
| Max difference | 0.023 % | 0.032 % | 0.016 % | 0.023 % | 0.028 % |

**Random draws:** `test0_gauss_sigma.cir`, 1000 steps: `gauss(1/3)` -> sigma 0.326, `(1/3)*gauss(3)` -> sigma 0.972, so
`gauss(x)` = N(0, sigma = x).

**Monte Carlo and mismatch in LTspice (`test3_mc_<case>.cir`)**: 300 runs, six transistors
(nfet / pfet 03v3 L = 0.55u, 06v0 L = 0.75u, 05v0 L = 0.6u, all W = 2u), against ngspice (the same libs with
`gauss` -> `agauss`, different seeds).

| Case | Mean of Id | sigma/mean |
|---|---|---|
| `mc` | within 0.45 % | -8 % ... +3 % |
| `mcmm` | within 0.45 % | -8 % ... +3 % |
| `mm`, `ss_mm`, `ff_mm`, `sf_mm`, `fs_mm` | within 0.13 % | 06v0 / 05v0: -5 % ... +7 %; 03v3: -9 % ... -13 % (see below) |
| `mm`, 1000 runs (`test3_mc_mm_1000.cir`), ngspice 3000 runs | within 0.02 % | all six devices: -7 % ... +4 % |
| `mm`, `pfet_03v3` only, 3000 runs (`test3_mc_mm_pfet03v3_3000.cir`), ngspice 6000 runs | mean 130.76 uA vs 130.72 uA (+0.03 %) | -4.4 % (0.603 % vs 0.631 %) |

With 300 runs the sigma has about 4 % relative uncertainty in LTspice and in ngspice. The apparent bias of -10 %
to -13 % in the 03v3 mismatch with 300 runs was sampling noise: with 1000 runs it is -2 % (nfet) and -7 % (pfet,
about 3 combined sigmas, the only value that stays a bit high). A dedicated 3000-run test of pfet_03v3 gives -4.4 %
(about 2.7 combined sigmas): a small residual, probably real, difference in the pfet_03v3 mismatch of at most a few
percent of sigma (0.03 pp of absolute sigma/mean); the mean current agrees within 0.03 %, so it has no practical impact. In LTspice the random sequence seems reproducible per
run index, so the five `*_mm` cases show almost the same deviation: they are not five independent samples.
Correlations behave as expected (instance mismatch ~0; global MC: n-n 0.66-0.97, n-p 0.42).

**Bin edges (`test2_mc_<case>.cir`):** nfet / pfet 03v3 at L = 0.5u (edge) and 0.55u (not an edge) are compared with
ngspice; see Known limitations for the rule.

## Known limitations

* **Bin edges:** BSIM4 level 54 is binned (`lmin/lmax/wmin/wmax`). When L is *exactly* on an internal bin edge (for
  example nfet_06v0 L = 0.7u, where bins .0 and .1 share `lmax = lmin = 0.7e-6`) LTspice deviates by ~1.7 % from ngspice,
  which is continuous there. Avoid L exactly on an edge (rule used for sky130: edge + 10 nm). Away from the edges
  the difference is < 0.04 %. That is why `test1` uses L = 0.75u for the nfet_06v0.
* **`mis_k` (`mulu0`) mismatch is not modelled.**
* Only FETs: no resistors, capacitors, BJTs, diodes or SAB (`*_dss`) variants unless `--keep-dss`.
* Validated in LTspice 26.0.1 for Windows. The files are made for LTspice for macOS (flat, ASCII, LF, no relative
  includes) but they have not been run there.

## Files

    gf180mcuD_ltspice_<case>.lib      13 libraries (tt ss ff sf fs, *_mm, mm, mc, mcmm)
    test0_gauss_sigma.cir             sigma of gauss()
    test1_op_<case>.cir               deterministic OP vs ngspice (tt ss ff sf fs)
    test2_mc_{mc,mm,mcmm}.cir         MC, 300 runs, L = 0.5u vs 0.55u
    test3_mc_<case>.cir               MC / mismatch with 03v3, 06v0 and 05v0 (7 cases)
    test3_mc_mm_1000.cir              mismatch with 1000 runs
    test3_mc_mm_pfet03v3_3000.cir     mismatch of pfet_03v3 only, 3000 runs
    MANIFEST_gf180_ltspice.txt        sha256 of every library
    tools/                            generator and test scripts

## Regenerate

Requires Python 3.9+; ngspice for `--smoke-test` and `--write-tests`. Input: the folder with the native
`sm141064.ngspice` (and `design.ngspice` for the tests), as distributed by open_pdks / gf180mcu-pdk.

    python make_min_gf180.py --src FOLDER_WITH_sm141064.ngspice --dst gf180mcuD_ltspice_min --force --smoke-test --write-tests
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3     # 3.3 V only
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3 nfet_06v0 pfet_06v0 nfet_06v0_nvt

`make_min_gf180.py` imports `make_min_pdk.py` (expression translation); keep both scripts together.
The additional tests (`test1` sf / fs and `test3`) come from `gf180_tests2.py`, `test3_mc_mm_1000.cir` from `gf180_tests3.py` and `test3_mc_mm_pfet03v3_3000.cir` from `gf180_tests4.py`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Unknown subcircuit called in: xnfet_03v3` | The library was not found. Use the absolute path in quotes or put it next to the netlist. |
| `.meas OP` FAILS with `.step` | Use the dummy `.dc V9 0 1 1` and `.meas DC ... AT 0`. |
| ~1.7 % difference in Id at some L | L exactly on a bin edge (see Known limitations). Move L by 10 nm. |
| MC sigma off by a few % from ngspice | Normal with 300 runs (~4 % uncertainty per side). Use more runs. |
| LTspice rejects `mulu0` | Do not use `--keep-mulu0`; LTspice does not support it. |

## License

Derived from the GlobalFoundries gf180mcu PDK (Apache License 2.0, Copyright GlobalFoundries PDK Authors);
see the license header of the original `sm141064.ngspice`. The tools are provided as they are, with no warranty.
