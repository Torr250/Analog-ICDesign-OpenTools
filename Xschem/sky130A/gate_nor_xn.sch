v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N 40 -60 40 20 {lab=out}
N 40 -160 40 -120 {lab=#net1}
N 40 -270 40 -220 {lab=VDDA}
N 40 -270 110 -270 {lab=VDDA}
N 110 -270 110 -90 {lab=VDDA}
N 40 -90 110 -90 {lab=VDDA}
N 40 -190 110 -190 {lab=VDDA}
N -130 50 -60 50 {lab=VSSA}
N -60 50 -60 120 {lab=VSSA}
N -60 120 110 120 {lab=VSSA}
N 110 50 110 120 {lab=VSSA}
N 40 50 110 50 {lab=VSSA}
N -130 80 -130 120 {lab=VSSA}
N -130 120 -60 120 {lab=VSSA}
N 40 80 40 120 {lab=VSSA}
N -130 -30 -130 20 {lab=out}
N -130 -30 40 -30 {lab=out}
N -30 50 0 50 {lab=A}
N -30 -190 -30 50 {lab=A}
N -30 -190 -0 -190 {lab=A}
N -190 -90 0 -90 {lab=B}
N -190 -190 -30 -190 {lab=A}
N 40 -10 160 -10 {lab=out}
N -190 50 -170 50 {lab=B}
N -190 -90 -190 50 {lab=B}
N -220 -90 -190 -90 {lab=B}
N -220 -190 -190 -190 {lab=A}
N 40 120 40 150 {lab=VSSA}
N 40 -310 40 -270 {lab=VDDA}
C {sky130_fd_pr/nfet_01v8.sym} 20 50 0 0 {name=M1
W=0.5
L=0.15
nf=1 
mult='nfing'
ad="expr('int((@nf + 1)/2) * @W / @nf * 0.29')"
pd="expr('2*int((@nf + 1)/2) * (@W / @nf + 0.29)')"
as="expr('int((@nf + 2)/2) * @W / @nf * 0.29')"
ps="expr('2*int((@nf + 2)/2) * (@W / @nf + 0.29)')"
nrd="expr('0.29 / @W ')" nrs="expr('0.29 / @W ')"
sa=0 sb=0 sd=0
model=nfet_01v8
spiceprefix=X
}
C {sky130_fd_pr/pfet_01v8.sym} 20 -90 0 0 {name=M2
W=1.4
L=0.15
nf=1
mult='nfing*4'
ad="expr('int((@nf + 1)/2) * @W / @nf * 0.29')"
pd="expr('2*int((@nf + 1)/2) * (@W / @nf + 0.29)')"
as="expr('int((@nf + 2)/2) * @W / @nf * 0.29')"
ps="expr('2*int((@nf + 2)/2) * (@W / @nf + 0.29)')"
nrd="expr('0.29 / @W ')" nrs="expr('0.29 / @W ')"
sa=0 sb=0 sd=0
model=pfet_01v8
spiceprefix=X
}
C {sky130_fd_pr/nfet_01v8.sym} -150 50 0 0 {name=M3
W=0.5
L=0.15
nf=1 
mult='nfing'
ad="expr('int((@nf + 1)/2) * @W / @nf * 0.29')"
pd="expr('2*int((@nf + 1)/2) * (@W / @nf + 0.29)')"
as="expr('int((@nf + 2)/2) * @W / @nf * 0.29')"
ps="expr('2*int((@nf + 2)/2) * (@W / @nf + 0.29)')"
nrd="expr('0.29 / @W ')" nrs="expr('0.29 / @W ')"
sa=0 sb=0 sd=0
model=nfet_01v8
spiceprefix=X
}
C {sky130_fd_pr/pfet_01v8.sym} 20 -190 0 0 {name=M4
W=1.4
L=0.15
nf=1
mult='nfing*4'
ad="expr('int((@nf + 1)/2) * @W / @nf * 0.29')"
pd="expr('2*int((@nf + 1)/2) * (@W / @nf + 0.29)')"
as="expr('int((@nf + 2)/2) * @W / @nf * 0.29')"
ps="expr('2*int((@nf + 2)/2) * (@W / @nf + 0.29)')"
nrd="expr('0.29 / @W ')" nrs="expr('0.29 / @W ')"
sa=0 sb=0 sd=0
model=pfet_01v8
spiceprefix=X
}
C {ipin.sym} -200 -390 0 0 {name=p6 lab=A}
C {iopin.sym} -80 -370 2 0 {name=p7 lab=VDDA}
C {iopin.sym} 10 -370 2 0 {name=p8 lab=VSSA}
C {opin.sym} 80 -370 0 0 {name=p9 lab=out}
C {code_shown.sym} -300 -280 0 0 {name=SPICE only_toplevel=false 
value="
.param nfing=1
"}
C {lab_pin.sym} -220 -190 0 0 {name=p11 sig_type=std_logic lab=A}
C {lab_pin.sym} 160 -10 0 1 {name=p12 sig_type=std_logic lab=out}
C {lab_pin.sym} 40 -310 0 0 {name=p13 sig_type=std_logic lab=VDDA}
C {lab_pin.sym} 40 150 0 0 {name=p14 sig_type=std_logic lab=VSSA}
C {lab_pin.sym} -220 -90 0 0 {name=p10 sig_type=std_logic lab=B}
C {ipin.sym} -200 -360 0 0 {name=p1 lab=B}
