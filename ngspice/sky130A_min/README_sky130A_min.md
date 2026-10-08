# sky130A_min (ngspice)

PDK sky130A reducido para ngspice: conserva solo los 6 FET continuos (1.8 V, 1.8 V LVT y 5 V) y las
49 secciones de esquina del original, con los mismos nombres. Sirve para que ngspice lea el modelo
mucho mas rapido. Generado por make_min_pdk.py; MANIFEST.txt lista cada archivo con su sha256.

## Dispositivos
nfet_01v8  pfet_01v8  nfet_01v8_lvt  pfet_01v8_lvt  nfet_g5v0d10v5  pfet_g5v0d10v5
Mismos nombres de subcircuito que el PDK original (sky130_fd_pr__nfet_01v8, etc.).
NO incluye: BJT, diodos, resistencias, capacitores, SONOS, RF ni celdas digitales. Si un netlist los
usa, ngspice dara "unknown subckt". Para otros FET: --devices en el generador.

## Estructura
    libs.tech/combined/
        sky130.lib.spice                    lib completa (49 secciones), includes podados
        sections/sky130_<seccion>.lib.spice una lib por seccion (49 archivos)  <- recomendada
        continuous/                         modelos y parametros (copias identicas al original)
    MANIFEST.txt

## Uso
En el netlist, solo cambia la ruta de la lib:

    .lib /ruta/sky130A_min/libs.tech/combined/sky130.lib.spice tt           (lib completa)
    .lib /ruta/sky130A_min/libs.tech/combined/sections/sky130_tt.lib.spice tt   (una seccion, mas rapido)

El nombre de seccion al final (tt) se repite a proposito: es la seccion .lib dentro del archivo, y
es la misma que tiene el original, asi que los netlists existentes no cambian. Secciones:
tt ss ff sf fs; ll hl lh hh (res/cap, no afectan a los FET); combinadas ss_ll ... ff_hh; todas con
sufijo _mm (mismatch por instancia); y mc (proceso global, para .step/.control con semillas).

## Velocidad (inversor, referencia)
    PDK completo, sky130.lib.spice      ~4.9 s      PDK reducido, sky130.lib.spice      ~2.5 s
    PDK completo, una seccion           ~0.7 s      PDK reducido, una seccion           ~0.6 s
El mayor ahorro viene de usar la lib de una sola seccion; reducir dispositivos ayuda sobre todo
con la lib multi-seccion. Los tiempos dependen de la maquina.

## Que cambia respecto al original
* sky130.lib.spice: solo se podan los .include de modelos descartados.
* continuous/models_fet.spice: lista solo los 6 dispositivos.
* sections/*: contenido de la seccion identico (verificado linea a linea); los includes llevan
  prefijo ../ porque la lib vive un nivel mas abajo.
* Todo lo demas son copias byte a byte (estado "identico" en MANIFEST.txt).

## Validacion (--smoke-test, requiere ngspice)
Compara Id en DC entre el PDK completo y el reducido en las esquinas deterministas (deben coincidir)
y comprueba que tt_mm y mc corran. Ademas, la verificacion de integridad corre siempre: todos los
includes existen, las secciones son identicas al original y la opcion scale esta presente.

## Regenerar
    python make_min_pdk.py --src RUTA/sky130A --dst sky130A_min --split-sections --force
    python make_min_pdk.py --check-netlist mi_circuito.cir     (avisa de dispositivos o secciones faltantes)

## Relacionado
sky130A_ltspice_min es otra cosa: traduccion a LTspice (--target ltspice), con su propio README_ltspice.md.
