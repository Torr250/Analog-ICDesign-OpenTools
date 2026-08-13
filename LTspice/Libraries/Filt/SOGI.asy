Version 4
SymbolType BLOCK
LINE Normal -56 -16 -60 -20
LINE Normal -60 -12 -56 -16
LINE Normal 18 -8 18 -24
LINE Normal 34 -16 18 -8
LINE Normal 18 -24 34 -16
LINE Normal 35 24 35 8
LINE Normal 19 16 35 24
LINE Normal 35 8 19 16
LINE Normal -42 -24 -45 -24
LINE Normal -20 -8 -23 -8
LINE Normal -47 -16 -54 -16
LINE Normal -25 -16 -33 -16
LINE Normal -3 -16 -11 -16
LINE Normal 18 -16 11 -16
LINE Normal 45 -16 34 -16
LINE Normal 39 -28 39 16
LINE Normal -10 -28 39 -28
LINE Normal 35 16 39 16
LINE Normal 11 16 19 16
LINE Normal -24 16 -3 16
LINE Normal -40 -28 -10 -28
LINE Normal -40 -23 -40 -28
LINE Normal -18 16 -18 -9
LINE Normal 4 9 4 -9
LINE Normal 15 0 4 0
LINE Normal 9 -11 -1 -21
LINE Normal -1 -11 9 -21
LINE Normal 9 21 -1 11
LINE Normal -1 21 9 11
LINE Normal -60 -20 -64 -20
LINE Normal -64 -12 -60 -12
RECTANGLE Normal 64 32 -64 -32
CIRCLE Normal -33 -9 -47 -23
CIRCLE Normal 40 -15 38 -17
CIRCLE Normal -19 17 -17 15
CIRCLE Normal 3 1 5 -1
CIRCLE Normal -11 -9 -25 -23
CIRCLE Normal 11 -9 -3 -23
CIRCLE Normal 11 23 -3 9
ARC Normal 22 -20 24 -12 24 -19 22 -16
ARC Normal 22 -12 20 -20 20 -13 22 -16
ARC Normal 31 12 33 20 33 13 31 16
ARC Normal 31 20 29 12 29 19 31 16
WINDOW 0 -64 -43 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel SOGI
SYMATTR SpiceLine f=50 ke={sqrt(2)}
SYMATTR Description Second order generalized integrator, adaptive. {f} [Hz] is the frequency, {ke} is the quality factor set by the error amplifier.
SYMATTR ModelFile filt.sub
PIN -64 -16 NONE 0
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 64 -16 RIGHT 0
PINATTR PinName v
PINATTR SpiceOrder 2
PIN 64 16 RIGHT 0
PINATTR PinName _v
PINATTR SpiceOrder 3
PIN -64 16 LEFT 0
PINATTR PinName f
PINATTR SpiceOrder 4
