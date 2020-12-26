#els
'''
    ==========================================================
    Epoch Launch Software, version 0.1
    Copyright (C) 2020 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    * This program isn't nearly functional though so I don't
    * really know why you would want to use, distribute or
    * modify it.
    * You do you though.
    ==========================================================
'''

import time
import math
import serial
import RPi.GPIO as GPIO
from time import sleep

# Variables
epoch_version = 0.1
comp_id = 1
receiving_command = True
ready_fire = False

global error_log
global flight_log

error_log, flight_log = [], []

# Constants
IGNITION_DELAY = 5

# GPIO setup
ignitor_x = 11
ignitor_y = 13
ignitor_z = 15

x_power = 36
y_power = 38
z_power = 40

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

GPIO.setup(ignitor_x, GPIO.OUT)    # needs to be defined
GPIO.setup(ignitor_y, GPIO.OUT)    # needs to be defined
GPIO.setup(ignitor_z, GPIO.OUT)    # needs to be defined

GPIO.setup(x_power, GPIO.OUT)      # needs to be defined
GPIO.setup(y_power, GPIO.OUT)      # needs to be defined
GPIO.setup(z_power, GPIO.OUT)      # needs to be defined

GPIO.output(x_power, GPIO.HIGH)
GPIO.output(y_power, GPIO.HIGH)
GPIO.output(z_power, GPIO.HIGH)




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
    new_file.write("EPOCH v" + str(epoch_version)+"\n")
    new_file.write(bottom_line)
    new_file.write(" \n")
    new_file.close()

