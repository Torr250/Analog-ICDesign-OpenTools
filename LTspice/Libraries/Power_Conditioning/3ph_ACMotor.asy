Version 4
SymbolType BLOCK
LINE Normal -32 32 -48 32
LINE Normal -22 23 -32 32
LINE Normal -32 -32 -48 -32
LINE Normal -22 -23 -32 -32
LINE Normal -32 0 -48 0
CIRCLE Normal 32 32 -32 -32
CIRCLE Normal 24 24 -24 -24
TEXT 0 0 Bottom 2 M
TEXT 0 0 Top 2 3~
TEXT -6 38 Right 2 N
WINDOW 0 -24 -48 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel 3ph_ACMotor
SYMATTR Description {Zp} nr. of poles, {Lm} [H] magn. ind., {Lr/Ls} [H] rotor/stator parasitic ind., {Rf} [Ohm] iron losses, {Rr/Rs} rotor/stator res.. For auto calculation, set those to 0 and use {Pn} [W] shaft power, {fn} [Hz] working freq., {Vn} [V] nominal voltage, {eff} efficiency, {phi} cos(phi), {DY} delta(0) or wye(1), and {slip}.
SYMATTR ModelFile pwr.sub
SYMATTR SpiceLine Pn=1.1k fn=50 Vn=400 eff=0.76 phi=0.77 slip=30m
SYMATTR Value2 Zp=2 J=2.1m DY=1
SYMATTR SpiceLine2 Lm=350.15m Ls=26.43m Lr=18.8m Rf=2k Rs=7.5 Rr=5.5
PIN -48 -32 BOTTOM 0
PINATTR PinName a
PINATTR SpiceOrder 1
PIN -48 0 BOTTOM 0
PINATTR PinName b
PINATTR SpiceOrder 2
PIN -48 32 BOTTOM 0
PINATTR PinName c
PINATTR SpiceOrder 3
PIN 0 32 NONE 8
PINATTR PinName N
PINATTR SpiceOrder 4
PIN 48 16 RIGHT 5
PINATTR PinName W
PINATTR SpiceOrder 5
PIN 48 -16 RIGHT 5
PINATTR PinName J
PINATTR SpiceOrder 6
