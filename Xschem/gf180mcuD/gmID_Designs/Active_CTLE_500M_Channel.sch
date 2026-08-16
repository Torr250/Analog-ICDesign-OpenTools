v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
B 2 620 -390 1420 10 {flags=graph
y1=-0.5
y2=0.5
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=8.5062046e-08
x2=1.088115e-07
divx=5
subdivx=4
xlabmag=1.0
ylabmag=1.0
dataset=-1
unitx=1
logx=0
logy=0
color="1 7 4"
node="ind
outd
rx"}
T {tcleval(gmIDN: [to_eng [xschem raw value gmIDn 0]])} -20 -580 0 0 0.3 0.3 {floater=1}
T {Calculated Parameters} -20 -620 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatN: [to_eng [xschem raw value vdsatn 0]])} -20 -550 0 0 0.3 0.3 {floater=1}
T {tcleval(Gain max: [to_eng [xschem raw value gainmax_db 0]] dB)} -20 -370 0 0 0.3 0.3 {floater=1}
T {tcleval(IDN: [to_eng [xschem raw value idn 0]])} -20 -520 0 0 0.3 0.3 {floater=1}
T {Measured Parameters} -20 -400 0 0 0.3 0.3 {floater=1}
T {tcleval(gmIDNB: [to_eng [xschem raw value gmIDnb 0]])} 160 -580 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatNB: [to_eng [xschem raw value vdsatnb 0]])} 160 -550 0 0 0.3 0.3 {floater=1}
T {tcleval(IDNB: [to_eng [xschem raw value idnb 0]])} 160 -520 0 0 0.3 0.3 {floater=1}
T {tcleval(GBW: [to_eng [xschem raw value gbw 0]] dB)} 180 -340 0 0 0.3 0.3 {floater=1}
T {tcleval(Av: [to_eng [xschem raw value av 0]])} -20 -480 0 0 0.3 0.3 {floater=1}
T {tcleval(Av: [to_eng 20*log10([xschem raw value av 0])] dB)} 160 -480 0 0 0.3 0.3 {floater=1}
T {tcleval(Peak Freq: [to_eng [xschem raw value peak_freq 0]] Hz)} -20 -340 0 0 0.3 0.3 {floater=1}
T {tcleval(Gain min: [to_eng [xschem raw value gainmin_db 0]] dB)} 180 -370 0 0 0.3 0.3 {floater=1}
N -600 -260 -600 -230 {lab=#net1}
N -490 40 -440 40 {lab=#net2}
N -490 40 -490 70 {lab=#net2}
N 180 -120 180 -60 {lab=OUTP}
N -40 -120 -40 -60 {lab=OUTN}
N 180 -220 180 -180 {lab=VDD}
N -40 -220 -40 -180 {lab=VDD}
N -40 0 -40 40 {lab=Vx1}
N 180 0 180 40 {lab=Vx2}
N -140 -30 -80 -30 {lab=RxP}
N 220 -30 270 -30 {lab=RxN}
N -40 -30 180 -30 {lab=0}
N 70 -30 70 -0 {lab=0}
N -40 40 -40 110 {lab=Vx1}
N -150 140 -80 140 {lab=VBN}
N -40 140 30 140 {lab=0}
N 30 140 30 200 {lab=0}
N -40 200 30 200 {lab=0}
N -40 170 -40 200 {lab=0}
N -40 200 -40 230 {lab=0}
N 390 310 440 310 {lab=OUTD}
N 390 310 390 340 {lab=OUTD}
N 200 350 200 420 {lab=OUTP}
N 200 350 350 350 {lab=OUTP}
N 280 390 280 420 {lab=OUTN}
N 280 390 350 390 {lab=OUTN}
N -330 0 -330 110 {lab=Vx}
N -330 -30 -270 -30 {lab=0}
N -270 -30 -270 210 {lab=0}
N -330 210 -270 210 {lab=0}
N -330 170 -330 210 {lab=0}
N -330 140 -270 140 {lab=0}
N -410 -30 -370 -30 {lab=Vref}
N -660 30 -660 70 {lab=Vref}
N -660 50 -590 50 {lab=Vref}
N -590 -30 -590 50 {lab=Vref}
N -590 -30 -410 -30 {lab=Vref}
N -580 120 -530 120 {lab=Vref}
N -330 -120 -330 -60 {lab=Vo}
N -330 -220 -330 -180 {lab=VDD}
N -330 210 -330 230 {lab=0}
N -560 80 -530 80 {lab=Vo}
N -560 -10 -560 80 {lab=Vo}
N -560 -10 -440 -10 {lab=Vo}
N -440 -90 -440 -10 {lab=Vo}
N -440 -90 -330 -90 {lab=Vo}
N -490 450 -490 480 {lab=#net3}
N -280 450 -280 480 {lab=#net3}
N -390 480 -390 500 {lab=#net3}
N -450 400 -430 400 {lab=VSwing}
N -430 360 -430 400 {lab=VSwing}
N -390 360 -350 360 {lab=VSwing}
N -350 360 -350 400 {lab=VSwing}
N -350 400 -320 400 {lab=VSwing}
N -430 360 -390 360 {lab=VSwing}
N -490 480 -280 480 {lab=#net3}
N -340 440 -320 440 {lab=0}
N -450 440 -430 440 {lab=0}
N -490 360 -490 390 {lab=INP}
N -490 360 -450 360 {lab=INP}
N -280 360 -280 390 {lab=INN}
N -330 360 -280 360 {lab=INN}
N 180 40 180 110 {lab=Vx2}
N 70 140 140 140 {lab=VBN}
N 180 140 250 140 {lab=0}
N 250 140 250 200 {lab=0}
N 180 200 250 200 {lab=0}
N 180 170 180 200 {lab=0}
N 180 200 180 230 {lab=0}
N 410 -90 410 -60 {lab=Vx1}
N 500 -90 500 -60 {lab=Vx1}
N 410 -90 500 -90 {lab=Vx1}
N 410 0 410 30 {lab=Vx2}
N 500 0 500 30 {lab=Vx2}
N 410 30 500 30 {lab=Vx2}
N -1080 500 -1080 530 {lab=VRAND}
N -1080 500 -1050 500 {lab=VRAND}
N -850 500 -820 500 {lab=D}
N -820 500 -700 500 {lab=D}
N -850 500 -850 530 {lab=D}
N -1040 690 -1000 690 {lab=D}
N -960 650 -960 680 {lab=in2}
N -960 650 -910 650 {lab=in2}
N -850 650 -790 650 {lab=in}
N -820 650 -820 680 {lab=in}
N -1060 730 -1060 760 {lab=#net4}
N -1060 730 -1000 730 {lab=#net4}
N -790 650 -750 650 {lab=in}
N -750 650 -750 670 {lab=in}
N -750 670 -730 670 {lab=in}
N -690 630 -690 660 {lab=VSwing}
N -690 630 -660 630 {lab=VSwing}
N -440 40 -420 40 {lab=#net2}
N -420 40 -420 60 {lab=#net2}
N -420 140 -370 140 {lab=VBN}
N -420 120 -420 170 {lab=VBN}
N 390 540 440 540 {lab=IND}
N 390 540 390 570 {lab=IND}
N 200 580 200 650 {lab=INP}
N 200 580 350 580 {lab=INP}
N 280 620 280 650 {lab=INN}
N 280 620 350 620 {lab=INN}
N -140 380 -90 380 {lab=INP}
N -140 460 -90 460 {lab=INN}
N 30 380 80 380 {lab=RxP}
N 30 460 80 460 {lab=RxN}
N 750 310 800 310 {lab=Rx}
N 750 310 750 340 {lab=Rx}
N 560 350 710 350 {lab=RxP}
N 640 390 710 390 {lab=RxN}
C {symbols/nfet_03v3.sym} -60 -30 0 0 {name=M1
L=0.4u
W=11u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {vcvs.sym} -490 100 0 0 {name=E1 value=50}
C {devices/code_shown.sym} -1130 -410 0 0 {name=MODELS only_toplevel=true
format="tcleval( @value )"
value="
.include $::180MCU_MODELS/design.ngspice
.lib $::180MCU_MODELS/sm141064.ngspice typical
.param sw_stat_global=0
.param sw_stat_mismatch=0
"}
C {gnd.sym} -490 130 0 0 {name=l11 lab=0}
C {devices/code_shown.sym} -1140 -250 0 0 {name=SPICE only_toplevel=false 
value="
*.options method=gear
.param VDD=3.3 TEMP=27 freq=1e9 VSwing=0.3
.temp \{TEMP\}
.csparam vdd = \{vdd\}
**** interactive sim
.control
  op
  tran 10p 200n 
  let gmn = @m.xm1.m0[gm]
  let gdsn = @m.xm1.m0[gds]
  let idn = @m.xm1.m0[id]
  let vdsn = @m.xm1.m0[vds]
  let vdsatn = @m.xm1.m0[vdsat]
  let gmnb = @m.xm3.m0[gm]
  let gdsnb = @m.xm3.m0[gds]
  let idnb = @m.xm3.m0[id]
  let vdsatnb = @m.xm3.m0[vdsat]
  let vdsnb = @m.xm3.m0[vds]
  let gmIDn = gmn/idn
  let gmIDnb = gmnb/idnb
  let rl = (vdd-(vdsn+vdsnb))/(idn)
  let Av = gmn/(gdsn + 1/rl)
  option remzerovec
  save all
  write Active_CTLE_500M_Channel.raw
  write /foss/designs/gf180mcuD/eye_diagram/Active_CTLE_500M_Channel.raw
.endc
"}
C {vsource.sym} -600 -200 0 0 {name=V9 value='VDD' savecurrent=false}
C {vsource.sym} -600 -290 0 0 {name=V7 value=0 savecurrent=false}
C {capa.sym} 280 450 0 0 {name=C2
m=1
value=90f
footprint=1206
device="ceramic capacitor"}
C {vdd.sym} -600 -320 0 0 {name=l1 lab=VDD}
C {gnd.sym} -600 -170 0 0 {name=l4 lab=0}
C {gnd.sym} 280 480 0 0 {name=l6 lab=0}
C {lab_wire.sym} 250 350 0 0 {name=p1 sig_type=std_logic lab=OUTP}
C {devices/launcher.sym} -495 -475 0 0 {name=h4 
descr="Select arrow and 
Ctrl-Left-Click to load/unload
simulation .raw file" 
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw
"
}
C {devices/launcher.sym} -500 -540 0 0 {name=h2
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {symbols/nfet_03v3.sym} 200 -30 0 1 {name=M2
L=0.4u
W=11u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {res.sym} -40 -150 0 0 {name=R1
value=3.5k
footprint=1206
device=resistor
m=1}
C {res.sym} 180 -150 0 0 {name=R2
value=3.5k
footprint=1206
device=resistor
m=1}
C {vdd.sym} -40 -220 0 0 {name=l3 lab=VDD}
C {vdd.sym} 180 -220 0 0 {name=l5 lab=VDD}
C {gnd.sym} 70 0 0 0 {name=l7 lab=0}
C {symbols/nfet_03v3.sym} -60 140 0 0 {name=M3
L=0.7u
W=35u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} -40 230 0 0 {name=l8 lab=0}
C {vcvs.sym} 390 370 0 0 {name=E2 value=0.5}
C {gnd.sym} 390 400 0 0 {name=l9 lab=0}
C {capa.sym} 200 450 0 0 {name=C1
m=1
value=90f
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 200 480 0 0 {name=l10 lab=0}
C {lab_wire.sym} 300 390 0 0 {name=p3 sig_type=std_logic lab=OUTN}
C {res.sym} -660 0 0 0 {name=R3
value=5.5k
footprint=1206
device=resistor
m=1}
C {res.sym} -660 100 0 0 {name=R4
value=6.5k
footprint=1206
device=resistor
m=1}
C {symbols/nfet_03v3.sym} -350 -30 0 0 {name=M4
L=0.4u
W=11u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} -350 140 0 0 {name=M5
L=0.7u
W=35u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} -660 130 0 0 {name=l2 lab=0}
C {vdd.sym} -660 -30 0 0 {name=l12 lab=VDD}
C {res.sym} -330 -150 0 0 {name=R5
value=3.5k
footprint=1206
device=resistor
m=1}
C {vdd.sym} -330 -220 0 0 {name=l13 lab=VDD}
C {gnd.sym} -330 230 0 0 {name=l14 lab=0}
C {lab_wire.sym} -530 -30 0 0 {name=p2 sig_type=std_logic lab=Vref}
C {lab_wire.sym} -560 120 0 0 {name=p4 sig_type=std_logic lab=Vref}
C {lab_wire.sym} -380 140 0 0 {name=p5 sig_type=std_logic lab=VBN}
C {lab_wire.sym} -410 -90 0 0 {name=p6 sig_type=std_logic lab=Vo}
C {lab_wire.sym} -330 60 0 0 {name=p7 sig_type=std_logic lab=Vx}
C {lab_wire.sym} -40 80 0 0 {name=p8 sig_type=std_logic lab=Vx1}
C {lab_wire.sym} -120 140 0 0 {name=p9 sig_type=std_logic lab=VBN}
C {vcvs.sym} -280 420 0 0 {name=E3 value=-1}
C {vsource.sym} -390 530 0 0 {name=V1 value='VDD-(VDD*0.45)' savecurrent=false}
C {vcvs.sym} -490 420 0 1 {name=E4 value=1}
C {gnd.sym} -390 560 0 0 {name=l15 lab=0}
C {lab_wire.sym} -460 360 0 0 {name=p10 sig_type=std_logic lab=INP}
C {lab_wire.sym} -290 360 0 0 {name=p11 sig_type=std_logic lab=INN}
C {lab_wire.sym} -110 -30 0 0 {name=p12 sig_type=std_logic lab=RxP}
C {lab_wire.sym} 240 -30 0 1 {name=p13 sig_type=std_logic lab=RxN}
C {lab_wire.sym} -40 -90 0 0 {name=p14 sig_type=std_logic lab=OUTN}
C {lab_wire.sym} 180 -90 0 0 {name=p15 sig_type=std_logic lab=OUTP}
C {lab_wire.sym} 420 310 0 0 {name=p16 sig_type=std_logic lab=OUTD}
C {symbols/nfet_03v3.sym} 160 140 0 0 {name=M6
L=0.7u
W=35u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 180 230 0 0 {name=l16 lab=0}
C {lab_wire.sym} 180 80 0 0 {name=p17 sig_type=std_logic lab=Vx2}
C {lab_wire.sym} 100 140 0 0 {name=p18 sig_type=std_logic lab=VBN}
C {res.sym} 410 -30 0 0 {name=R6
value=4.5k
footprint=1206
device=resistor
m=1}
C {capa.sym} 500 -30 0 0 {name=C3
m=1
value=220f
footprint=1206
device="ceramic capacitor"}
C {lab_wire.sym} 450 -90 0 0 {name=p19 sig_type=std_logic lab=Vx1}
C {lab_wire.sym} 470 30 0 0 {name=p20 sig_type=std_logic lab=Vx2}
C {gnd.sym} -1080 590 0 0 {name=l17 lab=0}
C {lab_pin.sym} -1050 500 2 0 {name=p21 sig_type=std_logic lab=VRAND}
C {vsource.sym} -1080 560 0 0 {name=V4 value="trrandom (2 '1/freq' 750p 1 0)" savecurrent=false}
C {lab_pin.sym} -700 500 2 0 {name=p22 sig_type=std_logic lab=D
}
C {gnd.sym} -850 590 0 0 {name=l18 lab=0}
C {bsource.sym} -850 560 0 0 {name=B1 VAR=V FUNC="sgn(V(VRAND))*VDD/2+VDD/2" m=1}
C {vcvs.sym} -960 710 0 0 {name=E5 value=1}
C {gnd.sym} -960 740 0 0 {name=l19 lab=0}
C {lab_pin.sym} -1040 690 2 1 {name=p23 sig_type=std_logic lab=D
}
C {lab_wire.sym} -930 650 0 0 {name=p24 sig_type=std_logic lab=in2}
C {res.sym} -880 650 1 0 {name=R7
value=50
footprint=1206
device=resistor
m=1}
C {lab_wire.sym} -790 650 0 0 {name=p25 sig_type=std_logic lab=in}
C {capa.sym} -820 710 0 0 {name=C4
m=1
value=1p
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} -820 740 0 0 {name=l20 lab=0}
C {vsource.sym} -1060 790 0 0 {name=V3 value='VDD/2' savecurrent=false}
C {gnd.sym} -1060 820 0 0 {name=l21 lab=0}
C {lab_wire.sym} -390 360 0 0 {name=p26 sig_type=std_logic lab=VSwing}
C {gnd.sym} -430 440 0 0 {name=l22 lab=0}
C {gnd.sym} -340 440 0 0 {name=l23 lab=0}
C {vcvs.sym} -690 690 0 0 {name=E6 value='VSwing'}
C {gnd.sym} -730 710 0 0 {name=l24 lab=0}
C {gnd.sym} -690 720 0 0 {name=l25 lab=0}
C {lab_wire.sym} -670 630 0 0 {name=p27 sig_type=std_logic lab=VSwing}
C {res.sym} -420 90 0 0 {name=R8
value=10k
footprint=1206
device=resistor
m=1}
C {capa.sym} -420 200 0 0 {name=C5
m=1
value=1
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} -420 230 0 0 {name=l26 lab=0}
C {capa.sym} 280 680 0 0 {name=C6
m=1
value=90f
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 280 710 0 0 {name=l27 lab=0}
C {lab_wire.sym} 250 580 0 0 {name=p28 sig_type=std_logic lab=INP}
C {vcvs.sym} 390 600 0 0 {name=E7 value=0.5}
C {gnd.sym} 390 630 0 0 {name=l28 lab=0}
C {capa.sym} 200 680 0 0 {name=C7
m=1
value=90f
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 200 710 0 0 {name=l29 lab=0}
C {lab_wire.sym} 300 620 0 0 {name=p29 sig_type=std_logic lab=INN}
C {lab_wire.sym} 420 540 0 0 {name=p30 sig_type=std_logic lab=IND}
C {lab_wire.sym} -120 460 0 0 {name=p31 sig_type=std_logic lab=INN}
C {lab_wire.sym} -120 380 0 0 {name=p32 sig_type=std_logic lab=INP}
C {lab_wire.sym} 60 460 0 1 {name=p33 sig_type=std_logic lab=RxN}
C {lab_wire.sym} 60 380 0 1 {name=p34 sig_type=std_logic lab=RxP}
C {lab_wire.sym} 610 350 0 0 {name=p35 sig_type=std_logic lab=RxP}
C {vcvs.sym} 750 370 0 0 {name=E8 value=0.5}
C {gnd.sym} 750 400 0 0 {name=l31 lab=0}
C {lab_wire.sym} 660 390 0 0 {name=p36 sig_type=std_logic lab=RxN}
C {lab_wire.sym} 780 310 0 0 {name=p37 sig_type=std_logic lab=Rx}
C {channel_model/tline_m10at500MHz.sym} -70 410 0 0 {name=x1}
C {channel_model/tline_m10at500MHz.sym} -70 490 0 0 {name=x2}
C {code_shown.sym} -1160 -650 0 0 {name=s1 only_toplevel=false value="
.include /foss/designs/gf180mcuD/channel_model/tline_m10at500MHz.sp
"}
