v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N 60 0 110 0 {lab=out}
N 110 0 110 20 {lab=out}
N 10 -20 10 20 {lab=out}
N 10 0 60 0 {lab=out}
N -60 70 -60 90 {lab=0}
N -60 70 -30 70 {lab=0}
N -80 50 -30 50 {lab=in}
N -80 -50 -80 50 {lab=in}
N -140 -50 -80 -50 {lab=in}
N -80 -50 -30 -50 {lab=in}
N -60 -30 -60 -10 {lab=0}
N -60 -30 -30 -30 {lab=0}
N 240 40 240 110 {lab=0}
N -60 110 240 110 {lab=0}
N -60 90 -60 110 {lab=0}
N 10 80 10 110 {lab=0}
N 110 80 110 110 {lab=0}
N 10 -120 10 -80 {lab=#net1}
N 10 -120 240 -120 {lab=#net1}
N 240 -120 240 -20 {lab=#net1}
N 70 110 70 140 {lab=0}
N -130 -50 -130 20 {lab=in}
N -130 80 -130 110 {lab=0}
N -130 110 -60 110 {lab=0}
N 110 -30 110 -0 {lab=out}
N 110 -120 110 -90 {lab=#net1}
C {capa.sym} 110 50 0 0 {name=C2
m=1
value='trise/(2.2*100)'
footprint=1206
device="ceramic capacitor"}
C {lab_pin.sym} 110 0 2 0 {name=p3 sig_type=std_logic lab=out}
C {gnd.sym} -60 -10 0 0 {name=l9 lab=0}
C {switch_ngspice.sym} 10 -50 0 0 {name=S1 model=SWP
device_model=".MODEL SW1 SW 
+ VT=0.9 VH=0.01
+ RON=0.01 ROFF=10G "}
C {switch_ngspice.sym} 10 50 0 0 {name=S2 model=SWN
device_model=".MODEL SW1 SW 
+ VT=0.9 VH=0.01
+ RON=0.01 ROFF=10G "}
C {code_shown.sym} -140 -230 0 0 {name=SPICE only_toplevel=false 
value="
.param vhigh=1.8 trise=200p
.model SWP SW VT='vhigh/2.01' VH=0.01 RON=100k ROFF=100
.model SWN SW VT='vhigh/1.99' VH=0.01 RON=100 ROFF=100k
"}
C {vsource.sym} 240 10 0 0 {name=V1 value='vhigh' savecurrent=false}
C {lab_pin.sym} -140 -50 2 1 {name=p1 sig_type=std_logic lab=in}
C {gnd.sym} 70 140 0 0 {name=l1 lab=0}
C {ipin.sym} -30 -290 0 0 {name=p2 lab=in}
C {opin.sym} 130 -290 0 0 {name=p4 lab=out}
C {capa.sym} -130 50 0 0 {name=C1
m=1
value=50f
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 110 -60 0 0 {name=C3
m=1
value='trise/(2.2*100)'
footprint=1206
device="ceramic capacitor"}
