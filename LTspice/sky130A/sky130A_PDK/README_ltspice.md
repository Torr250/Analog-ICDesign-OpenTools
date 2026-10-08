# sky130A para LTspice (sky130A_ltspice_min)

Uso rapido
    .lib "sky130A_ltspice_tt.lib"        (tt ss ff sf fs: deterministas)
    .lib "sky130A_ltspice_mc.lib"        + .step param run 1 300 1   (proceso global)
    .lib "sky130A_ltspice_mm.lib"        (mismatch por instancia)
    .lib "sky130A_ltspice_mcmm.lib"      (ambos)
Secciones: las mismas 49 de sky130.lib.spice (tt ss ff sf fs, ll hl lh hh, ss_ll ... ff_hh, todas las
_mm y mc) + MM y MCMM (mismatch solo / proceso+mismatch con parametros tt). Se usan igual:
    .lib "sky130A_ltspice.lib" ss_hl      o el archivo plano   .lib "sky130A_ltspice_ss_hl.lib"
Los sufijos de res/cap (ll hl lh hh) solo cambian resistencias/capacitores, que no se traducen: para
estos 6 FET dan EXACTAMENTE lo mismo que su corner base (ss_hl == ss). Existen para que un netlist
pueda cambiar de seccion sin editar nombres. sufijo _mm = mismatch por instancia activo; mc = proceso
global (usar con .step param run 1 N 1). Nota: el original no define sf_lh ni sf_lh_mm; tampoco aqui.
Dispositivos (subcircuitos con parametros l w nf mult ad as pd ps nrd nrs):
    xnfet_01v8 xpfet_01v8 xnfet_01v8_lvt xpfet_01v8_lvt xnfet_g5v0d10v5 xpfet_g5v0d10v5

## Validacion
* Las 24 secciones deterministas (tt..ff_hh): Id y Cgg de 23 geometrias contra el PDK completo en
  ngspice, diferencia 0 (--smoke-test). Las secciones _mm y mc: solo verificacion estatica; MC y
  mismatch validados con las corridas de LTspice descritas abajo (secciones mc, mm, mcmm).
* OP determinista (tt) en LTspice: 23 geometrias, incluidas nf=2/m=2 y bordes de W, diferencia maxima
  vs ngspice 0.0005 %.
* Monte Carlo de proceso global (L=0.55u, 300 pasos): sigma/mu nfet 0.59 %, pfet 0.74 %
  (ngspice, sensibilidades: 0.61 % / 0.76 %). Pares identicos: corr = 1.
* Mismatch con nf/m distintos de 1: NO validado en LTspice (la formula de area es la del PDK).

## AVISO: no uses L exactamente en un borde de bin
Los modelos estan binneados en L. Con L exactamente igual a un borde, la respuesta a la variacion
global de proceso (sw_polycd) difiere entre LTspice y ngspice (en ngspice ademas hay un cambio de
pendiente cerca del borde). Con L = borde + 10 nm coinciden a tres decimales en los 45 bordes
medidos. Afecta SOLO la sigma del Monte Carlo de proceso; el punto de operacion nominal y las
esquinas coinciden a ~1e-5 tambien en el borde.

Recomendacion: usa L >= borde + 10 nm (0.51u en lugar de 0.5u, 1.01u en lugar de 1u, ...).
Si necesitas L exactamente en el borde, compara con ngspice antes de confiar en la sigma.

Bordes de L (um) y razon LT/ng de la sensibilidad a sw_polycd medida EN el borde
(alta: >25 % o signo opuesto; media: 5-25 %; baja: <5 %):

    dispositivo        L_borde(um)  LT/ng(sens. sw_polycd)  severidad
    nfet_01v8               0.15                    1.00  baja
    nfet_01v8               0.18                    1.08  media
    nfet_01v8               0.25                    0.35  alta
    nfet_01v8                0.5                    0.69  alta
    nfet_01v8                  1                    1.06  media
    nfet_01v8                  2                    0.94  media
    nfet_01v8                  4                    1.00  baja
    nfet_01v8                  8                    1.01  baja
    nfet_01v8_lvt           0.15                    1.00  baja
    nfet_01v8_lvt           0.18                    0.66  alta
    nfet_01v8_lvt           0.25                    0.58  alta
    nfet_01v8_lvt            0.5                    1.00  baja
    nfet_01v8_lvt              1                    1.07  media
    nfet_01v8_lvt              2                   -0.58  alta
    nfet_01v8_lvt              4                    0.84  media
    nfet_01v8_lvt              8                    1.00  baja
    pfet_01v8               0.15                    1.00  baja
    pfet_01v8               0.18                    1.21  media
    pfet_01v8               0.25                    1.54  alta
    pfet_01v8                0.5                    1.36  alta
    pfet_01v8                  1                    1.06  media
    pfet_01v8                  2                    0.92  media
    pfet_01v8                  4                    1.05  media
    pfet_01v8                  8                    0.94  media
    pfet_01v8_lvt           0.35                    1.00  baja
    pfet_01v8_lvt            0.5                    1.07  media
    pfet_01v8_lvt              1                    1.14  media
    pfet_01v8_lvt            1.5                    0.93  media
    pfet_01v8_lvt              2                    0.99  baja
    pfet_01v8_lvt              4                    1.00  baja
    pfet_01v8_lvt              8                    0.97  baja
    nfet_g5v0d10v5           0.5                    1.00  baja
    nfet_g5v0d10v5           0.6                    0.91  media
    nfet_g5v0d10v5           0.8                    0.90  media
    nfet_g5v0d10v5             1                    1.03  baja
    nfet_g5v0d10v5             2                    1.02  baja
    nfet_g5v0d10v5             4                    1.01  baja
    nfet_g5v0d10v5             8                    0.99  baja
    pfet_g5v0d10v5           0.5                    1.00  baja
    pfet_g5v0d10v5           0.6                    0.98  baja
    pfet_g5v0d10v5           0.8                    0.84  media
    pfet_g5v0d10v5             1                    0.47  alta
    pfet_g5v0d10v5             2                    1.02  baja
    pfet_g5v0d10v5             4                    1.02  baja
    pfet_g5v0d10v5             8                    0.95  media

Bordes de W (um), sin medir en MC: 0.42, 0.55 (segun dispositivo), 0.75 (5 V), 1, 3, 5, 7, 15, 20.

Detalle: medido solo en L = borde y L = borde + 10 nm (no por debajo del borde), con W = 2u,
barriendo sw_polycd = -3, 0, +3 nm (test4_bordes_bin).

Aviso automatico:
    python check_bin_edges.py mi_circuito.cir otro.net esquema.asc
Revisa lineas  X.. xnfet_01v8 l=0.5u ..  (y .asc con SYMBOL/SpiceLine); tolerancia 5 nm; codigo de
salida 2 si hay L en borde. Las L dadas por .param/expresiones salen como "nota": revisalas a mano.
Con el generador: python make_min_pdk.py --target ltspice ... --check-netlist mi_circuito.cir
