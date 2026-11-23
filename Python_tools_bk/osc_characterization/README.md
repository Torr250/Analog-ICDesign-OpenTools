# osc_characterization.py

Caracterización de **osciladores** (típicamente diferenciales, también de una sola salida) a partir de simulaciones transitorias de **ngspice**. Está basado en `clock_jitter.py` (cruces direccionales, TIE por ajuste lineal, jitter de periodo y ciclo a ciclo, plegado del ojo), pero con una diferencia de fondo: la frecuencia de un oscilador **no es un dato de entrada**, se **mide** de la propia señal.

Cubre una simulación individual, curvas de sintonía (barrido de un parámetro de control) y esas mismas curvas en varias esquinas PVT. Los resultados se verificaron contra los `.meas` propios de ngspice (597.29 MHz para `CS_Pseudo_diff_N4.spice` y 628.56 MHz para `Ring_InvN3.spice` en condiciones nominales).

---

## 1. Contenido de la carpeta

```
osc_characterization/
├── osc_characterization.py        el script
├── README.md                      este documento
├── CS_Pseudo_diff_N4.spice        oscilador diferencial de 4 etapas con carga de corriente (ejemplo)
├── Ring_InvN3.spice               ring de 3 inversores, una salida, sin control (ejemplo)
├── CS_Pseudo_diff_N4.raw          simulaciones ya hechas, para probar `analyze`
├── Ring_InvN3.raw
└── configs/
    ├── cs_diff_base.json          ajustes comunes del diferencial (los demás heredan de él)
    ├── cs_diff_nominal.json       barrido de ibias, condiciones del netlist
    ├── cs_diff_worst3.json        barrido de ibias en 3 esquinas PVT
    ├── cs_diff_pvt45.json         barrido de ibias en la malla PVT completa (45 esquinas)
    ├── cs_diff_analyze.json       analiza un .raw del diferencial
    ├── ring_vdd.json              barrido de VDD del ring
    └── ring_analyze.json          analiza un .raw del ring
```

## 2. Requisitos

- Python 3 y `ngspice` en el `PATH` (o indícalo con `--ngspice /ruta/ngspice`).
- Librerías de Python:

```bash
pip install spicelib numpy scipy matplotlib --break-system-packages
```

El script solo lee archivos `.raw` en formato ngspice (vía `spicelib`); no depende de ningún PDK en particular.

## 3. Inicio rápido

```bash
cd osc_characterization

# a) Analizar una simulación que ya tienes (.raw)
python3 osc_characterization.py --config configs/cs_diff_analyze.json

# b) Barrer la corriente de polarización del diferencial
python3 osc_characterization.py --config configs/cs_diff_nominal.json

# c) Lo mismo en las tres esquinas PVT (ss/125 °C/3.0 V, typical/60 °C/3.3 V, ff/-40 °C/3.6 V)
python3 osc_characterization.py --config configs/cs_diff_worst3.json
```

Sin JSON, el equivalente de (a) es:

```bash
python3 osc_characterization.py analyze CS_Pseudo_diff_N4.raw \
  --pos "v(n1)" --neg "v(n3)" --vdd 3.3 --isupply "i(v7)" --icore "i(v1)" --probe "v(vcs)" \
  --phase-ref "v(n13)" --phase-sig "v(n24)" --phase-expected -90
```

## 4. Subcomandos y casos que soporta

| Subcomando | Qué hace | Necesita |
|---|---|---|
| `analyze` | Caracteriza **un** `.raw` (todas las métricas de la sección 5) | el `.raw` |
| `sweep` | Corre ngspice variando **una línea** del netlist, analiza cada punto y arma la curva de sintonía; opcionalmente repite el barrido en varias esquinas PVT | el netlist `.spice` |
| `mc` | Monte Carlo (variación global y/o mismatch del PDK gf180mcuD). **Un** valor de control = MC en un punto; **varios** = curvas de sintonía por pieza | el netlist `.spice` |
| `tuning` | Arma la curva de sintonía a partir de `.raw` que ya tienes (sin correr ngspice) | un `.raw` por punto |

