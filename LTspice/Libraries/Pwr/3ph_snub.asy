Version 4
SymbolType BLOCK
LINE Normal 8 -20 -8 -20
LINE Normal 8 -16 -8 -16
LINE Normal 4 -7 -4 -7
LINE Normal 4 18 4 -7
LINE Normal -4 18 4 18
LINE Normal -4 -7 -4 18
LINE Normal 0 -7 0 -16
LINE Normal 0 32 0 18
LINE Normal 0 -20 0 -32
RECTANGLE Normal 24 32 -23 -32
WINDOW 0 28 27 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel 3ph_snub
SYMATTR SpiceLine R=100 C=1n
SYMATTR Description Three-phase series RC snubber.
SYMATTR ModelFile pwr.sub
PIN -16 -32 NONE 8
PINATTR PinName a
PINATTR SpiceOrder 1
PIN 0 -32 NONE 8
PINATTR PinName b
PINATTR SpiceOrder 2
PIN 16 -32 NONE 8
PINATTR PinName c
PINATTR SpiceOrder 3
PIN 0 32 NONE 8
PINATTR PinName n
PINATTR SpiceOrder 4
