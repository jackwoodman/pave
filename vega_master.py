

'''
    ==========================================================
    Vega Flight Software, version 0.3
    Copyright (C) 2020 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    ==========================================================
'''

# You're gonna want the bmp_functions stored in the same folder
# https://github.com/jackwoodman/vega/blob/master/bmp_functions.py
import Adafruit_BMP.BMP085 as BMP085
import time
from time import sleep
import math
import threading
import serial
# The following assumes we only have an altimeter. Need to add config file support for dedicated accelerometer

#============RULES============
# 1.) Function descriptions marked  |--- TO BE REMOVED ---| are only used for
#     debug and dev purposes only. They will be archived on final release, so
#     don't call the function anywhere else that is intended for final release.
#=============================


# Look who hasn't learnt his lesson and is using global variables again
global flight_data
global data_store
import time

flight_data = {}
test_shit = {}
data_store = []
bmp_sensor = BMP085.BMP085()

vega_version = 0.3

def get_temp():
        return bmp_sensor.read_temperature()

def get_press_local():
        return bmp_sensor.read_pressure()

def get_alt():
        return bmp_sensor.read_altitude()

def get_press_sea():
        return bmp_sensor.read_sealevel_pressure()

""" The RPI needs an internet connection to keep time. Since the rocket won't
    be able to keep an internect connection, I'm going to have to make my own
    shitty timer. The issue: I'm going to use multi-threading to do this. Is
    that bad? Very. Will it work?

    UPDATE
    Guess what. I lied. Totally can work on its own, just can't get an accurate start time.
    That was a monumental waste of time. The homemade time functions are saved in the local
    backup of vega in case I'm wrong twice over.
    """
init_time = time.time()

global error_log
global flight_log

error_log, flight_log = [], []

def file_init(target_file, title):
    top_line = f"========== {title} ==========\n"
    bottom_line = "-" * len(top_line) + "\n"
    new_file = open(target_file, "w")
    new_file.write(top_line)
    new_file.write("Vega Version: " + str(vega_version)+"\n")
    new_file.write(bottom_line)
    new_file.write("")
    new_file.close()

def flight_log_unload(flight_log):
    flight_log_title = "vega_flightlog.txt"
    file_init(flight_log_title, "VEGA FLIGHT LOG")
    log_file = open(flight_log_title, "a")

    for tuple in flight_log:
        log, timestamp = tuple
        log_file.write(f"- {timestamp} : {log}\n")

    log_file.write("END OF LOG\n")
    log_file.close()

def error_unload(error_list):
    error_log_title = "vega_errorlog.txt"
    file_init(error_log_title, "VEGA ERROR LOG")

    error_file = open(error_log_title, "a")

    for tuple in error_list:
        error, timestamp = tuple
        error_file.write(f"- {timestamp} : {error}\n")

    error_file.close()

def flight_logger(event, time):
    global flight_log

    new_log = (event, time)

    flight_log.append(new_log)


def error_logger(error_code, time):
    global error_log

    new_error = (error_code, time)

    error_log.append(new_error)

def duration():
    """ Returns current change in time"""
    return format(time.time() - init_time, '.2f')

def flight_time(launch_time):
    return format(time.time() - launch_time, '.2f')

def estimate_velocity():
    global flight_data
    flight_data["velocity"] = 0
    last_r = 0
    """ Finds a poor estimate for velocity in increments of 0.5 seconds"""
    while True:
            init_alt = bmp_sensor.read_altitude()
            sleep(0.5)
            delta_y = ((bmp_sensor.read_altitude() - init_alt) / 0.5)
            if abs(delta_y - last_r) < 102:
                flight_data["velocity"] = delta_y
                last_r = delta_y
            sleep(0.08)


def altitude():
    global flight_data
    """ Logs current alt to flight_data"""
    flight_data["altitude"] = get_alt()



# Multi-threading Functions
def vel_start():
    global flight_data

    velocity_thread = threading.Thread(target=estimate_velocity)
    velocity_thread.start()

def alt_start():
    altitude_thread = threading.Thread(target=altitude)
    altitude_thread.start()


# Flight functions

