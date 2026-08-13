Version 4
SymbolType BLOCK
RECTANGLE Normal 48 24 -48 -24
TEXT -48 16 Left 2 f
TEXT 0 0 Center 2 AGC
WINDOW 0 -47 -32 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel AGC
SYMATTR SpiceLine f=1k min=0.1 filt=2
SYMATTR Description Automatic gain control, unity-gain output. {f} [Hz] - working frequency, anything connected at pin 'FREQ' overrides it, {min} [V] - lower than the minumum estimated gain (to avoid division by zero), can be zero, {filt} selectes between moving average filtering (1) or Bessel (2).
SYMATTR ModelFile filt.sub
PIN -48 -16 LEFT 1
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 48 -16 RIGHT 1
PINATTR PinName out
PINATTR SpiceOrder 2
PIN 48 16 RIGHT 1
PINATTR PinName gain
PINATTR SpiceOrder 3
PIN -48 16 NONE 1
PINATTR PinName freq
PINATTR SpiceOrder 4