Si omites el subcomando y das un `.raw`, se asume `analyze` (`python3 osc_characterization.py archivo.raw --pos ...`).

**Tipos de oscilador y de señal**

| Caso | Cómo se indica |
|---|---|
| Diferencial, con los dos nodos | `--pos "v(n1)" --neg "v(n3)"` (el script calcula pos − neg y además el modo común) |
| Diferencial ya construido en el netlist (fuente `E`) | `--signal "v(n13)"` |
| **Una sola salida** (ring, relajación, etc.) | `--signal "v(n1)" --single-ended` |
| Con parámetro de control (corriente, tensión de control...) | `sweep` con `--line-prefix`, `--template` y `--values` |
| **Sin** parámetro de control, de funcionamiento libre | `analyze`, o `sweep` sobre `VDD`/`TEMP` (ver ejemplo del ring) |
| Varias salidas con relación de fase (I/Q, multifase) | `--phase-ref` y `--phase-sig` |
| Ruido transitorio incluido en la simulación | `--noisy` (quita la nota de "jitter solo numérico") |

## 5. Análisis que realiza

Todas las métricas se calculan **en estado estable** (sección 5.2). En el informe (`osc_summary.txt`) aparecen en este orden.

### 5.1 Verificación de que la simulación es adecuada
Antes de medir, el script revisa que el `.tran` sea suficiente y emite avisos:

- **Puntos por periodo** en el peor caso (umbral `--min-ppp`, 20). Si el paso es muy grueso, la frecuencia, el jitter y los armónicos se degradan.
- **Ciclos de estado estable** (umbral `--min-cycles`, 10). Con pocos ciclos la estadística no es confiable.
- **Estado estable alcanzado**: avisa si no se detectó claramente.
- **Señal que parece de una sola salida** (offset de DC grande respecto a la excursión): sugiere `--single-ended`.

Cuando algo no cumple, **sugiere un `.tran` listo para pegar**: paso ≈ T/200 redondeado a 1-2-5 y tiempo final = inicio del estado estable + `--target-cycles` (50) periodos. Los avisos aparecen al inicio del informe, en `osc_metrics.json` (`warnings`; la clave `suggested_tran` existe solo cuando hay algo que corregir) y, en los barridos, como una columna de conteo de avisos.

### 5.2 Detección del estado estable
Se mide la amplitud y el periodo de **cada ciclo**; el valor final es la mediana del último cuarto de la simulación. El estado estable empieza en el primer ciclo a partir del cual la amplitud se mantiene dentro de ±2 % (`--amp-tol`) y el periodo dentro de ±0.5 % (`--freq-tol`) de ese valor final, más 2 ciclos de margen. Si no se establece con al menos 6 ciclos de margen, se usa la segunda mitad de la simulación y se avisa. Puedes forzar el inicio con `--t-start`.

### 5.3 Frecuencia y periodo
Ajuste lineal de los cruces ascendentes por el umbral (por defecto, el nivel medio de la señal; se cambia con `--threshold`). Reporta frecuencia, periodo y su dispersión. `--freq` es opcional y solo sirve para mostrar la desviación respecto a un valor esperado.

### 5.4 Amplitud y modo común
Amplitud diferencial (pico, pico a pico, rms), extremos, offset y asimetría entre picos; para cada nodo, su rango y valor medio; modo común (valor medio y rizado, que normalmente aparece a 2·f0). `--probe` agrega nodos extra (media y rizado), por ejemplo la tensión del tail.

### 5.5 Arranque (start-up)
Tiempos al 10 % y 90 % de la amplitud final, tasa de crecimiento exponencial y tiempos de asentamiento de amplitud y de frecuencia. Si el primer ciclo ya está cerca de la amplitud final (por un `.ic` muy agresivo), el script lo indica y los tiempos se reportan como "ya alcanzado". Con `.ic`/`uic` el arranque parte de un desbalance impuesto, no de ruido, así que sirve para **comparar** diseños o esquinas, no como valor absoluto.

