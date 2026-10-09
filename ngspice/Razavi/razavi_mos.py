"""razavi_mos.py -- calculo a mano de un transistor MOS con el modelo Level 1 de Razavi.

Este modulo es el mismo en ngspice/Razavi y en LTspice/Razavi. Contiene cuatro funciones:

1. leer_parametros_modelo(simulador, modelo)   lee un .MODEL de razavi_cmos.lib
2. calcular_transistor(params, tipo, VGS, VDS, VSB, W, L)   punto de operacion, pequena senal,
   capacitancias y ruido
3. tabla_transistores(...)                      imprime uno o varios transistores en una tabla
4. ruido_vs_frecuencia(transistor, f)           densidad espectral de ruido en funcion de f

Convenciones
------------
* Unidades SI: metros, volts, amperes, siemens, farads, hertz. Densidades en V^2/Hz o A^2/Hz.
* Todos los voltajes y corrientes de entrada y salida son MAGNITUDES POSITIVAS, tambien en el PMOS
  (VGS = 0.9 V significa |VGS| = 0.9 V). LTspice reporta el PMOS con signo negativo en Id, Vgs,
  Vds, Vth y Vdsat; ngspice tambien (id, vgs, vds). Aqui no.
* El subcircuito (.subckt) de la libreria NO se lee: el area y el perimetro de las difusiones se
  calculan con la misma regla que usa el subcircuito (AD = AS = W*wd, PD = PS = 2*W + 2*wd), con
  wd = 0.48 um por omision. Si se cambia wd en la libreria, hay que cambiarlo tambien aqui.
* "simulador" solo cambia de que carpeta se lee razavi_cmos.lib (el kf de cada libreria es distinto)
  y la formula del ruido flicker que se usa:
      ngspice : S_id,fl = kf * Id^af / (f * W * L * Cox^2)
      ltspice : S_id,fl = kf * gm^2 / (f * W * L * Cox)      (verificada solo con af = 1)
"""
import re
from pathlib import Path

import numpy as np
from prettytable import PrettyTable
from si_prefix import si_format

K_BOLTZMANN = 1.380649e-23     # J/K
EPS0 = 8.854214871e-12         # F/m, valor que usa ngspice
EPS_OX_REL = 3.9               # permitividad relativa del SiO2
T_SIM = 300.15                 # K (temp = 27 C, la de las simulaciones)
WD_POR_OMISION = 0.48e-6       # m, el de los subcircuitos de razavi_cmos.lib

_SUFIJOS = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
_CARPETA = {"ngspice": "ngspice", "ltspice": "LTspice"}

# Valores por omision de SPICE para los parametros que la libreria no declare
_POR_OMISION = dict(kp=2e-5, vto=0.0, gamma=0.0, phi=0.6, lambda_=0.0, tox=1e-7, cgso=0.0, cgdo=0.0,
                    cgbo=0.0, cj=0.0, cjsw=0.0, mj=0.5, mjsw=0.5, kf=0.0, af=1.0, rd=0.0, rs=0.0)


# ----------------------------------------------------------------------------------------------
# 1. Parametros del modelo
# ----------------------------------------------------------------------------------------------
def _valor_spice(texto):
    """Convierte '100u', '40e-10' o '9.81e-4' a float (sufijos SPICE: f p n u m k meg g t)."""
    m = re.fullmatch(r"([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)(meg|[tgkmunpf])?[a-z]*", texto.strip().lower())
    if not m:
        raise ValueError(f"No se puede interpretar el valor SPICE '{texto}'")
    return float(m.group(1)) * _SUFIJOS.get(m.group(2), 1.0)


def _ruta_libreria(simulador):
    """Ruta de razavi_cmos.lib del simulador pedido: la de esta carpeta o la de la carpeta hermana."""
    aqui = Path(__file__).resolve().parent
    carpeta = _CARPETA[simulador]
    candidatas = [aqui / "razavi_cmos.lib"] if aqui.parent.name.lower() == carpeta.lower() else []
    candidatas.append(aqui.parents[1] / carpeta / "Razavi" / "razavi_cmos.lib")
    for ruta in candidatas:
        if ruta.exists():
            return ruta
    raise FileNotFoundError(f"No se encuentra razavi_cmos.lib de {simulador}; indica la ruta con lib=...")


