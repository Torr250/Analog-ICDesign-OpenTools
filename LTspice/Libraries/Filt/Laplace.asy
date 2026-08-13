Version 4
SymbolType BLOCK
LINE Normal -40 0 -44 -4
LINE Normal -44 4 -40 0
LINE Normal -48 -4 -44 -4
LINE Normal -44 4 -48 4
LINE Normal -6 8 -2 -8
LINE Normal 0 11 -7 6
RECTANGLE Normal 48 32 -48 -32
ARC Normal -2 -13 4 -2 5 0 -1 -8
ARC Normal -6 5 -14 10 -7 5 -6 8
ARC Normal -3 3 7 11 1 9 6 7
ARC Normal -10 -16 4 1 -2 -14 7 0
WINDOW 0 -48 -40 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel Laplace
SYMATTR Value2 f=1 g=4
SYMATTR SpiceLine a2=1 a1=2 a0=10
SYMATTR SpiceLine2 b2=2 b1=1 b0=3
SYMATTR Description 2nd order Laplace transform, 20dB/dec only.
SYMATTR ModelFile filt.sub
PIN -48 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 48 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