### 5.6 Potencia y energía
Corriente media sobre periodos enteros → potencia y energía por ciclo. `--isupply` es la corriente **total** de la fuente de alimentación; `--icore` la corriente del **núcleo** (sin ramas de referencia o polarización), y se reportan por separado. La tensión se toma de `--vdd` o, si varía, de una traza (`--vsupply "v(vdd)"`).

### 5.7 Jitter
TIE (error de intervalo de tiempo) respecto a la rejilla ideal ajustada por mínimos cuadrados, jitter de periodo y jitter ciclo a ciclo, para flancos ascendentes y descendentes. **Sin ruido transitorio**, este jitter es solo numérico (error de integración del simulador) y sirve como piso de referencia; el ruido de fase real se estima aparte (por ejemplo con `isfpn.py`).

### 5.8 Diagrama de ojo
Las formas de onda se pliegan sobre la rejilla ideal (ventana de `--ui-window` periodos, `--oversample` puntos por periodo) para obtener el ojo, ciclo de trabajo, pendiente (slew) y tiempos de subida/bajada 10–90 %.

### 5.9 Espectro (FFT coherente)
Se toma un número **entero** de periodos y se remuestrea con spline cúbica a `--ppp` puntos por periodo, de modo que los armónicos caen exactamente en un bin y no hay fuga espectral (`--window rect`; `hann` es opcional). Reporta la fundamental, `--nharm` armónicos en dBc y la **THD**. Si hay pocos puntos por periodo, avisa a partir de qué armónico no es fiable.

### 5.10 Fase entre salidas
Fase de cada señal de `--phase-sig` respecto a `--phase-ref`, medida por la fundamental de la FFT y por cruces por cero (ambas deben coincidir). **Convención: positivo = la señal ATRASA respecto a la referencia**; por ejemplo, en el oscilador diferencial `v(n24)` adelanta 90° a `v(n13)`, así que la fase esperada es −90. Con `--phase-expected` (uno por señal, en el mismo orden) reporta el error. También acepta expresiones como `v(n1)-v(n3)`.

### 5.11 Curva de sintonía (`sweep` / `tuning`)
Para cada punto de control se obtiene frecuencia, amplitud diferencial, modo común, corriente, potencia, energía por ciclo, THD, tiempo al 90 %, fase y número de avisos. **Kvco = df/dctrl** se calcula por gradiente numérico, en Hz por unidad del eje (si usas `--ctrl-scale 1e-6`, es Hz por µA). Con solo 2 puntos válidos es la pendiente entre ellos; con 1 punto no se puede calcular (`nan` en el CSV y una nota en la gráfica en lugar de un panel vacío).

### 5.12 Esquinas PVT
Con `--corner` / `--corners`, todo el barrido se repite en cada esquina y se genera una comparativa: curvas superpuestas, rango de frecuencia por esquina, **rango alcanzable en todas las esquinas a la vez** y (con `--target-f`) el valor de control que se necesita en cada esquina para una frecuencia dada, por interpolación lineal.

## 6. Requisitos del netlist

El script **no necesita un netlist especial**, pero espera lo siguiente (tu netlist de ejemplo ya lo cumple):

- Un bloque `.control` con `tran ... ` y `write archivo.raw`, y `save all` (o al menos las señales que analizas). En `sweep` el script cambia el nombre del `.raw` automáticamente.
- Para esquinas PVT:
  - una línea `.lib <archivo> <sección>` con la sección `typical`, `ff`, `ss`, `fs` o `sf`;
  - `VDD=` y `TEMP=` dentro de una línea `.param` (por ejemplo `.param VDD=3.3 TEMP=60`), y que el resto del netlist use `{VDD}` y `{TEMP}` (por ejemplo `.temp {TEMP}`). Si no hay `TEMP=`, se acepta un `.temp 60` con número literal.
- Para variar un parámetro: un elemento en **una sola línea** (por ejemplo `I0 VBP 0 500u`).

Las rutas del PDK se pueden cambiar sin tocar el netlist con `--path-sub /ruta/vieja=/ruta/nueva` (repetible).

