Version 4
SymbolType CELL
LINE Normal 32 14 -28 14
LINE Normal 29 16 32 14
LINE Normal 32 14 29 12
LINE Normal -26 -30 -26 16
LINE Normal -24 -27 -26 -30
LINE Normal -26 -30 -28 -27
LINE Normal 28 26 29 20
LINE Normal 30 23 28 23
LINE Normal 42 -26 48 -32
LINE Normal 48 -32 42 -38
LINE Normal 48 0 42 -6
LINE Normal 42 6 48 0
LINE Normal 42 38 48 32
LINE Normal 48 32 42 26
LINE Normal -19 -30 -19 14
LINE Normal -18 -30 -19 -30
LINE Normal -18 14 -18 -30
LINE Normal -13 -25 -13 14
LINE Normal -12 -25 -13 -25
LINE Normal -12 14 -12 -25
LINE Normal -7 -16 -7 14
LINE Normal -6 -16 -7 -16
LINE Normal -6 14 -6 -16
LINE Normal -1 -5 -1 14
LINE Normal 0 -5 -1 -5
LINE Normal 0 14 0 -5
LINE Normal 5 6 5 14
LINE Normal 6 6 5 6
LINE Normal 6 14 6 6
LINE Normal 11 11 11 14
LINE Normal 12 11 11 11
LINE Normal 12 14 12 11
LINE Normal 17 9 17 14
LINE Normal 18 9 17 9
LINE Normal 18 14 18 9
LINE Normal 23 12 23 14
LINE Normal 24 12 23 12
LINE Normal 24 14 24 12
RECTANGLE Normal 48 48 -48 -48
ARC Normal 29 19 31 21 31 20 29 20
WINDOW 0 -48 -55 Left 2
SYMATTR SpiceLine h1=0 h2=0 h3=0 phi1=0 phi2=0 phi3=0
SYMATTR SpiceLine2 a=0 b=0 c=0 d=0 e=0 p=1 q=0 xp=1 xq=1 ma=0 mb=0
SYMATTR Prefix x
SYMATTR SpiceModel 3ph_gen
SYMATTR Description Three-phase, voltage/current harmonics generator +. See pwr.sub/3ph_gen for details.
SYMATTR ModelFile pwr.sub
SYMATTR Value2 dc1=0 dc2=0 dc3=0 A1=1 A2=1 A3=1
SYMATTR Value sym=1 f=50 amp=325 phi=0 Ro=1 N=-51
PIN 48 -32 NONE 3
PINATTR PinName 1
PINATTR SpiceOrder 1
PIN 48 0 NONE 3
PINATTR PinName 2
PINATTR SpiceOrder 2
PIN 48 32 NONE 3
PINATTR PinName 3
PINATTR SpiceOrder 3
PIN -48 0 VTOP 1
PINATTR PinName NUL
PINATTR SpiceOrder 4
PIN -32 48 BOTTOM 1
PINATTR PinName FM
PINATTR SpiceOrder 5
PIN 0 48 BOTTOM 1
PINATTR PinName AM
PINATTR SpiceOrder 6
PIN 32 48 BOTTOM 1
PINATTR PinName PM
PINATTR SpiceOrder 7
