# PAVE
PArkes Vega Epoch (PAVE) - is ground, flight and launch software in early development for model rocketry.

The software in this project has been developed over four years, both before and during my formal programming education. As such, there is a noticable fluctuation in the quality of my code and the practices I followed. Please keep this in mind if you're looking to adapt any of my code! :)

# Outline of PAVE:

Parkes Ground Software:
 - user interface for the PAVE system
 - live telemetry downlink over radio (HC-12)
 - launch control (via Epoch)
 - configuration and testing of all three systems
 - error handling and display for all three systems

Vega Flight Software:
 - flight data recording
 - live data downlink over radio
 - flight comms links
 
Epoch Launch Software:
 - commands ignition of up to three engines simultaneously
 - controls launch clamps, LEDS, and other launchpad functionality
 - receives launch commands from Parkes wirelessly, negates need for wires
 - serves as secondary antenna, closer to launchpad


Codebases are shared between systems where possible, with system management and radio communication protocols identical between the three.

# Hardware Implementation
- Parkes is run on a Raspberry Pi 3, with LCD and buttons/switches/LEDs for interaction.
- Vega is run on a Raspberry Pi Zero, with an MPU6050 for gyro/accel, BMP180 for alt., and Pi Camera for video.
- Epoch is run on a Raspberry Pi Zero, with three 3.3V Gravity Relays for ignition control and red and green lamps for status updates
- All three computers communicate using HC-12 radios.


# Dependencies
- filterpy
- Adafruit_BMP