## 7. Barridos

### 7.1 Barrido de un parámetro de control
```bash
python3 osc_characterization.py sweep \
  --netlist CS_Pseudo_diff_N4.spice \
  --line-prefix I0 --template "I0 VBP 0 {v}" \
  --values 300u 400u 500u 600u 700u \
  --ctrl-label "I_bias (uA)" --ctrl-scale 1e-6 \
  --pos "v(n1)" --neg "v(n3)" --vdd 3.3 --isupply "i(v7)" --icore "i(v1)" \
  --outdir osc_sweep
```

- `--line-prefix`: nombre del elemento (o directiva) cuya línea se reemplaza; se sustituye la **primera** línea que empieza con ese nombre.
- `--template`: la línea nueva; `{v}` se sustituye por cada valor.
- `--values`: acepta sufijos de SPICE (`300u`, `1.2`, `2meg`).
- `--ctrl-scale`: divide el valor para mostrarlo (1e-6 → µA); afecta etiquetas, tablas, CSV y Kvco.

### 7.2 Barrido de VDD o TEMP (sin parámetro de control)
Se reescribe la línea `.param`; la plantilla debe repetir los demás parámetros de esa línea:

```bash
python3 osc_characterization.py sweep \
  --netlist Ring_InvN3.spice \
  --line-prefix .param --template ".param VDD={v} TEMP=60" \
  --values 2.4 2.7 3.0 3.3 3.6 --ctrl-label "VDD (V)" \
  --signal "v(n1)" --single-ended --vsupply "v(vdd)" --isupply "i(v7)" \
  --outdir ring_vdd
```
(Como VDD cambia, la potencia usa `--vsupply` en lugar de `--vdd`.)

### 7.3 Barrido de control en esquinas PVT
```bash
python3 osc_characterization.py sweep \
  --netlist CS_Pseudo_diff_N4.spice \
  --line-prefix I0 --template "I0 VBP 0 {v}" \
  --values 300u 400u 500u 600u 700u --ctrl-label "I_bias (uA)" --ctrl-scale 1e-6 \
  --corners worst3 --target-f 600meg \
  --pos "v(n1)" --neg "v(n3)" --isupply "i(v7)" --icore "i(v1)" \
  --outdir sweep_pvt
```

- **Presets** (`--corners`, repetible; se pueden combinar entre sí y con `--corner`):

| Preset | Esquinas |
|---|---|
| `worst3` | `ss:125:3.0`, `typical:60:3.3`, `ff:-40:3.6` |
| `process5` | las 5 esquinas de proceso (typical, ff, ss, fs, sf) a 60 °C y 3.3 V |
| `pvt45` | malla completa: 5 procesos × {-40, 27, 125 °C} × {3.0, 3.3, 3.6 V} (las mismas de `pvt_runner.py`) |
| `pvt27` | lo mismo con 3 procesos (typical, ff, ss) |
| `temp3` | solo temperatura: typical, 3.3 V, -40/27/125 °C |
| `vdd3` | solo alimentación: typical, 27 °C, 3.0/3.3/3.6 V |

  Se agregan más presets editando el diccionario `PRESETS` del script (una lista de textos `"proceso:temp:vdd"`). Ojo con el costo: el número de simulaciones es esquinas × valores de control (`pvt45` con 5 valores = 225 corridas), así que conviene usar `--jobs`. Con más de 6 esquinas, la figura comparativa usa color = proceso, estilo de línea = VDD y opacidad = temperatura (más claro = más frío), igual que `pvt_runner.py compare-all`.
- **Esquinas sueltas** (`--corner NOMBRE:TEMP:VDD`, repetible): `--corner ss:125:3.0 --corner typical:27:3.3`. `NOMBRE` puede ser `typical` (o `tt`), `ff`, `ss`, `fs`, `sf`.
- Los valores de control son los mismos en todas las esquinas.
- En pantalla se muestra **una línea por esquina** (rango de frecuencia, número de avisos y puntos fallidos) y al final la comparación; el detalle de cada esquina queda en `<esquina>/analysis.log`. Con `--verbose` (`"verbose": true` en el JSON) se imprime todo en pantalla como antes.
- No uses `--vdd` en este modo: la potencia se calcula con el VDD de cada esquina.

