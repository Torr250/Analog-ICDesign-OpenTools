* validacion interna (fuente ideal directa al filtro)
* ============================================================
* Modelo de canal: SOLO pérdida (filtro shelving, 1 etapa(s) en
* cascada), sin líneas de transmisión ni reflexión
* generado por channel_model_generator.py
*
* Pérdida ajustada: 0.000 dB en DC, 6.000 dB @ 1.0000 GHz, 10.000 dB @ 8.0000 GHz
* fp1=0.453618 GHz   fp2=1.455681 GHz   (por etapa, x1 etapas)
*
* Uso: X1 nodo_entrada nodo_salida CHANNEL_MODEL
* La entrada tiene impedancia infinita (sensa, no carga) y la
* salida es una fuente ideal (impedancia de salida cero) -- no
* representa Z0 ni reflexiones, solo la forma de pérdida en magnitud.
* ============================================================
.subckt CHANNEL_MODEL in out
Ebuf_in1 mid_in1 0 in 0 1
R1 mid_in1 mid_r1 3.508569e+02
C1 mid_r1 0 1.000000e-12
Bshelf1 shelf_out1 0 V = V(mid_r1) + (V(mid_in1)-V(mid_r1))*0.311618952
Epad out 0 shelf_out1 0 1.000000000
.ends
Vin in_src 0 AC 1
X1 in_src out CHANNEL_MODEL
.control
  ac dec 50 1e6 16000000000.0
  let loss_db = 20*log10(abs(v(out)))
  meas ac loss_dc FIND loss_db AT=1e6
  meas ac loss1 FIND loss_db AT=1000000000.0
  meas ac loss2 FIND loss_db AT=8000000000.0
  print loss_dc
  print loss1
  print loss2
.endc
.end