def leer_parametros_modelo(simulador, modelo="nch", lib=None):
    """Lee los parametros de un .MODEL Level 1 de razavi_cmos.lib.

    simulador : "ngspice" o "ltspice". Elige la libreria (cada una tiene su propio kf) y la
                formula del ruido flicker.
    modelo    : nombre del .MODEL: "nch", "pch", "nch_rs" o "pch_rs" (los _rs tienen rd = rs = 200 ohm).
    lib       : ruta opcional a otra libreria.
    Regresa un diccionario con los parametros en unidades SI (los que no estan en la libreria
    toman el valor por omision de SPICE).
    """
    simulador = simulador.lower()
    if simulador not in _CARPETA:
        raise ValueError("simulador debe ser 'ngspice' o 'ltspice'")
    ruta = Path(lib) if lib else _ruta_libreria(simulador)

    # Paso 1: quitar comentarios (* al inicio de linea, ; al final) y lineas vacias
    lineas = []
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.split(";")[0].strip()
        if linea and not linea.startswith("*"):
            lineas.append(linea)

    # Paso 2: unir las lineas de continuacion (empiezan con +)
    bloques = []
    for linea in lineas:
        if linea.startswith("+") and bloques:
            bloques[-1] += " " + linea[1:].strip()
        else:
            bloques.append(linea)

    # Paso 3: buscar el .MODEL pedido y separar sus pares nombre=valor
    for bloque in bloques:
        m = re.match(r"\.model\s+(\w+)\s+(nmos|pmos)\s*(.*)", bloque, flags=re.I)
        if m and m.group(1).lower() == modelo.lower():
            resto = re.sub(r"\s*=\s*", "=", m.group(3))
            pares = {k.lower(): _valor_spice(v) for k, v in re.findall(r"(\w+)=(\S+)", resto)}
            if pares.get("level", 1) != 1:
                raise ValueError(f"El modelo {modelo} no es Level 1")
            params = dict(_POR_OMISION)
            for k, v in pares.items():
                params["lambda_" if k == "lambda" else k] = v
            params.update(nombre=m.group(1), tipo="n" if m.group(2).lower() == "nmos" else "p",
                          simulador=simulador, lib=str(ruta))
            return params
    raise KeyError(f"No hay un .MODEL llamado '{modelo}' en {ruta}")


# ----------------------------------------------------------------------------------------------
# 2. Punto de operacion, pequena senal, capacitancias y ruido
# ----------------------------------------------------------------------------------------------
class Transistor:
    """Contenedor de resultados: los atributos son los nombres de las cantidades (nch.gm, nch.cgg...)."""

    def __init__(self, **datos):
        self.__dict__.update(datos)

    def como_dict(self):
        return dict(self.__dict__)

    def __repr__(self):
        return (f"Transistor({self.nombre}, {self.tipo.upper()}MOS, {self.region}, "
                f"Id={self.id:.4g} A, gm={self.gm:.4g} S, gds={self.gds:.4g} S)")


def _nivel1(p, vgs, vds, vsb, W, L):
    """Ecuaciones DC de Level 1 (como ngspice, magnitudes positivas). Regresa un diccionario."""
    beta = p["kp"] * W / L
    # Umbral con efecto de cuerpo. Con VSB < 0 ngspice linealiza la raiz (igual aqui).
    if vsb >= 0:
        sarg = np.sqrt(p["phi"] + vsb)
    else:
        sarg = max(0.0, np.sqrt(p["phi"]) + vsb / (2 * np.sqrt(p["phi"])))
    vth = abs(p["vto"]) + p["gamma"] * (sarg - np.sqrt(p["phi"]))
    vov = vgs - vth
    arg = p["gamma"] / (2 * sarg) if sarg > 0 else 0.0           # gmb = gm * arg
    lam = p["lambda_"]
    if vov <= 0:
        region, i_d, gm, gds = "corte", 0.0, 0.0, 0.0
    elif vds >= vov:
        betap = beta * (1 + lam * vds)
        region, i_d, gm, gds = "saturacion", 0.5 * betap * vov**2, betap * vov, 0.5 * beta * lam * vov**2
    else:
        betap = beta * (1 + lam * vds)
        region = "triodo"
        i_d = betap * vds * (vov - vds / 2)
        gm = betap * vds
        gds = betap * (vov - vds) + beta * lam * vds * (vov - vds / 2)
    return dict(region=region, vth=vth, vov=vov, vdsat=max(vov, 0.0), id=i_d, gm=gm, gds=gds,
                gmb=gm * arg, sarg=sarg)


