Version 4
SymbolType CELL
LINE Normal -24 0 -32 0
LINE Normal 24 0 48 0
LINE Normal 0 -24 0 -32
LINE Normal -17 -17 -32 -32
LINE Normal -32 32 -17 17
LINE Normal 0 32 0 24
CIRCLE Normal 24 24 -24 -24
TEXT 6 -32 Left 2 a
TEXT -26 -32 Left 2 b
TEXT -32 0 Top 2 c
TEXT -26 32 Left 2 d
TEXT 6 32 Left 2 e
WINDOW 38 32 16 Left 2
WINDOW 0 32 -16 Left 2
SYMATTR SpiceModel +++++
SYMATTR Prefix x
SYMATTR Description 5 input sum/difference, ground unused ones. Any combination possible (except nulls).
SYMATTR ModelFile mathfunc5.sub
PIN 0 -32 NONE 8
PINATTR PinName a
PINATTR SpiceOrder 1
PIN -32 -32 NONE 8
PINATTR PinName b
PINATTR SpiceOrder 2
PIN -32 0 NONE 8
PINATTR PinName c
PINATTR SpiceOrder 3
PIN -32 32 NONE 8
PINATTR PinName d
PINATTR SpiceOrder 4
PIN 0 32 NONE 8
PINATTR PinName e
PINATTR SpiceOrder 5
PIN 48 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 6
