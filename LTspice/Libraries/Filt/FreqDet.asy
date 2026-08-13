Version 4
SymbolType CELL
LINE Normal -32 24 16 24
LINE Normal -32 -25 -32 24
LINE Normal -32 -25 16 -25
LINE Normal -2 8 1 -5
LINE Normal 2 0 -2 0
LINE Normal 16 -25 32 0
LINE Normal 32 0 16 24
ARC Normal 1 -8 6 2 6 -4 1 -4
TEXT -32 -16 Left 2 +
TEXT -32 16 Left 2 -
WINDOW 0 -32 -32 Left 2
SYMATTR SpiceLine limit=1m gain=1
SYMATTR Prefix x
SYMATTR SpiceModel FreqDet
SYMATTR Description Simple frequency detector. {limit} is an estimate of the lowest time period to avoid division by zero, can be null, {gain} adjusts input signal level (if too high/low).
SYMATTR ModelFile filt.sub
PIN -32 -16 NONE 3
PINATTR PinName 1
PINATTR SpiceOrder 1
PIN -32 16 NONE 3
PINATTR PinName 2
PINATTR SpiceOrder 2
PIN 32 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 3