def _meyer(p, vgs, vds, vth, vdsat, C):
    """Capacitancias intrinsecas de compuerta (modelo de Meyer, igual que ngspice). C = Cox*W*L."""
    vgst = vgs - vth
    phi = p["phi"]
    if vgst <= -phi:
        return 0.0, 0.0, C
    if vgst <= -phi / 2:
        return 0.0, 0.0, -vgst * C / phi
    if vgst <= 0:
        return 2 * (vgst * C / (1.5 * phi) + C / 3), 0.0, -vgst * C / phi
    if vdsat <= vds:
        return 2 * C / 3, 0.0, 0.0
    vddif = 2 * vdsat - vds
    vddif1 = vdsat - vds
    cgd = (2 * C / 3) * (1 - vdsat**2 / vddif**2)
    cgs = (2 * C / 3) * (1 - vddif1**2 / vddif**2)
    return cgs, cgd, 0.0


def calcular_transistor(params, tipo, VGS, VDS, VSB, W, L, wd=WD_POR_OMISION, T=T_SIM):
    """Calcula el punto de operacion y los parametros de pequena senal de un transistor.

    params : diccionario de leer_parametros_modelo()
    tipo   : "n" o "p" (debe coincidir con el .MODEL)
    VGS, VDS, VSB : magnitudes positivas, voltajes EXTERNOS del transistor (si el modelo tiene
             rd o rs, el punto de operacion intrinseco se obtiene resolviendo la caida en ellas)
    W, L   : ancho y largo del canal (m)
    wd     : longitud de difusion (m) que usa el subcircuito para calcular AD, AS, PD y PS
    T      : temperatura (K)
    Regresa un objeto Transistor con atributos: region, vth, vov, vdsat, id, gm, gds, gmb,
    cgs, cgd, cgb (totales, incluyen traslape), cgs_int, cgd_int, cgb_int, cbd, cbs,
    cgg, cdd, css, s_id_th, s_vin_th, s_id_fl_1Hz, s_vin_fl_1Hz, f_corner y avisos.
    """
    if tipo.lower() != params["tipo"]:
        raise ValueError(f"El modelo {params['nombre']} es {params['tipo'].upper()}MOS y se pidio tipo '{tipo}'")
    if VDS < 0 or VSB < 0:
        raise ValueError("VDS y VSB se ingresan como magnitudes positivas (VSB < 0 no esta soportado)")
    p = params
    avisos = []
    rd, rs = p["rd"], p["rs"]

    # Paso 1: punto de operacion. Sin rd ni rs, los voltajes externos son los intrinsecos.
    if rd == 0 and rs == 0:
        vgs_i, vds_i, vsb_i = VGS, VDS, VSB
        op = _nivel1(p, vgs_i, vds_i, vsb_i, W, L)
    else:
        # Con rd y rs: se busca por biseccion la corriente que cumple Id = Id_modelo(voltajes intrinsecos)
        # VGS_i = VGS - Id*rs,  VDS_i = VDS - Id*(rd+rs),  VSB_i = VSB + Id*rs
        bajo, alto = 0.0, VDS / (rd + rs)
        for _ in range(200):
            i_med = 0.5 * (bajo + alto)
            op = _nivel1(p, VGS - i_med * rs, VDS - i_med * (rd + rs), VSB + i_med * rs, W, L)
            if op["id"] - i_med > 0:
                bajo = i_med
            else:
                alto = i_med
        i_med = 0.5 * (bajo + alto)
        vgs_i, vds_i, vsb_i = VGS - i_med * rs, VDS - i_med * (rd + rs), VSB + i_med * rs
        op = _nivel1(p, vgs_i, vds_i, vsb_i, W, L)

    # Paso 2: capacitancias. Cox desde tox; las de difusion con AD = AS = W*wd, PD = PS = 2W + 2wd
    Cox = EPS_OX_REL * EPS0 / p["tox"]
    cgs_int, cgd_int, cgb_int = _meyer(p, vgs_i, vds_i, op["vth"], op["vdsat"], Cox * W * L)
    cgs_ov, cgd_ov, cgb_ov = p["cgso"] * W, p["cgdo"] * W, p["cgbo"] * L
    area, perim = W * wd, 2 * W + 2 * wd
    if p["mj"] != 0 or p["mjsw"] != 0:
        avisos.append("mj o mjsw distintos de cero: las capacitancias de union dependen del voltaje y aqui "
                      "se calculan con polarizacion cero")
    cbd = cbs = p["cj"] * area + p["cjsw"] * perim
    cgs, cgd, cgb = cgs_int + cgs_ov, cgd_int + cgd_ov, cgb_int + cgb_ov
    cgg, cdd, css = cgs + cgd + cgb, cgd + cbd, cgs + cbs

    # Paso 3: ruido. Termico del canal 4kT(2/3)gm; flicker segun el simulador
    s_id_th = 4 * K_BOLTZMANN * T * (2 / 3) * op["gm"]
    if p["simulador"] == "ngspice":
        s_id_fl_1Hz = p["kf"] * op["id"] ** p["af"] / (W * L * Cox**2)
    else:
        s_id_fl_1Hz = p["kf"] * op["gm"] ** 2 / (W * L * Cox)
        if p["af"] != 1.0:
            avisos.append("af distinto de 1: la formula de ruido flicker de LTspice solo se verifico con af = 1")
    s_vin_th = s_id_th / op["gm"] ** 2 if op["gm"] > 0 else np.inf
    s_vin_fl_1Hz = s_id_fl_1Hz / op["gm"] ** 2 if op["gm"] > 0 else np.inf
    f_corner = s_id_fl_1Hz / s_id_th if s_id_th > 0 else np.inf       # S_fl(fc) = S_th con S_fl ~ 1/f

    if op["region"] != "saturacion":
        avisos.append(f"El transistor esta en {op['region']}: el ruido termico usa (2/3)*gm como en los simuladores; "
                      "fuera de saturacion ese modelo no es fisico (en triodo gm es pequeno aunque el canal sea resistivo)")
    if rd or rs:
        avisos.append(f"rd = {rd:g} ohm y rs = {rs:g} ohm: los valores intrinsecos son los del transistor interno "
                      f"(VGS_i = {vgs_i:.4f} V, VDS_i = {vds_i:.4f} V, VSB_i = {vsb_i:.4f} V)")

    return Transistor(nombre=p["nombre"], tipo=p["tipo"], simulador=p["simulador"], params=p, W=W, L=L, wd=wd, T=T,
                      VGS=VGS, VDS=VDS, VSB=VSB, vgs_i=vgs_i, vds_i=vds_i, vsb_i=vsb_i, Cox=Cox,
                      region=op["region"], vth=op["vth"], vov=op["vov"], vdsat=op["vdsat"], id=op["id"],
                      gm=op["gm"], gds=op["gds"], gmb=op["gmb"], rd=rd, rs=rs,
                      cgs_int=cgs_int, cgd_int=cgd_int, cgb_int=cgb_int, cgs_ov=cgs_ov, cgd_ov=cgd_ov, cgb_ov=cgb_ov,
                      cgs=cgs, cgd=cgd, cgb=cgb, cbd=cbd, cbs=cbs, cgg=cgg, cdd=cdd, css=css,
                      s_id_th=s_id_th, s_vin_th=s_vin_th, s_id_fl_1Hz=s_id_fl_1Hz, s_vin_fl_1Hz=s_vin_fl_1Hz,
                      f_corner=f_corner, avisos=avisos)


