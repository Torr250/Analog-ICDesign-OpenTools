Version 4
SymbolType BLOCK
LINE Normal -32 10 -32 -22
LINE Normal 0 -6 -32 10
LINE Normal -32 -22 0 -6
LINE Normal 36 1 25 1
LINE Normal 25 3 36 3
LINE Normal 31 12 31 3
LINE Normal 34 12 28 12
LINE Normal 31 14 34 12
LINE Normal 28 12 31 14
LINE Normal 31 -6 31 1
LINE Normal 25 -6 50 -6
LINE Normal 0 -6 9 -6
LINE Normal -32 -16 -40 -16
LINE Normal -32 4 -36 4
LINE Normal -36 21 -36 4
LINE Normal 43 21 -36 21
LINE Normal 43 -6 43 21
RECTANGLE Normal 64 48 -64 -48
CIRCLE Normal 44 -5 42 -7
ARC Normal 9 -8 13 -4 13 -6 9 -6
ARC Normal 13 -8 17 -4 17 -6 13 -6
ARC Normal 17 -8 21 -4 21 -6 17 -6
ARC Normal 21 -8 25 -4 25 -6 21 -6
TEXT 62 -32 Right 2 +
TEXT 62 32 Right 2 -
SYMATTR Prefix x
SYMATTR SpiceModel UcD_block
SYMATTR Value Lf=33u Cf=680n
SYMATTR Value2 Cfd=220p Rser=1k Rpar=8k2 Ratt=1k8
SYMATTR SpiceLine Ron=100m Roff=10meg Vfwd=0.7 Vrev=1k
SYMATTR SpiceLine2 td=150n dt=50n
SYMATTR Description Full-bridge, non-inverting UcD amplifier, see pwr.sub for details.
SYMATTR ModelFile pwr.sub
PIN -64 -32 LEFT 0
PINATTR PinName in
PINATTR SpiceOrder 1
PIN -64 32 LEFT 0
PINATTR PinName fb
PINATTR SpiceOrder 2
PIN 64 -32 NONE 0
PINATTR PinName out+
PINATTR SpiceOrder 3
PIN 64 32 NONE 0
PINATTR PinName out-
PINATTR SpiceOrder 4
PIN 0 -48 TOP 0
PINATTR PinName Vcc
PINATTR SpiceOrder 5
PIN 0 48 BOTTOM 0
PINATTR PinName Vee
PINATTR SpiceOrder 6
