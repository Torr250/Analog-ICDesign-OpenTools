Version 4
SymbolType CELL
LINE Normal -44 -4 -48 -4
LINE Normal -40 0 -44 -4
LINE Normal -44 4 -40 0
LINE Normal -48 4 -44 4
RECTANGLE Normal 48 24 -48 -24
WINDOW 0 -48 -32 Left 2
WINDOW 39 0 33 Center 2
WINDOW 38 0 0 Center 2
SYMATTR SpiceLine Kp=0 Ki=0 Kd=0
SYMATTR SpiceLine2 Ts=1m
SYMATTR Prefix x
SYMATTR SpiceModel PID
SYMATTR Description Universal PID controller, Kp+Ki/s+sKd. Any combination of {Kp}, {Ki} or {Kd} works for the analog version. Select {PIDd} model for the digital version where {Ts} [s] is the sampling time.
SYMATTR ModelFile filt.sub
PIN -48 0 NONE 8
PINATTR PinName in+
PINATTR SpiceOrder 1
PIN 48 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
