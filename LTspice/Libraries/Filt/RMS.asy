Version 4
SymbolType BLOCK
LINE Normal -24 0 -32 -8
LINE Normal -32 8 -24 0
RECTANGLE Normal 32 16 -32 -16
TEXT 0 0 Center 2 RMS
SYMATTR Prefix x
SYMATTR SpiceModel RMS
SYMATTR SpiceLine fc=250 b0=1 b1=3
SYMATTR Description Frequency-independent RMS value. {fc} sets the corner frequency for the filter, {b0, b1} set the filter's denominator terms (default Bessel: <3,3>).
SYMATTR ModelFile filt.sub
PIN -32 0 NONE 0
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 32 0 NONE 0
PINATTR PinName out
PINATTR SpiceOrder 2
