Version 4
SymbolType BLOCK
RECTANGLE Normal 32 56 -32 -72
TEXT 0 -5 Center 2 MUX
SYMATTR Prefix x
SYMATTR SpiceModel MUX
SYMATTR Description A simple analog multiplexer. Output is V(1) if V(ctl)==1, V(2) if V(ctl)==2, ..., anything below or above the range means zero output.
SYMATTR ModelFile filt.sub
PIN -32 -64 LEFT 1
PINATTR PinName 1
PINATTR SpiceOrder 1
PIN -32 -48 LEFT 1
PINATTR PinName 2
PINATTR SpiceOrder 2
PIN -32 -32 LEFT 1
PINATTR PinName 3
PINATTR SpiceOrder 3
PIN -32 -16 LEFT 1
PINATTR PinName 4
PINATTR SpiceOrder 4
PIN -32 0 LEFT 1
PINATTR PinName 5
PINATTR SpiceOrder 5
PIN -32 16 LEFT 1
PINATTR PinName 6
PINATTR SpiceOrder 6
PIN -32 32 LEFT 1
PINATTR PinName 7
PINATTR SpiceOrder 7
PIN -32 48 LEFT 1
PINATTR PinName 8
PINATTR SpiceOrder 8
PIN 32 -48 RIGHT 1
PINATTR PinName out
PINATTR SpiceOrder 9
PIN 32 32 RIGHT 1
PINATTR PinName ctl
PINATTR SpiceOrder 10
