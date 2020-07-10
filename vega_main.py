# Oh boy here we go
#Iteratino Version 0.1.14

# You're gonna want the bmp_functions stored in the same folder
# https://github.com/jackwoodman/vega/blob/master/bmp_functions.py
import Adafruit_BMP.BMP085 as BMP085
import time
from time import sleep
import math
import threading
import serial
# The following assumes we only have an altimeter. Need to add config file support for dedicated accelerometer

# Look who hasn't learnt his lesson and is using global variables again
global flight_data
global data_store
import time

flight_data = {}
test_shit = {}
data_store = []
bmp_sensor = BMP085.BMP085()

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

def duration():
    """ Returns current change in time"""
    return format(time.time() - init_time, '.2f')


def estimate_velocity():
    global flight_data
    """ Finds a poor estimate for velocity in increments of 0.5 seconds"""
    while True:
            initial_time_one = duration()
            alts_one = []

            while (float(initial_time_one) - float(duration())) < 0.5:
                alts_one.append(get_alt())

            alt_one_dis = alts_one[-1] - alts_one[0]

            alts_one_average = alt_one_dis / 2

            flight_data["velocity"] = alts_one_average


def altitude():
    global flight_data
    """ Logs current alt to flight_data"""
    flight_data["altitude"] = get_alt()



# Multi-threading Functions
def vel_start():
    global flight_data
    flight_data["velocity"] = 0
    velocity_thread = threading.Thread(target=estimate_velocity)
    velocity_thread.start()

def alt_start():
    altitude_thread = threading.Thread(target=altitude)
    altitude_thread.start()



# Flight functions

def armed():
    # Update parkes
    vega_radio.write("v00000_a0000_m1_p00000".encode())


    # Initialising stuff
    armed_alt = get_alt()
    while True:
        current_alt = get_alt()
        # This might need some boundary adjustments becuase fuck dude
        if current_alt - armed_alt > 2:
            break
    timer_start()
    vel_start()
    alt_start()
    flight_data["flight_record"] = flight()

# Data structure = [timestamp, altitude, velocity, data id]
def flight():
    global data_store
    flight_data["status"] = "flight"
    data_id = 0
    while True:
        #data_store.append((flight_data["current_time"], data_id))
        v, a, m, p = flight_data["velocity"], bmp_sensor.read_altitude(), "m2", data_id
        data_store.append((duration(), a, flight_data["velocity"], data_id))
        print(a)
        command = str("v"+str(v).zfill(5)+"_a"+str(a).zfill(4)+"_m"+str(m)+"_p"+str(p).zfill(5)+"\n")
        sleep(0.1)
        vega_radio.write(command.encode())

        data_id += 1
        sleep(0.1)

def bmp_debug():
    global data_store
    while True:
        command = "v00000_a"+str(bmp_sensor.read_altitude())+"m2_p00000"
        vega_radio.write(command.encode())



def open_port():
    global vega_radio
    # Opens the default port for Parkes transceiver
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
        print("DEBUG: heartbeat = on")
        vega_radio.write("v10000_a1000_m8_p00000\n".encode())
        heartbeat()

    elif "v10000_a1000_m0_p" in new_command:
        receiving_command = False
        print("NC: "+ new_command)
        print("DEBUG: disabled rec_command")

    elif "v10000_a1000_m2_p" in new_command:
        vel_start()
        flight()


armed()
