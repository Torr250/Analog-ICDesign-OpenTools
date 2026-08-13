Version 4
SymbolType CELL
LINE Normal -44 -36 -48 -36
LINE Normal -40 -32 -44 -36
LINE Normal -44 -28 -40 -32
LINE Normal -48 -28 -44 -28
LINE Normal -44 -4 -48 -4
LINE Normal -40 0 -44 -4
LINE Normal -44 4 -40 0
LINE Normal -48 4 -44 4
LINE Normal -44 28 -48 28
LINE Normal -40 32 -44 28
LINE Normal -44 36 -40 32
LINE Normal -48 36 -44 36
RECTANGLE Normal 64 48 -48 -40
WINDOW 38 9 4 Center 2
SYMATTR SpiceModel abc/AB0
SYMATTR Prefix x
SYMATTR Description Clarke and Park transformation matrices ( 3 <-> 3 and 2 <-> 2 quadrature), symmetrical components transformation and reverse. Select the desired function from the drop-down menu. {sq} amplitude(0) or power(1) invariant matrix. {f} [Hz] frequency (abc<>120 only).
SYMATTR ModelFile transforms.sub
SYMATTR SpiceLine sq=1
SYMATTR SpiceLine2 f=50
PIN -48 -32 NONE 8
PINATTR PinName in1
PINATTR SpiceOrder 1
PIN -48 0 NONE 8
PINATTR PinName in2
PINATTR SpiceOrder 2
PIN -48 32 NONE 8
PINATTR PinName in3
PINATTR SpiceOrder 3
PIN 64 -32 NONE 8
PINATTR PinName out1
PINATTR SpiceOrder 4
PIN 64 0 NONE 8
PINATTR PinName out2
PINATTR SpiceOrder 5
PIN 64 32 NONE 8
PINATTR PinName out3
PINATTR SpiceOrder 6
PIN -16 48 BOTTOM 1
PINATTR PinName wt
PINATTR SpiceOrder 7