def flight_log_unload(flight_log, done=True):
    # VFS Flight Log Unloader Tool
    flight_log_title = "epoch_flightlog.txt"
    file_init(flight_log_title, "EPOCH FLIGHT LOG")
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
    global epoch_radio
    # Opens the default port for Vega transceiver
    epoch_radio = serial.Serial(
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
    epoch_radio.write(command.encode())

def receive():
    # Listens for a vamp from Vega. Simples
    data = epoch_radio.read_until()
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

"""==== EPOCH FUNCTIONS ===="""
def echo():
    # oof oof dsp_error_nonfatal
    # this doesn't work yet but is vital

    sleep(1)
    flight_logger("echo - active", duration())

    v, a, m, p = "00000", "0000", "2", "20000"
    command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
    epoch_radio.write(command.encode())
    sleep(1)

    flight_logger("echo - inactive", duration())

def relay_powerup(target="all"):
    # these can be combined
    gpio_dict = {"x": x_power, "y": y_power, "z": z_power}

    if target == "all":
        GPIO.output(x_power, 1)
        GPIO.output(y_power, 1)
        GPIO.output(z_power, 1)

    else:
        GPIO.output(gpio_dict[target], 1)

def relay_shutdown(target="all"):
    # these can be combined
    gpio_dict = {"x": x_power, "y": y_power, "z": z_power}

    if target == "all":
        GPIO.output(x_power, 0)
        GPIO.output(y_power, 0)
        GPIO.output(z_power, 0)

    else:
        GPIO.output(gpio_dict[target], 0)

def startup():
    relay_powerup()
    print("starting up...")




def command_ignition():
    # Upon receiving command from Parkes, approve Epoch to fire.
    flight_logger("command_ignition - active", duration())
    sleep(1)

    # confirm with parkes that launch is imminent
    v, a, m, p = "00000", "0000", "9", "20000"
    command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
    epoch_radio.write(command.encode())




    flight_logger("commanding all_fire", duration())

    all_fire()
    flight_logger("command_ignition - inactive", duration())

def test_single(target_ignitor=ignitor_x):
    # stay for That
    sleep(1)
    flight_logger("test_single - active", duration())
    select_fire(target_ignitor)
    flight_logger("test_single - inactive", duration())

def test_all():
    # yeah boy
    sleep(1)
    flight_logger("test_all - active", duration())
    test_fire()
    flight_logger("test_single - inactive", duration())




def select_fire(target_ignitor):
    sleep(1)
    flight_logger("IGNITION: firing ignitor " + str(target_ignitor), duration())

    GPIO.output(target_ignitor, GPIO.HIGH)
    sleep(IGNITION_DELAY)
    GPIO.output(target_ignitor, GPIO.LOW)


def all_fire(sleep_del=IGNITION_DELAY):
    flight_logger("IGNITION: firing all ignitors", duration())

    flight_logger("all_fire HIGH", duration())

    GPIO.output(ignitor_x, GPIO.HIGH)
    GPIO.output(ignitor_y, GPIO.HIGH)
    GPIO.output(ignitor_z, GPIO.HIGH)

    sleep(sleep_del)

    flight_logger("all_fire LOW", duration())
    GPIO.output(ignitor_x, GPIO.LOW)
    GPIO.output(ignitor_y, GPIO.LOW)
    GPIO.output(ignitor_z, GPIO.LOW)

    flight_logger("all_fire complete", duration())

def command_fire():
    current_am = 1
    while True:
        amount = input(": ")


        if amount == "":
            all_fire(current_am)
        else:
            current_am = float(amount)

def test_fire():
    sleep(1)
    counter = 1
    seco = 0

    while counter > 0:

        # Testfire ignitor x
        GPIO.output(ignitor_x, GPIO.HIGH)
        sleep(counter)
        GPIO.output(ignitor_x, GPIO.LOW)

        # Testfire ignitor y
        GPIO.output(ignitor_y, GPIO.HIGH)
        sleep(counter)
        GPIO.output(ignitor_y, GPIO.LOW)

        # Testfire ignitor z
        GPIO.output(ignitor_z, GPIO.HIGH)
        sleep(counter)
        GPIO.output(ignitor_z, GPIO.LOW)
        sleep(counter)
        counter -= 0.1

        if seco < 10 and counter < 0.1:
            print("go")
            counter += 0.1
            seco += 1

    # Testfire all ignitors
    GPIO.output(ignitor_x, GPIO.HIGH)
    GPIO.output(ignitor_y, GPIO.HIGH)
    GPIO.output(ignitor_z, GPIO.HIGH)
    sleep(2)
    GPIO.output(ignitor_x, GPIO.LOW)
    GPIO.output(ignitor_y, GPIO.LOW)
    GPIO.output(ignitor_z, GPIO.LOW)


# STARTUP
init_time = time.time()
flight_logger("epoch launch software - startup", duration())
flight_logger("initialising pls - verison: " + str(epoch_version), duration())
# Initialise epoch_radio
#open_port() DEBUG
time.sleep(1)
flight_logger("port open", duration())

command_dict = {
    0 : echo,
    1 : command_ignition,
    2 : test_fire,
    3 : test_single,
    4 : startup,
    5 : command_fire

}


command_list = {0:"echo", 1:"command_ignition", 2:"test_fire", 3:"test_single", 4:"startup", 5:"command_fire"}
while True:

    for command in command_list:
        print(" - " + str(command) + " : " + str(command_list[command]))
    print(" ")
    inp = int(input("Select command: "))

    if inp in command_list:
        command_dict[inp]()
    print(" ")
    time.sleep(1)

test = """while receiving_command:
    flight_logger("RECEIVING COMMAND...", duration())

    new_command = vamp_destruct(receive())
    flight_logger("COMMAND: " + str(new_command), duration())

    target_program = new_command[2]
    target_comp = new_command[3][0]
    if __name__ == "__main__":
        try:
            # Check epoch is the intended target for command
            if target_comp == comp_id:

                command_dict[target_program]()
        except KeyboardInterrupt:
            flight_logger("KeyboardInterrupt detected", duration())
            flight_logger("port closed", duration())
            compile_logs()"""




      # do noth
