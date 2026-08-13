* validacion interna (fuente ideal directa al filtro)
* ============================================================
* Modelo de canal: SOLO pérdida (filtro shelving, 3 etapa(s) en
* cascada), sin líneas de transmisión ni reflexión
* generado por channel_model_generator.py
*
* Pérdida ajustada: 0.000 dB en DC, 12.000 dB @ 0.5000 GHz, 20.000 dB @ 2.0000 GHz
* fp1=0.287402 GHz   fp2=0.643870 GHz   (por etapa, x3 etapas)
*
* Uso: X1 nodo_entrada nodo_salida CHANNEL_MODEL
* La entrada tiene impedancia infinita (sensa, no carga) y la
* salida es una fuente ideal (impedancia de salida cero) -- no
* representa Z0 ni reflexiones, solo la forma de pérdida en magnitud.
* ============================================================
.subckt CHANNEL_MODEL in out
Ebuf_in1 mid_in1 0 in 0 1
R1 mid_in1 mid_r1 5.537718e+02
C1 mid_r1 0 1.000000e-12
Bshelf1 shelf_out1 0 V = V(mid_r1) + (V(mid_in1)-V(mid_r1))*0.446365802
Ebuf_in2 mid_in2 0 shelf_out1 0 1
R2 mid_in2 mid_r2 5.537718e+02
C2 mid_r2 0 1.000000e-12
Bshelf2 shelf_out2 0 V = V(mid_r2) + (V(mid_in2)-V(mid_r2))*0.446365802
Ebuf_in3 mid_in3 0 shelf_out2 0 1
R3 mid_in3 mid_r3 5.537718e+02
C3 mid_r3 0 1.000000e-12
Bshelf3 shelf_out3 0 V = V(mid_r3) + (V(mid_in3)-V(mid_r3))*0.446365802
Epad out 0 shelf_out3 0 1.000000000
.ends
Vin in_src 0 AC 1
X1 in_src out CHANNEL_MODEL
.control
  ac dec 50 1e6 4000000000.0
  let loss_db = 20*log10(abs(v(out)))
  meas ac loss_dc FIND loss_db AT=1e6
  meas ac loss1 FIND loss_db AT=500000000.0
  meas ac loss2 FIND loss_db AT=2000000000.0
  print loss_dc
  print loss1
  print loss2
.endc
.end
