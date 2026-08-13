Version 4
SymbolType BLOCK
LINE Normal -40 0 -48 -8
LINE Normal -48 8 -40 0
LINE Normal 32 -24 -32 24 2
LINE Normal 7 0 -7 0
LINE Normal -7 10 -7 0
LINE Normal -7 10 -21 10
LINE Normal -21 20 -21 10
LINE Normal -21 20 -35 20
LINE Normal 21 -10 21 -20
LINE Normal 21 -10 7 -10
LINE Normal 7 0 7 -10
LINE Normal 35 -20 21 -20
RECTANGLE Normal 48 32 -48 -32
WINDOW 0 -48 -42 Left 2
SYMATTR Prefix X
SYMATTR SpiceLine N=16 VinH=32767 VinL=-32768 type=1
SYMATTR Description 16bit quantizer. {N} bits conversion, {VinH,VinL} input levels, type=<1:4> means, in order, int() (default), floor(), ceil(), and round().
SYMATTR SpiceModel Quant16
SYMATTR ModelFile 0101.sub
PIN -48 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 48 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
