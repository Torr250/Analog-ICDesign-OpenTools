v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N -20 -0 20 -0 {lab=N1}
N -180 -0 -140 -0 {lab=in}
N 140 0 180 0 {lab=out}
N -90 -80 -90 -50 {lab=VDDA}
N -90 -80 70 -80 {lab=VDDA}
N 70 -80 70 -50 {lab=VDDA}
N -90 50 -90 80 {lab=VSSA}
N -90 80 70 80 {lab=VSSA}
N 70 50 70 80 {lab=VSSA}
N 0 -110 0 -80 {lab=VDDA}
N 0 80 0 100 {lab=VSSA}
N 0 -30 0 0 {lab=N1}
C {gate_not_x1.sym} -120 0 0 0 {name=x1}
C {gate_not_x1.sym} 40 0 0 0 {name=x2}
C {lab_pin.sym} -180 0 0 0 {name=p5 sig_type=std_logic lab=in}
C {lab_pin.sym} 180 0 0 1 {name=p6 sig_type=std_logic lab=out}
C {lab_pin.sym} 0 -110 0 0 {name=p7 sig_type=std_logic lab=VDDA}
C {lab_pin.sym} 0 100 0 0 {name=p8 sig_type=std_logic lab=VSSA}
C {lab_pin.sym} 0 -30 0 0 {name=p1 sig_type=std_logic lab=N1}
C {ipin.sym} -190 -200 0 0 {name=p2 lab=in}
C {opin.sym} 150 -200 0 0 {name=p3 lab=out}
C {iopin.sym} -80 -200 0 0 {name=p4 lab=VDDA}
C {iopin.sym} 20 -200 0 0 {name=p9 lab=VSSA}
