For some time now I saw that there aren't too many things related to power-conditioning, except for some PFCs, a grid-tied inverter and a few minor others, but none related to power-electronics, pq theory or grid synchronization, so I added some examples to try and fill up the gap a bit. These are some examples with application to this domain. The contents of the archive has, in no particular order, the following schematics:

- two shunt active power filters, pq theory, sine and power strategies;
- shunt active power filter, dq theory;
- shunt active power filter, pq/sine strategy, full schematic but with ideal blocks;
- universal power quality conditioner, dq theory for both shunt and series filters;
- simple passive reactive power compensation;
- positive sequence detectors, pq and dq, and filtering methods test case;
- phase-locked loop for grid-tied inverters;
- quadrature signal generator based on generalized integrators;
- three-phase, three-level modulation example;
- three-phase thyristor bridge rectifier;
- a small extra find.

The archive "Power_Conditioning.zip" is uploaded in: Files/Examples/Educational/Power_Conditioning/.

Not all examples are new, but they are all made by me, inspired by paragraphs from many floating papers online, passages from books, in general, whatever free documentation can be found that *is* free (for personal information, no selling products, etc).
All the schematics have PC_ in front of the name so they should be easier to spot. Also, all the files should be installed/extracted under the same directory (as they are now), without sub-folders; sadly, LTspice doesn't allow custom subfolder(s) to avoid cluttering. The schematics have .asc extension, the symbols .asy and the subcircuit files .sub; .plt files are optional and they contain the plot settings. Details about the custom models can be found at http://ltspice-goodies.comoj.com .

The examples are for educational/informational purposes only, not because I say so, but because they are based on the same informational-only flag.


Vlad


*** Updates:

- 2012.08.10	- added two space-vector modulation schematics: PWM and hysteresis.
- 2012.08.22	- added state-space modelling of an inverter's LCL output stage.
- 2012.08.25	- added virtual resistor damping.
- 2012.09.29	- added IIR filters to the filtering comparison schematic.
- 2012.09.29	- added symmetrical components faults.
- 2012.10.02	- added time-domain Fourier analysis.
		- added shunt active filter with FFT algorithm.
- 2013.01.19	- "Contents.txt" is no longer referred to, instead, the .sub files containing the subcircuits should be read.
- 2013.02.02	- Modified PC_Symmetrical_Components_Faults to include the new symmetrical components symbol.
- 2013.07.20	- Updated the symbols/libraries.
- 2014.04.15	- Update the symbols/libraries/schematics.

