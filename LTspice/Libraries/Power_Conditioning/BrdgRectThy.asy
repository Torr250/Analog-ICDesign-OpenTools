Version 4
SymbolType CELL
LINE Normal 4 9 -18 9
LINE Normal -7 -7 4 9
LINE Normal -18 9 -3 -14
LINE Normal -7 -23 -7 24
LINE Normal 4 -7 -18 -7
LINE Normal 6 -14 -3 -14
RECTANGLE Normal 32 64 -48 -41
WINDOW 0 -48 -48 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel BrdgRectThy
SYMATTR SpiceLine Ron=100m Roff=10meg Vser=1
SYMATTR SpiceLine2 f=50 phi=0 ang=-pi/5 lvl=1
SYMATTR ModelFile pwr.sub
SYMATTR Description Thyristor bridge rectifier. For internal, fixed angle {ang} [rad], specify {f} [Hz] and {phi} [rad]. {Ron/Roff/Vser} LTspice's SW specific, _enable/disable at pin '_EN' (internal pull-down), angle control at the BUS pin 'S[1:6]' -- MUST be named as a 6-bus
PIN -48 -32 NONE 8
PINATTR PinName A
PINATTR SpiceOrder 1
PIN -48 0 NONE 8
PINATTR PinName B
PINATTR SpiceOrder 2
PIN -48 32 NONE 8
PINATTR PinName C
PINATTR SpiceOrder 3
PIN 32 -32 RIGHT 1
PINATTR PinName +
PINATTR SpiceOrder 4
PIN 32 32 RIGHT 1
PINATTR PinName -
PINATTR SpiceOrder 5
PIN -32 64 VLEFT 1
PINATTR PinName s[1:6]
PINATTR SpiceOrder 6
PIN 16 64 VLEFT 1
PINATTR PinName _EN
PINATTR SpiceOrder 7
