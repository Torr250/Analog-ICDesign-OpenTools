# gf180mcuD para LTspice (macOS y Windows) - libs segmentadas

Generado por `make_min_gf180.py` a partir del `sm141064.ngspice` NATIVO del PDK.
Cada archivo `gf180mcuD_ltspice_<caso>.lib` es plano y autocontenido (~160 KB en vez de 1.3 MB):
no hay `.lib` anidados, ni rutas relativas, ni `design.ngspice`, ni `gf180mcuD_ltspice.lib`.

## Uso (una sola linea en el netlist/esquematico)

    .lib "gf180mcuD_ltspice_tt.lib"

* Pon los `.lib` en la misma carpeta que tu `.asc`/`.cir` o usa la ruta absoluta entre comillas.
* Instancias:  `X1 d g s b xnfet_03v3 l=0.28u w=2u nf=1 m=1`  (igual para xpfet_03v3, xnfet_06v0,
  xpfet_06v0, xnfet_05v0, xpfet_05v0). ad/as/pd/ps/nrd/nrs se calculan solos.
* En un esquematico, SpiceModel = `xnfet_03v3`, etc. (los simbolos xnch/xpch de tu repo sirven).

## Casos

| archivo (`gf180mcuD_ltspice_...lib`) | seccion nativa | sw_stat_global | sw_stat_mismatch |
|---|---|---|---|
| tt, ss, ff, sf, fs | typical, ss, ff, sf, fs | 0 | 0 |
| tt_mm, ss_mm, ff_mm, sf_mm, fs_mm (mm = tt_mm) | idem | 0 | 1 |
| mc | statistical | 1 | 0 |
| mcmm | statistical | 1 | 1 |

Monte Carlo: `.lib "gf180mcuD_ltspice_mcmm.lib"` + `.step param run 1 300 1`.
Un parametro global se sortea una vez por paso; el mismatch se sortea por instancia.
`mc_skew`, `res_mc_skew`, `cap_mc_skew` = 3 y `fnoicor` = 0 (valores de design.ngspice) estan al inicio de cada archivo.

## Que cambia respecto al PDK nativo / a tu sm141064 editado

1. **Sorteos**: `agauss(0,1,3)` -> `gauss((1)/(3))`. En LTspice `gauss(x)` es N(0, sigma=x), asi que
   sigma = 1/3, igual que ngspice. (`{(1/3)*gauss(3)}` daria sigma = 1, tres veces mayor;
   `test0_gauss_sigma.cir` lo comprueba en tu LTspice.)
2. **Mismatch**: `delvto='mis_vth*sw_stat_mismatch'` se conserva y se sortea por instancia.
   **`mulu0` se omite** (LTspice no lo admite): el mismatch de movilidad `mis_k` no se modela. En ngspice,
   con y sin `mulu0` la sigma de Id es indistinguible (1.29 % vs 1.33 %, 500 muestras).
3. **pd/ps**: los wrappers usan el perimetro `2*int((nf+1)/2)*(W/nf+0.18u)` (convencion de los simbolos
   xschem de gf180mcu). En `gf180mcuD_ltspice.lib` pd/ps eran como ad/as (un area, no un perimetro), lo
   que anulaba las capacidades de pared lateral de las uniones: Cdd cambia ~20-30 % (p. ej. nfet
   L=0.28u W=2u: 1.93 fF -> 2.30 fF a Vds=0); Id y Cgg no cambian. `--legacy-wrapper` reproduce el anterior.
4. **Se omiten** los subcircuitos `*_dss` (SAB; usan el operador `?:` que LTspice no tiene) y las
   resistencias/capacitores/BJT/diodos. `--keep-dss` los conserva (con `?:` -> `if()`).
5. **nf**: el wrapper original no pasaba `nf` al modelo (siempre nf=1, aunque ad/as/pd/ps si usaban nf); aqui si.
   Efecto en Id (nfet L=0.6u): nf=2 W=4u +2.3 %, nf=4 W=10u +0.6 %, nf=8 W=20u +0.7 % (se reduce Id al aplicar nf).
6. Solo se conservan los parametros globales que usan los modelos elegidos.

## Verificacion (ngspice, PDK nativo vs estas libs)

`--smoke-test`: con los sorteos sustituidos por constantes, Id (2 sesgos) y Cgg de 22 dispositivos/geometrias
(nf, m, L y W de varios bins) en los 12 casos: diferencia relativa maxima 0 (identicos).
Esto valida corners, nf/m, mismatch (delvto) y el cableado de parametros estadisticos.
NO valida el motor de LTspice: para eso estan los tests.

## Pruebas para correr en LTspice

* `test0_gauss_sigma.cir` - sigma de gauss(1/3) y (1/3)*gauss(3) (1000 pasos).
* `test1_op_{tt,ss,ff}.cir` - Id contra ngspice nativo (<0.1 %). Incluye nf=2 m=2 y bordes de bin L=0.5u, 1.2u.
* `test2_mc_{mc,mm,mcmm}.cir` - 300 corridas, sigma/media de Id contra ngspice. Compara L=0.5u (borde de
  bin) con L=0.55u: en ngspice el gf180 es suave en los bordes (salto de Id <= 0.08 %); en sky130 LTspice
  difirio en el borde, aqui se comprueba.

## Regenerar

    python make_min_gf180.py --src CARPETA_CON_sm141064.ngspice --dst gf180mcuD_ltspice_min --force --smoke-test --write-tests
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3     # solo 3.3 V
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3 nfet_06v0 pfet_06v0 nfet_06v0_nvt
