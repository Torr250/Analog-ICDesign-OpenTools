Version 4
SymbolType CELL
LINE Normal -15 21 -23 21
LINE Normal 24 -22 16 -22
LINE Normal 16 -22 -15 21
LINE Normal -28 -4 -32 -4
LINE Normal -24 0 -28 -4
LINE Normal -28 4 -24 0
LINE Normal -32 4 -28 4
RECTANGLE Normal 32 32 -32 -32
WINDOW 39 0 48 Center 2
SYMATTR SpiceLine Min=-1 Max=1
SYMATTR Prefix x
SYMATTR SpiceModel LimExt
SYMATTR Description Limits the output voltage between predefined {Max} and {Min}. Anything connected to the external limit pins overrides internal settings.
SYMATTR ModelFile filt.sub
PIN -32 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 32 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
PIN 0 -32 NONE 8
PINATTR PinName Max
PINATTR SpiceOrder 3
PIN 0 32 NONE 8
PINATTR PinName Min
PINATTR SpiceOrder 4