# ----------------------------------------------------------------------------------------------
# 3. Tabla de parametros
# ----------------------------------------------------------------------------------------------
_FILAS = [("Region", "region", ""), ("VGS", "VGS", "V"), ("VDS", "VDS", "V"), ("VSB", "VSB", "V"),
          ("VTH", "vth", "V"), ("Vov = VGS - VTH", "vov", "V"), ("VDSat", "vdsat", "V"),
          ("ID", "id", "A"), ("gm", "gm", "S"), ("gds", "gds", "S"), ("gmb", "gmb", "S"),
          ("Cgs (total)", "cgs", "F"), ("Cgd (total)", "cgd", "F"), ("Cgb (total)", "cgb", "F"),
          ("Cbd", "cbd", "F"), ("Cbs", "cbs", "F"),
          ("Cgg = Cgs + Cgd + Cgb", "cgg", "F"), ("Cdd = Cgd + Cbd", "cdd", "F"), ("Css = Cgs + Cbs", "css", "F"),
          ("S_Id termico", "s_id_th", "A^2/Hz"), ("S_Vin termico", "s_vin_th", "V^2/Hz"),
          ("S_Vin flicker a 1 Hz", "s_vin_fl_1Hz", "V^2/Hz"), ("Esquina flicker fc", "f_corner", "Hz")]