### 7.4 Curva de sintonía desde `.raw` ya simulados
```bash
python3 osc_characterization.py tuning \
  --run 300u:a.raw --run 400u:b.raw --run 500u:c.raw \
  --ctrl-label "I_bias (uA)" --ctrl-scale 1e-6 \
  --pos "v(n1)" --neg "v(n3)" --vdd 3.3 --isupply "i(v7)"
```

## 7b. Monte Carlo (`mc`)

Un solo subcomando; el número de valores de control define el caso:

- **Un valor** (o ninguno, el netlist tal cual): MC en un punto de operación (histograma, σ, rendimiento).
- **Varios valores**: cada pieza (semilla) se simula en todos los valores; se obtiene la curva de sintonía por pieza, Kvco por pieza y el rango cubierto por ~90 % de las piezas ([p95 de fmin, p5 de fmax]).

Modos (`--mc-mode`):

| Modo | Qué varía | Esquinas permitidas |
|---|---|---|
| `mismatch` | solo desapareo entre transistores (`sw_stat_mismatch=1`) | **cualquiera** (`--corner`/`--corners`: ss, ff, fs, sf, typical, presets) |
| `global` | solo variación de proceso global (`sw_stat_global=1`) | solo typical |
| `both` | global + mismatch | solo typical |
| `split` | corre los tres y reporta el reparto de varianza (σ²_both vs σ²_g+σ²_m) | mismatch en todas; global/both solo en typical (con aviso) |

Motivo: la sección `statistical` del PDK está centrada en typical y reemplaza a la sección de esquina, así que global/both no tienen sentido en ss/ff. El mismatch (`fets_mm`) sí funciona sobre cualquier esquina determinista.

```bash
python3 osc_characterization.py mc --netlist CS_Pseudo_diff_N4.spice \
  --line-prefix I0 --template "I0 VBP 0 {v}" --values 500u \
  --ctrl-scale 1e-6 --pos "v(n1)" --neg "v(n3)" --isupply "i(v7)" --vdd 3.3 \
  --corners worst3 --mc-mode split --mc-n 100 --spec f:560meg:640meg \
  --jobs 4 --threads 1 --outdir results/mc
# o con JSON: python3 osc_characterization.py --config configs/cs_diff_mc.json
```

Opciones: `--mc-n` (muestras, default 100), `--mc-seed` (semilla maestra; la misma lista de semillas se usa en todos los casos, modos y valores de control), `--mc-skew` (3 = 1σ del PDK), `--spec METRICA:MIN:MAX` (repetible, para el rendimiento), `--min-amp` (fracción de VDD bajo la cual la muestra se considera "no oscila" y cuenta como fallo, default 0.05), `--keep-raw`, `--no-mc-plots`.

Salidas: `mc_samples.csv` (una fila por simulación), `mc_summary.csv`, `mc_report.txt`, `mc_split.csv`, `mc_hist*.png`, `mc_tuning.png`, `mc_split.png`, `mc_corners.png`; carpetas `<esquina>/<modo>/runs/`.

Costo = casos × valores × (1 nominal + modos × N). Error estándar de σ ≈ σ/√(2(N−1)): N=100 → ~7 %, N=200 → ~5 %. Las muestras que no oscilan (o sin frecuencia medible) se marcan como fallo y bajan el rendimiento, no entran en media/σ.

## 8. Archivos de salida

**`analyze`** (carpeta `--outdir`, por defecto `osc_analysis/`)

| Archivo | Contenido |
|---|---|
| `osc_summary.txt` | informe completo (el mismo que se imprime) |
| `osc_metrics.json` | todas las métricas, avisos y `.tran` sugerido, para procesarlas con otros scripts |
| `osc_overview.png`, `osc_eye.png`, `osc_jitter.png`, `osc_spectrum.png` | formas de onda y arranque, ojo, jitter, espectro |
| `config_used.json` | opciones efectivas con las que se hizo el análisis |