def armed():
    flight_logger("armed() initated", duration())
    # Update parkes
    vega_radio.write("v00000_a0000_m1_p00000".encode())


    # Initialising stuff
    armed_alt = get_alt()
    flight_logger("armed_alt: " + str(armed_alt)", duration())
    flight_logger("entering arm loop", duration())
    while True:
        current_alt = get_alt()
        # This might need some boundary adjustments becuase fuck dude
        if current_alt - armed_alt > 2:
            flight_logger("LAUNCH DETECTED", duration())
            break
    timer_start()
    vel_start()
    alt_start()
    flight_logger("all multithreads succesful", duration())
    flight_data["flight_record"] = flight()



# Data structure = [timestamp, altitude, velocity, data id]
def flight():
    flight_logger("flight() initated", duration())
    # This function is the main flight loop. Let's keep things light boys
    global data_store
    flight_data["status"] = "flight"
    data_id = 0
    recent_command = "v10000_a1000_m8_p1"

    # THIS WILL BE MOVED TO ARMED()
    attempts = []
    for attempt in range(3):
        attempts.append(bmp_sensor.read_altitude())
    calibrated_alt = sum(attempts) // 3
    flight_logger("calibrated_alt: " + str(calibrated_alt), 00.00)


    # THIS WILL BE MOVED TO ARMED()
    last_a = bmp_sensor.read_altitude() - calibrated_alt
    launch_time = time.time()
    flight_logger("switching to flight time", duration())
    flight_logger("flight() loop entered", flight_time(launch_time))
    while True:
        #data_store.append((flight_data["current_time"], data_id))
        v, a, m, p = flight_data["velocity"], (bmp_sensor.read_altitude() - calibrated_alt), "m2", data_id

        data_store.append((flight_time(launch_time), a, v, data_id))
        if abs(a - last_a) < 100 and a > 0:
            command = str("v"+str(round(v, 4)).zfill(5)+"_a"+str(round(a, 4)).zfill(4)+"_"+str(m)+"_p"+str(p).zfill(5)+"\n")
            sleep(0.1)
            vega_radio.write(command.encode())
            if command:
                print(command)
            recent_command = command
        else:
            if command:
                vega_radio.write(recent_command.encode())
                error_logger("E010", flight_time(launch_time))
                print(command)

        data_id += 1
        sleep(0.1)

def bmp_debug():
    # --- TO BE REMOVED ---
    # This function has been deprecated and is ready for removal.
    # Do not base anything important on this function.
    global data_store
    global flight_data
    while True:
        command = str(flight_data["velocity"])+str(bmp_sensor.read_altitude())+"m2_p00000"
        print(command)
        sleep(0.7)

def demo_loop():
    global data_store
    data_id = 0
    demo_vel, demo_alt, current_modetype = 0, 0, 0

    while True:
        #data_store.append((flight_data["current_time"], data_id))
        v, a, m, p = demo_vel, demo_alt, "m"+str(current_modetype), data_id
        command = str("v"+str(round(v, 4)).zfill(5)+"_a"+str(round(a, 4)).zfill(4)+"_"+str(m)+"_p"+str(p).zfill(5)+"\n")
        sleep(0.1)
        vega_radio.write(command.encode())
        print(command)

        if demo_vel == 9999:
            demo_vel = 0
        else:
            demo_vel += 5

        if demo_alt == 999:
            demo_alt = 0
        else:
            demo_alt += 1

        if demo_alt % 10 == 0:
            if current_modetype != 7:
                current_modetype += 1
            else:
                current_modetype = 0

        sleep(0.1)




def open_port():
    global vega_radio
    # Opens the default port for Vega transceiver
    vega_radio = serial.Serial(
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
        error("E121")
    command = "v"+str(v)+"_a"+str(a)+"_m"+str(m)+"_p"+str(p)+"\n"
    vega_radio.write(command.encode())

def receive():
    # Listens for a vamp from Vega. Simples
    data = vega_radio.read_until()
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

    return vamp


def heartbeat():
    global vega_radio

    # Receive Handshake

    # Confirm handshake
    to_send = "v10000_a1000_m8_p00000\n"
    vega_radio.write(to_send.encode())

    # Start heartbeat
    # Heartbeat Loop
    beat = 1
    vega_radio.timeout = 0.6
    heartbeat_loop = True
    while heartbeat_loop:
        to_send = "v10000_a1000_m8_p"
        to_send = to_send + str(beat).zfill(5)
        to_send = to_send + "\n"

        vega_radio.write(to_send.encode())
        sleep(0.6)
        print("Heartbeat Away... (" +str(beat)+") ("+to_send+")")
        beat += 1
        check_kill = ""
        check_kill = vega_radio.read_until().decode()
        if "v10000_a1000_m8_p" in check_kill:
            heartbeat_loop = False

    vega_radio.timeout = None


# STARTUP

open_port()
receiving_command = True


while receiving_command:

    new_command = vega_radio.read_until().decode()

    if "v10000_a1000_m8_p" in new_command:
        flight_logger("heartbeat command received", duration())
        vega_radio.write("v10000_a1000_m8_p00000\n".encode())

        heartbeat()

    elif "v10000_a1000_m0_p" in new_command:
        receiving_command = False
        flight_logger("NC: "+ new_command, duration())
        flight_logger("DEBUG: disabled rec_command", duration())

    elif "v10000_a1000_m2_p" in new_command:
        #--- TO BE REMOVED ---
        flight_logger("FORCING LAUNCH", duration())
        flight_logger("LAUNCH DETCTED", duration())
        vel_start()
        flight()

    elif "v10000_a1000_m3_p" in new_command:
        #--- TO BE REMOVED ---
        demo_loop()

armed()