def tabla_transistores(*transistores, nombres=None, leyenda=True):
    """Imprime los parametros de uno o varios transistores en columnas (PrettyTable).

    nombres : lista opcional con el nombre de cada columna (por omision, modelo y tipo).
    leyenda : si es True, agrega las notas sobre signos y avisos.
    Regresa la tabla.
    """
    if nombres is None:
        nombres = [f"{t.nombre} (W={si_format(t.W, 2)}m, L={si_format(t.L, 2)}m)" for t in transistores]
    tabla = PrettyTable(["Parametro"] + list(nombres))
    for etiqueta, atributo, unidad in _FILAS:
        fila = [etiqueta + (f" [{unidad}]" if unidad else "")]
        for t in transistores:
            v = getattr(t, atributo)
            fila.append(v if isinstance(v, str) else si_format(v, 3))
        tabla.add_row(fila)
    tabla.align["Parametro"] = "l"
    print(tabla)
    if leyenda:
        print("Nota: todos los valores son magnitudes positivas, tambien en el PMOS. LTspice (y ngspice) reportan "
              "el PMOS con signo negativo en Id, Vgs, Vds, Vth y Vdsat.")
        print("Las capacitancias Cgs, Cgd y Cgb incluyen el traslape (ngspice las reporta asi; LTspice reporta "
              "por separado Cgs, Cgd, Cgb intrinsecas y los traslapes Cgsov, Cgdov, Cgbov).")
        for nombre, t in zip(nombres, transistores):
            for aviso in t.avisos:
                print(f"Aviso ({nombre}): {aviso}")
    return tabla


# ----------------------------------------------------------------------------------------------
# 4. Ruido en funcion de la frecuencia
# ----------------------------------------------------------------------------------------------
def ruido_vs_frecuencia(t, f, RD=None):
    """Densidad espectral de ruido de un transistor en un vector de frecuencias.

    t  : objeto Transistor de calcular_transistor()
    f  : vector de frecuencias (Hz)
    RD : opcional, resistencia de carga a la fuente de alimentacion (ohm). Sin RD la carga es una
         fuente de corriente ideal (circuito A de los notebooks de ruido). No se combina con rd/rs.
    Regresa un diccionario (arreglos del tamano de f):
      s_id_th, s_id_fl, s_id : densidad de corriente del canal (A^2/Hz)
      s_vin, s_vin_th, s_vin_fl : referido a la entrada (V^2/Hz); s_vin_th incluye todo lo que no es
                              flicker (RD, rd, rs)
      s_vout : ruido de salida (V^2/Hz); si no hay rd/rs incluye Cdd = Cgd + Cbd en el nodo de salida
    """
    f = np.asarray(f, dtype=float)
    cuatro_kT = 4 * K_BOLTZMANN * t.T
    s_id_th = np.full_like(f, t.s_id_th)
    s_id_fl = t.s_id_fl_1Hz / f                       # el Level 1 solo tiene flicker 1/f
    s_id = s_id_th + s_id_fl

    if t.rd == 0 and t.rs == 0:
        s_extra = cuatro_kT / RD if RD else 0.0       # ruido termico de la resistencia de carga
        G = t.gds + (1 / RD if RD else 0.0)           # conductancia del nodo de salida
        s_i_total = s_id + s_extra
        s_vin = s_i_total / t.gm**2
        s_vin_fl = s_id_fl / t.gm**2
        s_vout = s_i_total / (G**2 + (2 * np.pi * f * t.cdd) ** 2)
    else:
        if RD:
            raise ValueError("RD no se puede combinar con rd/rs en esta funcion")
        # Ecuaciones de nodos con incognitas [vd, vd', vs'] (drenador externo, drenador interno, fuente interna)
        g_rd = 1 / t.rd if t.rd else 1e12
        g_rs = 1 / t.rs if t.rs else 1e12
        Y = np.array([[g_rd, -g_rd, 0.0],
                      [-g_rd, g_rd + t.gds, -(t.gm + t.gds + t.gmb)],
                      [0.0, -t.gds, g_rs + t.gm + t.gds + t.gmb]])
        Av = np.linalg.solve(Y, np.array([0.0, -t.gm, t.gm]))[0]
        H_ch = np.linalg.solve(Y, np.array([0.0, -1.0, 1.0]))[0]
        H_rd = np.linalg.solve(Y, np.array([1.0, -1.0, 0.0]))[0]
        H_rs = np.linalg.solve(Y, np.array([0.0, 0.0, 1.0]))[0]
        s_rd = cuatro_kT / t.rd if t.rd else 0.0
        s_rs = cuatro_kT / t.rs if t.rs else 0.0
        num = s_id * H_ch**2 + (s_rd * H_rd**2 + s_rs * H_rs**2) * np.ones_like(f)
        s_vin = num / Av**2
        s_vin_fl = s_id_fl * H_ch**2 / Av**2
        s_vout = num                                   # sin capacitancias en el nodo de salida

    return dict(f=f, s_id_th=s_id_th, s_id_fl=s_id_fl, s_id=s_id, s_vin=s_vin, s_vin_th=s_vin - s_vin_fl,
                s_vin_fl=s_vin_fl, s_vout=s_vout)
