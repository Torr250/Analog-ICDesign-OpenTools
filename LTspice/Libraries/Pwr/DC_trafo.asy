Version 4
SymbolType BLOCK
LINE Normal -16 -8 -16 -32
LINE Normal 0 32 0 0 2
LINE Normal 8 0 -8 0 2
LINE Normal -8 0 -4 -2 1
LINE Normal -4 2 -8 0 1
LINE Normal 8 0 4 -2 1
LINE Normal 4 2 8 0 1
LINE Normal 0 19 -3 24 1
LINE Normal 3 24 0 19 1
LINE Normal -16 32 -16 8
LINE Normal 16 -8 16 -32
LINE Normal 16 32 16 8
LINE Normal -21 -9 -21 -15
LINE Normal -24 -12 -18 -12
LINE Normal -24 11 -18 11
LINE Normal 21 -9 21 -15
LINE Normal 18 -12 24 -12
LINE Normal 18 11 24 11
CIRCLE Normal -8 8 -24 -8
CIRCLE Normal 24 8 8 -8
TEXT -16 -21 Left 2 1
TEXT 16 -21 Right 2 3
TEXT -16 22 Left 2 2
TEXT 16 22 Right 2 4
WINDOW 0 -16 -48 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel DC_trafo
SYMATTR SpiceLine Rin=1Meg Rout=1u d=0.5
SYMATTR Description DC trafo + duty cycle.
SYMATTR ModelFile pwr.sub
PIN -16 -32 NONE 2
PINATTR PinName 1
PINATTR SpiceOrder 1
PIN -16 32 NONE 2
PINATTR PinName 2
PINATTR SpiceOrder 2
PIN 16 -32 NONE 2
PINATTR PinName 3
PINATTR SpiceOrder 3
PIN 16 32 NONE 2
PINATTR PinName 4
PINATTR SpiceOrder 4
PIN 0 32 NONE 8
PINATTR PinName D
PINATTR SpiceOrder 5
