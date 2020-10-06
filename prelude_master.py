#pls
'''
    ==========================================================
    Prelude Launch Software, version 0.0
    Copyright (C) 2020 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    ==========================================================
'''

import time
import math
import serial
import RPi.GPIO as GPIO

prelude_version = 0.0
receiving_command = True

# GPIO setup
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)


# System functions
def duration():
    """ Returns current change in time"""
    return format(time.time() - init_time, '.2f')

def file_append(target_file, data):
    # File appending tool, imported from VFS 0.3
    opened_file = open(target_file, "a")
    opened_file.write(data + "\n")
    opened_file.close()

def file_init(target_file, title):
    # File creation tool, imported from VFS 0.3
    top_line = f"========== {title} ==========\n"
    bottom_line = "=" * (len(top_line)-1) + "\n"
    new_file = open(target_file, "w")
    new_file.write(top_line)
    new_file.write("PRELUDE v" + str(prelude_version)+"\n")
    new_file.write(bottom_line)
    new_file.write(" \n")
    new_file.close()

def flight_log_unload(flight_log, done=True):
    # VFS Flight Log Unloader Tool
    flight_log_title = "prelude_flightlog.txt"
    file_init(flight_log_title, "PRELUDE FLIGHT LOG")
    log_file = open(flight_log_title, "a")

    for tuple in flight_log:
        log, timestamp = tuple
        log_file.write(f"- {timestamp} : {log}\n")

    if done:
        log_file.write("END OF LOG\n")
    log_file.close()

def flight_logger(event, time):
    global flight_log
    new_log = (event, time)

    flight_log.append(new_log)

# Comms Functions
def open_port():
    global prelude_radio
    # Opens the default port for Vega transceiver
    prelude_radio = serial.Serial(
        port = "/dev/serial0",
        baudrate = 9600,
        parity = serial.PARITY_NONE,
        stopbits = serial.STOPBITS_ONE,
        bytesize = serial.EIGHTBITS,

        # You might need a timeout here if it doesn't work, try a timeout of 1 sec
        )
def send(vamp):
    # Sends command over radio
    try:
        v, a, m, p = vamp
    except:
        error("E310")
    command = "v"+str(v)+"_a"+str(a)+"_m"+str(m)+"_p"+str(p)+"\n"
    prelude_radio.write(command.encode())

def receive():
    # Listens for a vamp from Vega. Simples
    data = prelude_radio.read_until()
    to_return = data
    to_return = to_return.decode()
    return to_return


def vamp_destruct(vamp):
    vamp_decom = []
    for element in vamp.split("_"):
        vamp_decom.append(element[1:])

    try:
        v, a, m, p = vamp_decom
    except:
        error("E120")
    vamp = (int(v), int(a), int(m), int(p))


# STARTUP
init_time = time.time()
flight_logger("prelude launch software - startup", duration())
flight_logger("initialising pls - verison: " + str(prelude_version), duration())
# Initialise prelude_radio
open_port()
time.sleep(1)
flight_logger("port open", duration())

command_dict = {
    0 : arm,
    2 : force_launch,
    3 : demo_loop,
    4 : compile_logs,
    7 : receive_config,
    8 : heartbeat_init

}


while receiving_command:
    flight_logger("RECEIVING COMMAND...", duration())

    new_command = vamp_destruct(receive())
    flight_logger("COMMAND: " + str(new_command), duration())

    target_program = new_command[2]
    if __name__ == "__main__":
        try:
            command_dict[target_program]()
        except KeyboardInterrupt:
            flight_logger("KeyboardInterrupt detected", duration())
            flight_logger("port closed", duration())
            compile_logs()



      # do noth
