# pave
Parkes Vega - or PAVE - is flight software in early development for avionics systems. 
Short term goals include:
  - Flight data recording
  - Avionics data logging
  
# outline of PAVE:

Parkes Ground Software:
 - user interface for the PAVE system
 - live telemetry downlink over radio
 - launch control
 - configuration of all involved systems
 - error handling and display

Vega Flight Software:
 - flight data recording
 - live data downlink over radio
 - flight comms links
 
Prelude Launch Software:
 - commands ignition of up to three engines simultaneously
 - controls launch clamps, LEDS, and other launchpad functionality
 - receives launch commands from Parkes wirelessly, negates need for wires
 - serves as secondary antenna, closer to launchpad

Codebases are shared between systems where possible, with system management and radio communication protocols identical between the three.

Repl.it -> [![Run on Repl.it](https://repl.it/badge/github/jackwoodman/vega)](https://repl.it/github/jackwoodman/vega)