**`sweep` / `tuning`** (carpeta `--outdir`, por defecto `osc_sweep/` y `osc_tuning/`)

| Archivo | Contenido |
|---|---|
| `tuning.csv` | `ctrl, f, amp, vcm, idd, power, energy, t90, thd, kvco, phase, phase_err, nwarn, ok` (`ctrl` en unidades escaladas; `f` en Hz; `power` en W; `energy` en J; `kvco` en Hz por unidad de `ctrl`; `ok=0` si ese punto falló) |
| `osc_tuning.png` | f, Kvco, amplitud y modo común, potencia y energía por ciclo (y fase y THD si hay `--phase-*`) |
| `runs/` | por cada punto: el netlist modificado (`.spice`), el `.log` de ngspice y el `.raw` |
| `run_<valor>/` | informe y métricas de ese punto |
| `analysis.log` | solo con esquinas: el detalle del análisis de esa esquina (el que antes se imprimía en pantalla) |
| `config_used.json` | opciones efectivas |

**Con esquinas**, además: una subcarpeta por esquina (`ss_125C_3V/`, `typical_60C_3.3V/`, `ff_-40C_3.6V/`, cada una con lo anterior) y, en la carpeta principal:

| Archivo | Contenido |
|---|---|
| `corners_tuning.png` | las curvas de todas las esquinas superpuestas (f, Kvco, amplitud, potencia, energía, THD o fase), con el rango total sombreado y el rango común a todas |
| `corners_summary.csv` | por esquina: fmin, fmax, rango de sintonía (%), Kvco medio, potencias mínima y máxima |
| `corners_tuning.csv` | frecuencia de cada esquina para cada valor de control |

## 9. Archivos de configuración JSON

Todo lo que se pasa por la línea de comandos puede vivir en un JSON, con el mismo nombre de la opción (con guion o guion bajo). Ejemplo (`configs/cs_diff_worst3.json` hereda de `cs_diff_base.json`):

```json
{
  "_nota": "Barrido de ibias en ss/125C/3.0V, typical/60C/3.3V y ff/-40C/3.6V",
  "extends": "cs_diff_base.json",
  "command": "sweep",
  "corners": ["worst3"],
  "target_f": "600meg",
  "jobs": 5,
  "outdir": "results/cs_diff_worst3"
}
```

- `command`: `analyze`, `tuning` o `sweep`. Con eso basta `python3 osc_characterization.py --config archivo.json`.
- `extends`: hereda otro JSON (uno o varios); lo del archivo hijo tiene prioridad.
- Las **opciones de la línea de comandos tienen prioridad** sobre el JSON: `--config cs_diff_worst3.json --jobs 1 --outdir prueba`.
- Las rutas de archivos de entrada (`netlist`, `raw_path`, archivos de `run`) son **relativas al JSON**; `outdir` es relativo a donde ejecutas.
- Las listas se escriben como listas (`"values": ["300u", "400u"]`); las opciones activables (`single_ended`, `noisy`) son `true`/`false`; `path_sub` acepta una lista de `"VIEJO=NUEVO"` o un objeto `{"viejo": "nuevo"}`.
- Se permiten líneas completas de comentario que empiecen con `//` y claves que empiecen con `_`.
- Una clave desconocida da un error con sugerencia (`did you mean ['netlist']?`).
- **`--save-config archivo.json`** convierte un comando que ya te funcionó en un JSON (escribe el archivo y termina, no simula).
- Cada ejecución deja un `config_used.json` en su carpeta de salida, reutilizable con `--config` para repetirla.

## 10. Rendimiento y paralelismo

