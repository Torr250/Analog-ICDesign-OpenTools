Version 4
SymbolType BLOCK
LINE Normal 23 3 11 3
LINE Normal 23 7 11 7
LINE Normal 17 -9 17 3
LINE Normal 7 -9 26 -9
LINE Normal -20 -9 -29 -9
LINE Normal 17 7 17 20
RECTANGLE Normal 32 48 -32 -48
ARC Normal -20 -14 -11 -4 -11 -9 -20 -9
ARC Normal -11 -14 -2 -4 -2 -9 -11 -9
ARC Normal -2 -14 7 -4 7 -9 -2 -9
WINDOW 0 -31 -55 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel 3ph_LC
SYMATTR SpiceLine L=1m C=1u
SYMATTR Description 3-phase lowpass LC, with or without null.
SYMATTR ModelFile pwr.sub
SYMATTR SpiceLine2 null=1 k=0
PIN -32 -32 NONE 8
PINATTR PinName 11
PINATTR SpiceOrder 1
PIN -32 0 NONE 8
PINATTR PinName 12
PINATTR SpiceOrder 2
PIN -32 32 NONE 8
PINATTR PinName 13
PINATTR SpiceOrder 3
PIN 32 -32 NONE 8
PINATTR PinName 21
PINATTR SpiceOrder 4
PIN 32 0 NONE 8
PINATTR PinName 22
PINATTR SpiceOrder 5
PIN 32 32 NONE 8
PINATTR PinName 23
PINATTR SpiceOrder 6
PIN 0 48 NONE 8
PINATTR PinName -1
PINATTR SpiceOrder 7
