v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
B 2 2120 530 2920 930 {flags=graph
y1=4.6e-101
y2=0.00012
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=0
x2=3.3
divx=5
subdivx=4
xlabmag=1.0
ylabmag=1.0
dataset=-1
unitx=1
logx=0
logy=0
color="4 5 21"
node="i(idn_simple)
i(idn_cascode)
i(idn_lowvolt)"}
B 2 2120 -150 2920 250 {flags=graph
y1=0
y2=0.00012
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=0
x2=3.3
divx=5
subdivx=4
xlabmag=1.0
ylabmag=1.0
dataset=-1
unitx=1
logx=0
logy=0
color="4 5 21"
node="i(idp_simple)
i(idp_cascode)
i(idp_lowvolt)"}
B 2 2980 530 3780 930 {flags=graph
y1=1.2974164e-320
y2=54000000
ypos1=0
ypos2=2
divy=5
subdivy=4
unity=1
x1=0
x2=3.3
divx=5
subdivx=4
xlabmag=1.0
ylabmag=1.0
dataset=-1
unitx=1
logx=0
logy=0
color="4 5 21"
node="deriv simple; 1 i(idn_simple) deriv() / abs()
deriv cascode; 1 i(idn_cascode) deriv() / abs()
deriv lowvolt; 1 i(idn_lowvolt) deriv() / abs()"}
B 2 2980 -150 3780 250 {flags=graph
y1=1.2974164e-320
y2=20000000
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=0
x2=3.3
divx=5
subdivx=4
xlabmag=1.0
ylabmag=1.0
dataset=-1
unitx=1
logx=0
logy=0
color="4 5 21"
node="deriv simple; 1 i(idp_simple) deriv() / abs()
deriv cascode; 1 i(idp_cascode) deriv() / abs()
deriv lowvolt; 1 i(idp_lowvolt) deriv() / abs()"}
T {tcleval(gmIDN1: [to_eng [xschem raw value gmidn1 0]])} 120 990 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatN1: [to_eng [xschem raw value vdsatn1 0]])} 120 1020 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSN1: [to_eng [xschem raw value vdsn1 0]])} 120 1050 0 0 0.3 0.3 {floater=1}
T {tcleval(gmIDN2: [to_eng [xschem raw value gmidn2 0]])} -140 990 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatN2: [to_eng [xschem raw value vdsatn2 0]])} -140 1020 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSN2: [to_eng [xschem raw value vdsn2 0]])} -140 1050 0 0 0.3 0.3 {floater=1}
T {tcleval(gmIDP4: [to_eng [xschem raw value gmidp4 0]])} 130 320 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatP4: [to_eng [xschem raw value vdsatp4 0]])} 130 350 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSP4: [to_eng [xschem raw value vdsp4 0]])} 130 380 0 0 0.3 0.3 {floater=1}
T {tcleval(gmIDP3: [to_eng [xschem raw value gmidp3 0]])} -130 320 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatP3: [to_eng [xschem raw value vdsatp3 0]])} -130 350 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSP3: [to_eng [xschem raw value vdsp3 0]])} -130 380 0 0 0.3 0.3 {floater=1}
T {tcleval(gmIDN5: [to_eng [xschem raw value gmidn5 0]])} 790 990 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatN5: [to_eng [xschem raw value vdsatn5 0]])} 790 1020 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSN5: [to_eng [xschem raw value vdsn5 0]])} 790 1050 0 0 0.3 0.3 {floater=1}
T {tcleval(gmIDP8: [to_eng [xschem raw value gmidp8 0]])} 800 310 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatP8: [to_eng [xschem raw value vdsatp8 0]])} 800 340 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSP8: [to_eng [xschem raw value vdsp8 0]])} 800 370 0 0 0.3 0.3 {floater=1}
T {tcleval(gmIDN13: [to_eng [xschem raw value gmidn13 0]])} 1690 990 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatN13: [to_eng [xschem raw value vdsatn13 0]])} 1690 1020 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSN13: [to_eng [xschem raw value vdsn13 0]])} 1690 1050 0 0 0.3 0.3 {floater=1}
T {tcleval(gmID16: [to_eng [xschem raw value gmidp16 0]])} 1700 310 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSatP16: [to_eng [xschem raw value vdsatp16 0]])} 1700 340 0 0 0.3 0.3 {floater=1}
T {tcleval(VDSP16: [to_eng [xschem raw value vdsp16 0]])} 1700 370 0 0 0.3 0.3 {floater=1}
N -300 -160 -300 -130 {lab=#net1}
N 140 860 190 860 {lab=0}
N 190 860 190 920 {lab=0}
N 140 920 190 920 {lab=0}
N 140 890 140 920 {lab=0}
N 140 920 140 940 {lab=0}
N 140 770 140 830 {lab=VON1}
N -100 860 -50 860 {lab=0}
N -100 860 -100 920 {lab=0}
N -100 920 -50 920 {lab=0}
N -50 890 -50 920 {lab=0}
N -50 920 -50 940 {lab=0}
N -10 860 100 860 {lab=VBN1}
N -50 790 10 790 {lab=VBN1}
N 10 790 10 860 {lab=VBN1}
N -50 730 -50 830 {lab=VBN1}
N 140 770 320 770 {lab=VON1}
N 320 770 320 820 {lab=VON1}
N -50 620 -50 670 {lab=VDD}
N -10 50 100 50 {lab=VBP1}
N -120 50 -50 50 {lab=VDD}
N -120 -20 -120 50 {lab=VDD}
N -120 -20 -50 -20 {lab=VDD}
N -50 -20 -50 20 {lab=VDD}
N 140 50 210 50 {lab=VDD}
N 210 -20 210 50 {lab=VDD}
N 140 -20 210 -20 {lab=VDD}
N 140 -20 140 20 {lab=VDD}
N 140 80 140 180 {lab=#net2}
N -50 80 -50 180 {lab=VBP1}
N -50 110 30 110 {lab=VBP1}
N 30 50 30 110 {lab=VBP1}
N -50 -50 -50 -20 {lab=VDD}
N 140 -50 140 -20 {lab=VDD}
N 360 870 390 870 {lab=0}
N 390 870 390 890 {lab=0}
N -330 70 -330 100 {lab=VSWING}
N -370 70 -330 70 {lab=VSWING}
N 360 830 410 830 {lab=VSWING}
N 180 230 210 230 {lab=0}
N 210 230 210 250 {lab=0}
N 180 190 230 190 {lab=VSWING}
N 810 860 860 860 {lab=0}
N 860 860 860 920 {lab=0}
N 810 920 860 920 {lab=0}
N 810 890 810 920 {lab=0}
N 810 920 810 940 {lab=0}
N 810 650 810 710 {lab=VON2}
N 570 860 620 860 {lab=0}
N 570 860 570 920 {lab=0}
N 570 920 620 920 {lab=0}
N 620 890 620 920 {lab=0}
N 620 920 620 940 {lab=0}
N 660 860 770 860 {lab=VBN2}
N 620 790 680 790 {lab=VBN2}
N 680 790 680 860 {lab=VBN2}
N 810 650 990 650 {lab=VON2}
N 990 650 990 700 {lab=VON2}
N 620 540 620 590 {lab=VDD}
N 660 0 770 0 {lab=VBP2}
N 550 0 620 0 {lab=VDD}
N 550 -70 550 0 {lab=VDD}
N 550 -70 620 -70 {lab=VDD}
N 620 -70 620 -30 {lab=VDD}
N 810 0 880 0 {lab=VDD}
N 880 -70 880 0 {lab=VDD}
N 810 -70 880 -70 {lab=VDD}
N 810 -70 810 -30 {lab=VDD}
N 620 -100 620 -70 {lab=VDD}
N 810 -100 810 -70 {lab=VDD}
N 1030 750 1060 750 {lab=0}
N 1060 750 1060 770 {lab=0}
N 1030 710 1080 710 {lab=VSWING}
N 850 230 880 230 {lab=0}
N 880 230 880 250 {lab=0}
N 850 190 900 190 {lab=VSWING}
N 810 770 810 830 {lab=VXN2}
N 620 770 620 830 {lab=VBN2}
N 620 650 620 710 {lab=VCN2}
N 660 740 770 740 {lab=VCN2}
N 680 680 680 740 {lab=VCN2}
N 620 680 680 680 {lab=VCN2}
N 620 30 620 70 {lab=VBP2}
N 620 50 690 50 {lab=VBP2}
N 690 0 690 50 {lab=VBP2}
N 620 130 620 180 {lab=VCP2}
N 660 100 770 100 {lab=VCP2}
N 620 150 690 150 {lab=VCP2}
N 690 100 690 150 {lab=VCP2}
N 810 130 810 180 {lab=#net3}
N 810 30 810 70 {lab=VXP2}
N 810 100 880 100 {lab=VDD}
N 880 0 880 100 {lab=VDD}
N 550 100 620 100 {lab=VDD}
N 550 0 550 100 {lab=VDD}
N 570 740 570 860 {lab=0}
N 570 740 620 740 {lab=0}
N 860 740 860 860 {lab=0}
N 810 740 860 740 {lab=0}
N 1710 860 1760 860 {lab=0}
N 1760 860 1760 920 {lab=0}
N 1710 920 1760 920 {lab=0}
N 1710 890 1710 920 {lab=0}
N 1710 920 1710 940 {lab=0}
N 1710 650 1710 710 {lab=VON3}
N 1470 860 1520 860 {lab=0}
N 1470 860 1470 920 {lab=0}
N 1470 920 1520 920 {lab=0}
N 1520 890 1520 920 {lab=0}
N 1520 920 1520 940 {lab=0}
N 1560 860 1670 860 {lab=VBN3}
N 1710 650 1890 650 {lab=VON3}
N 1890 650 1890 700 {lab=VON3}
N 1520 540 1520 590 {lab=VDD}
N 1560 0 1670 0 {lab=VBP3}
N 1450 0 1520 0 {lab=VDD}
N 1450 -70 1450 0 {lab=VDD}
N 1450 -70 1520 -70 {lab=VDD}
N 1520 -70 1520 -30 {lab=VDD}
N 1710 0 1780 0 {lab=VDD}
N 1780 -70 1780 0 {lab=VDD}
N 1710 -70 1780 -70 {lab=VDD}
N 1710 -70 1710 -30 {lab=VDD}
N 1520 -100 1520 -70 {lab=VDD}
N 1710 -100 1710 -70 {lab=VDD}
N 1930 750 1960 750 {lab=0}
N 1960 750 1960 770 {lab=0}
N 1930 710 1980 710 {lab=VSWING}
N 1750 230 1780 230 {lab=0}
N 1780 230 1780 250 {lab=0}
N 1750 190 1800 190 {lab=VSWING}
N 1710 770 1710 830 {lab=VXN3}
N 1520 770 1520 830 {lab=#net4}
N 1520 650 1520 710 {lab=VBN3}
N 1560 740 1670 740 {lab=VCN3}
N 1520 30 1520 70 {lab=#net5}
N 1520 130 1520 180 {lab=VBP3}
N 1560 100 1670 100 {lab=VCP3}
N 1520 150 1590 150 {lab=VBP3}
N 1710 130 1710 180 {lab=#net6}
N 1710 30 1710 70 {lab=VXP3}
N 1710 100 1780 100 {lab=VDD}
N 1780 0 1780 100 {lab=VDD}
N 1450 100 1520 100 {lab=VDD}
N 1450 0 1450 100 {lab=VDD}
N 1470 740 1470 860 {lab=0}
N 1470 740 1520 740 {lab=0}
N 1760 740 1760 860 {lab=0}
N 1710 740 1760 740 {lab=0}
N 1600 680 1600 860 {lab=VBN3}
N 1590 0 1590 150 {lab=VBP3}
N 1250 50 1320 50 {lab=VDD}
N 1320 -100 1320 -70 {lab=VDD}
N 1320 80 1320 180 {lab=VCP3}
N 1320 110 1390 110 {lab=VCP3}
N 1390 50 1390 110 {lab=VCP3}
N 1360 50 1390 50 {lab=VCP3}
N 1570 50 1570 100 {lab=VCP3}
N 1390 50 1570 50 {lab=VCP3}
N 1320 540 1320 590 {lab=VDD}
N 1320 650 1320 710 {lab=VCN3}
N 1320 710 1320 770 {lab=VCN3}
N 1520 680 1600 680 {lab=VBN3}
N 1360 800 1580 800 {lab=VCN3}
N 1580 740 1580 800 {lab=VCN3}
N 1320 830 1320 850 {lab=#net7}
N 1320 910 1320 940 {lab=0}
N 1270 920 1320 920 {lab=0}
N 1270 800 1270 920 {lab=0}
N 1270 800 1320 800 {lab=0}
N 1270 880 1320 880 {lab=0}
N 1360 880 1380 880 {lab=VCN3}
N 1380 800 1380 880 {lab=VCN3}
N 1380 730 1380 800 {lab=VCN3}
N 1320 730 1380 730 {lab=VCN3}
N 1320 -10 1320 20 {lab=#net8}
N 1250 -40 1250 50 {lab=VDD}
N 1250 -40 1320 -40 {lab=VDD}
N 1360 -40 1390 -40 {lab=VCP3}
N 1390 -40 1390 50 {lab=VCP3}
N 1250 -80 1250 -40 {lab=VDD}
N 1250 -80 1320 -80 {lab=VDD}
N 150 1530 200 1530 {lab=0}
N 200 1530 200 1590 {lab=0}
N 150 1590 200 1590 {lab=0}
N 150 1560 150 1590 {lab=0}
N 150 1590 150 1610 {lab=0}
N 150 1310 220 1310 {lab=VDD}
N 220 1240 220 1310 {lab=VDD}
N 150 1240 220 1240 {lab=VDD}
N 150 1240 150 1280 {lab=VDD}
N 150 1210 150 1240 {lab=VDD}
N 70 1310 110 1310 {lab=VBP1}
N 70 1530 110 1530 {lab=VBN1}
N 150 1340 150 1370 {lab=#net9}
N 150 1430 150 1500 {lab=VSimple}
N 750 1710 800 1710 {lab=0}
N 800 1710 800 1770 {lab=0}
N 750 1770 800 1770 {lab=0}
N 750 1740 750 1770 {lab=0}
N 750 1770 750 1790 {lab=0}
N 750 1620 750 1680 {lab=VN02}
N 800 1590 800 1710 {lab=0}
N 750 1590 800 1590 {lab=0}
N 750 1270 820 1270 {lab=VDD}
N 820 1200 820 1270 {lab=VDD}
N 750 1200 820 1200 {lab=VDD}
N 750 1200 750 1240 {lab=VDD}
N 750 1170 750 1200 {lab=VDD}
N 750 1300 750 1340 {lab=VN01}
N 750 1370 820 1370 {lab=VDD}
N 820 1270 820 1370 {lab=VDD}
N 750 1400 750 1430 {lab=#net10}
N 750 1490 750 1560 {lab=VCascode}
N 670 1270 710 1270 {lab=VBP2}
N 670 1370 710 1370 {lab=VCP2}
N 670 1710 710 1710 {lab=VBN2}
N 670 1590 710 1590 {lab=VCN2}
N 1570 1730 1620 1730 {lab=0}
N 1620 1730 1620 1790 {lab=0}
N 1570 1790 1620 1790 {lab=0}
N 1570 1760 1570 1790 {lab=0}
N 1570 1790 1570 1810 {lab=0}
N 1570 1640 1570 1700 {lab=VN04}
N 1620 1610 1620 1730 {lab=0}
N 1570 1610 1620 1610 {lab=0}
N 1570 1290 1640 1290 {lab=VDD}
N 1640 1220 1640 1290 {lab=VDD}
N 1570 1220 1640 1220 {lab=VDD}
N 1570 1220 1570 1260 {lab=VDD}
N 1570 1190 1570 1220 {lab=VDD}
N 1570 1320 1570 1360 {lab=VN03}
N 1570 1390 1640 1390 {lab=VDD}
N 1640 1290 1640 1390 {lab=VDD}
N 1570 1420 1570 1450 {lab=#net11}
N 1570 1510 1570 1580 {lab=Vlowvolt}
N 1490 1290 1530 1290 {lab=VBP3}
N 1490 1390 1530 1390 {lab=VCP3}
N 1490 1730 1530 1730 {lab=VBN3}
N 1490 1610 1530 1610 {lab=VCN3}
C {symbols/nfet_03v3.sym} 120 860 0 0 {name=M1
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/code_shown.sym} -820 -420 0 0 {name=MODELS only_toplevel=true
format="tcleval( @value )"
value="
.include $::180MCU_MODELS/design.ngspice
.lib $::180MCU_MODELS/sm141064.ngspice typical
.param sw_stat_global=0
.param sw_stat_mismatch=0
"}
C {devices/code_shown.sym} -830 -260 0 0 {name=SPICE only_toplevel=false 
value="
*.options method=gear
.param VDD=3.3 TEMP=27 VSwing=\{VDD/2\}
.temp \{TEMP\}
.csparam vdd = \{vdd\}
**** interactive sim
.control
  op
  dc v1 0 3.3 10m
  let gmn1 = @m.xm1.m0[gm]
  let gdsn1 = @m.xm1.m0[gds]
  let idn1 = @m.xm1.m0[id]
  let vdsatn1 = @m.xm1.m0[vdsat]
  let vdsn1 = @m.xm1.m0[vds]
  let gmIDn1 = gmn1/idn1

  let gmn2 = @m.xm2.m0[gm]
  let gdsn2 = @m.xm2.m0[gds]
  let idn2 = @m.xm2.m0[id]
  let vdsatn2 = @m.xm2.m0[vdsat]
  let vdsn2 = @m.xm2.m0[vds]
  let gmIDn2 = gmn2/idn2

  let gmp3 = @m.xm3.m0[gm]
  let gdsp3 = @m.xm3.m0[gds]
  let idp3 = @m.xm3.m0[id]
  let vdsatp3 = @m.xm3.m0[vdsat]
  let vdsp3 = @m.xm3.m0[vds]
  let gmIDp3 = gmp3/idp3

  let gmp4 = @m.xm4.m0[gm]
  let gdsp4 = @m.xm4.m0[gds]
  let idp4 = @m.xm4.m0[id]
  let vdsatp4 = @m.xm4.m0[vdsat]
  let vdsp4 = @m.xm4.m0[vds]
  let gmIDp4 = gmp4/idp4

  let gmn5 = @m.xm5.m0[gm]
  let gdsn5 = @m.xm5.m0[gds]
  let idn5 = @m.xm5.m0[id]
  let vdsatn5 = @m.xm5.m0[vdsat]
  let vdsn5 = @m.xm5.m0[vds]
  let gmIDn5 = gmn5/idn5

  let gmp8 = @m.xm8.m0[gm]
  let gdsp8 = @m.xm8.m0[gds]
  let idp8 = @m.xm8.m0[id]
  let vdsatp8 = @m.xm8.m0[vdsat]
  let vdsp8 = @m.xm8.m0[vds]
  let gmIDp8 = gmp8/idp8

  let gmn13 = @m.xm13.m0[gm]
  let gdsn13 = @m.xm13.m0[gds]
  let idn13 = @m.xm13.m0[id]
  let vdsatn13 = @m.xm13.m0[vdsat]
  let vdsn13 = @m.xm13.m0[vds]
  let gmIDn13 = gmn13/idn13

  let gmp16 = @m.xm16.m0[gm]
  let gdsp16 = @m.xm16.m0[gds]
  let idp16 = @m.xm16.m0[id]
  let vdsatp16 = @m.xm16.m0[vdsat]
  let vdsp16 = @m.xm16.m0[vds]
  let gmIDp16 = gmp16/idp16

  let idn_simple = abs(i(e1))
  let idp_simple = abs(i(e2))
  let idn_cascode = abs(i(e3))
  let idp_cascode = abs(i(e4))
  let idn_lowvolt = abs(i(e5))
  let idp_lowvolt = abs(i(e6))
  print gmidn1
  print idn1
  option remzerovec
  save all
  write gmID_Course_S06.raw
.endc
"}
C {vsource.sym} -300 -100 0 0 {name=V9 value='VDD' savecurrent=false}
C {vsource.sym} -300 -190 0 0 {name=V7 value=0 savecurrent=false}
C {vdd.sym} -300 -220 0 0 {name=l1 lab=VDD}
C {gnd.sym} -300 -70 0 0 {name=l4 lab=0}
C {gnd.sym} 140 940 0 0 {name=l7 lab=0}
C {devices/launcher.sym} 695 -235 0 0 {name=h4 
descr="Select arrow and 
Ctrl-Left-Click to load/unload
simulation .raw file" 
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw
"
}
C {devices/launcher.sym} 690 -300 0 0 {name=h2
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {symbols/nfet_03v3.sym} -30 860 0 1 {name=M2
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} -50 940 0 1 {name=l2 lab=0}
C {isource.sym} -50 700 0 0 {name=I0 value=100u}
C {vdd.sym} -50 620 0 0 {name=l3 lab=VDD}
C {vsource.sym} -330 130 0 0 {name=V1 value='VSwing' savecurrent=false}
C {gnd.sym} -330 160 0 0 {name=l5 lab=0}
C {lab_wire.sym} 60 860 0 0 {name=p1 sig_type=std_logic lab=VBN1}
C {lab_wire.sym} 220 770 0 0 {name=p2 sig_type=std_logic lab=VON1}
C {gnd.sym} -50 240 0 1 {name=l8 lab=0}
C {isource.sym} -50 210 0 0 {name=I1 value=100u}
C {symbols/pfet_03v3.sym} -30 50 0 1 {name=M3
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 120 50 0 0 {name=M4
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {vdd.sym} -50 -50 0 0 {name=l9 lab=VDD}
C {vdd.sym} 140 -50 0 0 {name=l11 lab=VDD}
C {vcvs.sym} 320 850 0 1 {name=E1 value=1}
C {gnd.sym} 320 880 0 0 {name=l6 lab=0
value=1}
C {gnd.sym} 390 890 0 0 {name=l12 lab=0
value=1}
C {lab_wire.sym} -370 70 0 0 {name=p3 sig_type=std_logic lab=VSWING}
C {lab_wire.sym} 410 830 0 1 {name=p4 sig_type=std_logic lab=VSWING
value=1}
C {vcvs.sym} 140 210 0 1 {name=E2 value=1}
C {gnd.sym} 140 240 0 0 {name=l13 lab=0
value=1}
C {gnd.sym} 210 250 0 0 {name=l14 lab=0
value=1}
C {lab_wire.sym} 230 190 0 1 {name=p5 sig_type=std_logic lab=VSWING
value=1}
C {symbols/nfet_03v3.sym} 790 860 0 0 {name=M5
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 810 940 0 0 {name=l10 lab=0}
C {symbols/nfet_03v3.sym} 640 860 0 1 {name=M6
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 620 940 0 1 {name=l15 lab=0}
C {isource.sym} 620 620 0 0 {name=I2 value=100u}
C {vdd.sym} 620 540 0 0 {name=l16 lab=VDD}
C {lab_wire.sym} 730 860 0 0 {name=p6 sig_type=std_logic lab=VBN2}
C {lab_wire.sym} 890 650 0 0 {name=p7 sig_type=std_logic lab=VON2}
C {gnd.sym} 620 240 0 1 {name=l17 lab=0}
C {isource.sym} 620 210 0 0 {name=I3 value=100u}
C {symbols/pfet_03v3.sym} 640 0 0 1 {name=M7
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 790 0 0 0 {name=M8
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {vdd.sym} 620 -100 0 0 {name=l18 lab=VDD}
C {vdd.sym} 810 -100 0 0 {name=l19 lab=VDD}
C {vcvs.sym} 990 730 0 1 {name=E3 value=1}
C {gnd.sym} 990 760 0 0 {name=l20 lab=0
value=1}
C {gnd.sym} 1060 770 0 0 {name=l21 lab=0
value=1}
C {lab_wire.sym} 1080 710 0 1 {name=p8 sig_type=std_logic lab=VSWING
value=1}
C {vcvs.sym} 810 210 0 1 {name=E4 value=1}
C {gnd.sym} 810 240 0 0 {name=l22 lab=0
value=1}
C {gnd.sym} 880 250 0 0 {name=l23 lab=0
value=1}
C {lab_wire.sym} 900 190 0 1 {name=p9 sig_type=std_logic lab=VSWING
value=1}
C {symbols/nfet_03v3.sym} 790 740 0 0 {name=M9
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} 640 740 0 1 {name=M10
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 730 740 0 0 {name=p10 sig_type=std_logic lab=VCN2}
C {symbols/pfet_03v3.sym} 640 100 0 1 {name=M11
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 790 100 0 0 {name=M12
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 80 50 0 0 {name=p11 sig_type=std_logic lab=VBP1}
C {lab_wire.sym} 740 0 0 0 {name=p12 sig_type=std_logic lab=VBP2}
C {lab_wire.sym} 740 100 0 0 {name=p13 sig_type=std_logic lab=VCP2}
C {lab_wire.sym} 810 800 0 0 {name=p14 sig_type=std_logic lab=VXN2}
C {lab_wire.sym} 810 50 0 0 {name=p15 sig_type=std_logic lab=VXP2}
C {symbols/nfet_03v3.sym} 1690 860 0 0 {name=M13
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 1710 940 0 0 {name=l24 lab=0}
C {symbols/nfet_03v3.sym} 1540 860 0 1 {name=M14
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 1520 940 0 1 {name=l25 lab=0}
C {isource.sym} 1520 620 0 0 {name=I4 value=100u}
C {vdd.sym} 1520 540 0 0 {name=l26 lab=VDD}
C {lab_wire.sym} 1650 860 0 0 {name=p16 sig_type=std_logic lab=VBN3}
C {lab_wire.sym} 1790 650 0 0 {name=p17 sig_type=std_logic lab=VON3}
C {gnd.sym} 1520 240 0 1 {name=l27 lab=0}
C {isource.sym} 1520 210 0 0 {name=I5 value=100u}
C {symbols/pfet_03v3.sym} 1540 0 0 1 {name=M15
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 1690 0 0 0 {name=M16
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {vdd.sym} 1520 -100 0 0 {name=l28 lab=VDD}
C {vdd.sym} 1710 -100 0 0 {name=l29 lab=VDD}
C {vcvs.sym} 1890 730 0 1 {name=E5 value=1}
C {gnd.sym} 1890 760 0 0 {name=l30 lab=0
value=1}
C {gnd.sym} 1960 770 0 0 {name=l31 lab=0
value=1}
C {lab_wire.sym} 1980 710 0 1 {name=p18 sig_type=std_logic lab=VSWING
value=1}
C {vcvs.sym} 1710 210 0 1 {name=E6 value=1}
C {gnd.sym} 1710 240 0 0 {name=l32 lab=0
value=1}
C {gnd.sym} 1780 250 0 0 {name=l33 lab=0
value=1}
C {lab_wire.sym} 1800 190 0 1 {name=p19 sig_type=std_logic lab=VSWING
value=1}
C {symbols/nfet_03v3.sym} 1690 740 0 0 {name=M17
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} 1540 740 0 1 {name=M18
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 1650 740 0 0 {name=p20 sig_type=std_logic lab=VCN3}
C {symbols/pfet_03v3.sym} 1540 100 0 1 {name=M19
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/pfet_03v3.sym} 1690 100 0 0 {name=M20
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 1640 0 0 0 {name=p21 sig_type=std_logic lab=VBP3}
C {lab_wire.sym} 1640 100 0 0 {name=p22 sig_type=std_logic lab=VCP3}
C {lab_wire.sym} 1710 800 0 0 {name=p23 sig_type=std_logic lab=VXN3}
C {lab_wire.sym} 1710 50 0 0 {name=p24 sig_type=std_logic lab=VXP3}
C {gnd.sym} 1320 240 0 1 {name=l34 lab=0}
C {isource.sym} 1320 210 0 0 {name=I6 value=100u}
C {symbols/pfet_03v3.sym} 1340 50 0 1 {name=M21
L=0.4u
W=12.9u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {vdd.sym} 1320 -100 0 0 {name=l35 lab=VDD}
C {symbols/nfet_03v3.sym} 1340 800 0 1 {name=M22
L=0.6u
W=6.6u
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
C {gnd.sym} 1320 940 0 1 {name=l36 lab=0}
C {isource.sym} 1320 620 0 0 {name=I7 value=100u}
C {vdd.sym} 1320 540 0 0 {name=l37 lab=VDD}
C {symbols/nfet_03v3.sym} 1340 880 0 1 {name=M23
L=0.6u
W=6.6u
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
C {symbols/pfet_03v3.sym} 1340 -40 0 1 {name=M24
L=0.4u
W=12.9u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {symbols/nfet_03v3.sym} 130 1530 0 0 {name=M25
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 150 1610 0 0 {name=l38 lab=0}
C {symbols/pfet_03v3.sym} 130 1310 0 0 {name=M26
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {vdd.sym} 150 1210 0 0 {name=l39 lab=VDD}
C {lab_wire.sym} 70 1530 0 0 {name=p25 sig_type=std_logic lab=VBN1}
C {lab_wire.sym} 70 1310 0 0 {name=p26 sig_type=std_logic lab=VBP1}
C {lab_wire.sym} 150 1470 0 1 {name=p27 sig_type=std_logic lab=VSimple}
C {vsource.sym} 150 1400 0 0 {name=V2 value=0 savecurrent=false}
C {symbols/nfet_03v3.sym} 730 1710 0 0 {name=M27
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 750 1790 0 0 {name=l40 lab=0}
C {symbols/nfet_03v3.sym} 730 1590 0 0 {name=M28
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 750 1650 0 0 {name=p28 sig_type=std_logic lab=VN02}
C {symbols/pfet_03v3.sym} 730 1270 0 0 {name=M29
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {vdd.sym} 750 1170 0 0 {name=l41 lab=VDD}
C {symbols/pfet_03v3.sym} 730 1370 0 0 {name=M30
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 750 1320 0 0 {name=p31 sig_type=std_logic lab=VN01}
C {lab_wire.sym} 750 1530 0 1 {name=p32 sig_type=std_logic lab=VCascode}
C {vsource.sym} 750 1460 0 0 {name=V3 value=0 savecurrent=false}
C {lab_wire.sym} 670 1270 0 0 {name=p29 sig_type=std_logic lab=VBP2}
C {lab_wire.sym} 670 1370 0 0 {name=p30 sig_type=std_logic lab=VCP2}
C {lab_wire.sym} 670 1710 0 0 {name=p33 sig_type=std_logic lab=VBN2}
C {lab_wire.sym} 670 1590 0 0 {name=p34 sig_type=std_logic lab=VCN2}
C {symbols/nfet_03v3.sym} 1550 1730 0 0 {name=M31
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {gnd.sym} 1570 1810 0 0 {name=l42 lab=0}
C {symbols/nfet_03v3.sym} 1550 1610 0 0 {name=M32
L=0.6u
W=2.7u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 1570 1670 0 0 {name=p35 sig_type=std_logic lab=VN04}
C {symbols/pfet_03v3.sym} 1550 1290 0 0 {name=M33
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {vdd.sym} 1570 1190 0 0 {name=l43 lab=VDD}
C {symbols/pfet_03v3.sym} 1550 1390 0 0 {name=M34
L=0.4u
W=6.1u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {lab_wire.sym} 1570 1340 0 0 {name=p36 sig_type=std_logic lab=VN03}
C {lab_wire.sym} 1570 1550 0 1 {name=p37 sig_type=std_logic lab=Vlowvolt}
C {vsource.sym} 1570 1480 0 0 {name=V4 value=0 savecurrent=false}
C {lab_wire.sym} 1490 1290 0 0 {name=p38 sig_type=std_logic lab=VBP3}
C {lab_wire.sym} 1490 1390 0 0 {name=p39 sig_type=std_logic lab=VCP3}
C {lab_wire.sym} 1490 1730 0 0 {name=p40 sig_type=std_logic lab=VBN3}
C {lab_wire.sym} 1490 1610 0 0 {name=p41 sig_type=std_logic lab=VCN3}
