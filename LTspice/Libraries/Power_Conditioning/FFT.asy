Version 4
SymbolType CELL
RECTANGLE Normal 64 64 -64 -64
TEXT 64 -48 Right 2 a[0:31]
TEXT 64 -16 Right 2 b[1:31]
TEXT 64 16 Right 2 sin[1:31]
TEXT 64 48 Right 2 cos[1:31]
TEXT 0 0 Center 2 CFT
WINDOW 0 -64 -72 Left 2
SYMATTR SpiceModel CFT
SYMATTR Prefix x
SYMATTR Description Fourier Transform up to N=31; for more, see the .sub file. {f} [Hz] is the frequency. The outputs need bus naming, else they're hard or'ed.
SYMATTR SpiceLine f=50 N=31
SYMATTR ModelFile filt.sub
PIN -64 -48 LEFT 2
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 64 -48 NONE 8
PINATTR PinName a[0:31]
PINATTR SpiceOrder 2
PIN 64 -16 NONE 8
PINATTR PinName b[1:31]
PINATTR SpiceOrder 3
PIN 64 16 NONE 8
PINATTR PinName sin[1:31]
PINATTR SpiceOrder 4
PIN 64 48 NONE 8
PINATTR PinName cos[1:31]
PINATTR SpiceOrder 5