| Opción | Valor por defecto | Para qué |
|---|---|---|
| `--jobs N` | 1 | simulaciones ngspice en paralelo |
| `--threads N` | 1 | hilos por proceso de ngspice (se fuerza `set num_threads=N` en el `.control` de cada corrida; `0` = no tocar) |
| `--omp-wait` | `auto` | política `OMP_WAIT_POLICY`: sin tocar en serie; con `jobs>1` solo `passive` si `--threads 0` o `jobs × threads` excede las CPUs |
| `--timeout S` | 300 | tiempo máximo por corrida; una corrida atorada se marca `FAILED` y el barrido continúa (0 = sin límite) |

Recomendaciones (medidas con otra herramienta del repo, `isfpn.py`, en una máquina de 16 núcleos físicos):

- **Varios procesos de un hilo ganan a pocos procesos con varios hilos**; por eso `--threads 1` es el valor por defecto.
- Sube `--jobs` hasta el número de núcleos **físicos** como máximo.
- El tiempo total es "rondas × tiempo por corrida": con 15 corridas, `--jobs 5` da 3 rondas exactas; `--jobs 4` da 4. El script avisa al inicio si con menos jobs obtendrías las mismas rondas.
- Si ngspice en tu entorno usa muchos hilos por proceso (un `set num_threads=8` en `.spiceinit`, por ejemplo), `--threads 1` lo anula.
- Los resultados son idénticos para cualquier `--jobs`.
- Si una corrida falla (no converge, timeout), el barrido continúa; el script solo termina con error si fallan **todas**.

## 11. Uso como librería

```python
from osc_characterization import characterize, default_config

cfg = default_config(pos="v(n1)", neg="v(n3)", vdd=3.3, isupply="i(v7)")
res, informe = characterize("run.raw", cfg, outdir="salida", plots=False)
res["freq"]["f"], res["amplitude"]["diff"]["amp"], res["warnings"], res.get("suggested_tran")  # solo existe si hay algo que corregir
```

Pensado para reutilizarlo desde futuros scripts de PVT y Monte Carlo.

## 12. Limitaciones y notas

- **Monte Carlo** y **ruido de fase** (ISF de Hajimiri) todavía no están integrados; el ruido de fase se estima con `Python_tools/isfpn/isfpn.py`.
- `sweep` varía **un** parámetro de control a la vez, y los mismos valores se usan en todas las esquinas.
- La línea que se reemplaza debe estar en **una sola línea** (no se manejan continuaciones con `+`). Con `--line-prefix .param` solo se reescribe la **primera** línea `.param`, por eso la plantilla debe repetir los demás parámetros.
- En esquinas PVT, `VDD` y `TEMP` deben ser parámetros (`.param`); si el VDD aparece como número fijo en una fuente, el script no puede cambiarlo.
- Con `.ic` y `uic` el arranque es por desbalance impuesto, no por ruido: los tiempos de arranque sirven para comparar, no como valor absoluto.
- Las simulaciones sin ruido dan solo jitter numérico (piso del simulador).
- Para simulaciones en las que el oscilador no arranca (por ejemplo, en una esquina lenta), el punto se reporta con avisos o como `ok=0`, y el barrido continúa.

## 13. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `The line to replace was not found` | `--line-prefix` no coincide con el inicio de ninguna línea del netlist |
| `The netlist has no 'write file.raw' line` | falta `write archivo.raw` dentro de `.control` |
| `No '.lib <file> <section>' line ...` | con esquinas, el netlist necesita un `.lib` con la sección `typical`, `ff`, `ss`, `fs` o `sf` |
| `No 'VDD=' found in a .param line` | con esquinas, `VDD=` y `TEMP=` deben estar en un `.param` |
| `file dialect is not specified` / error leyendo el `.raw` | `.raw` que no es de ngspice o `spicelib` desactualizado |
| `ngspice did not produce ...raw` | revisa el `.log` de esa corrida en `runs/` (ruta del PDK, convergencia) |
| `ngspice timed out` | corrida atorada; sube `--timeout` o revisa el `.log` |
| Avisos de pocos puntos por periodo o de pocos ciclos | usa el `.tran` sugerido en el informe |
| El sistema se vuelve lento con `--jobs` alto | baja `--jobs`; mantén `--threads 1` |
| `Error: unknown key ... in config.json` | clave mal escrita en el JSON |
