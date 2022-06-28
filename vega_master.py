#vfs

# requires pave_comms.py (beta 1 and up)
# requires pave_file.py (beta 1 and up)

'''
    ==========================================================
    Vega Flight Software, version 0.6
    Copyright (C) 2022 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    ==========================================================
'''


import Adafruit_BMP.BMP085 as BMP085
import time
import smbus
from time import sleep
import math
import threading
import serial
import copy
import os
from random import randint
import csv
import pave_comms
import pave_graphics
import numpy as np
import RPi.GPIO as GPIO
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise
from picamera import PiCamera


vega_version = 0.6
internal_version = "0.6.1"

#=============================
global flight_data
global data_store
global configuration
import time

# Configuration Values
RUN_CAMERA = False
COMP_ID = 0
COMP_NAME = "vega flight software"


flight_data = {}
test_shit = {}
data_store = []
bmp_sensor = BMP085.BMP085()
receiving_command = True
if RUN_CAMERA:
    onboard_camera = PiCamera()
configuration = {
    "beep_vol" : 5,
    "debug_mode" : True,
    "rocket_data" : {"name"       : "R2",
                     "burn_time"  : 3.5,
                     "deploy_time": 4,
                     "max_accel"  : 15 }
}

# Default pin constants for GPIO
#GPIO.setwarnings(False)
#GPIO.setmode(GPIO.BOARD)
GPIO_MATE = 99
#GPIO.setup(GPIO_MATE, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#Constants
LOG_FILENAME = "vega_flightlog.txt"
VIDEO_FILENAME = "vega_onboard"
VIDEO_SAVELOCATION = "/home/pi/Desktop/"
X_OFFSET = 1.42
RAW_AX_OFFSET = 21100
AVIONICS_RUNTIME = 300
FILE_VARS = ['time','altitude','velocity', 'kalman_velocity',
             'mode','gx','gy','gz','ax','ay','az','id']

#MPU6050 Registers
bus = smbus.SMBus(1)    #bus = smbus.SMBus(0) on older version boards
PWR_MGMT_1   = 0x6B
SMPLRT_DIV   = 0x19
CONFIG       = 0x1A
GYRO_CONFIG  = 0x1B
INT_ENABLE   = 0x38
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F
GYRO_XOUT_H  = 0x43
GYRO_YOUT_H  = 0x45
GYRO_ZOUT_H  = 0x47
MPU_ADDRESS  = 0x68   # MPU6050 device address

# define Kalman filter (https://filterpy.readthedocs.io/en/latest/kalman/KalmanFilter.html)
K_f = KalmanFilter(dim_x=2, dim_z=1)


def error(error_in, error_extra=""):
    # converts parkes error to flight log
    flight_logger(f"{error_in} - {error_extra}", duration())


def check_mate():
    # check for mating connection

    if (GPIO.input(GPIO_MATE) == GPIO.LOW):
        return True

    return False




def MPU_Init():
        # Comments to explain this function are in imutest.py
        bus.write_byte_data(MPU_ADDRESS, SMPLRT_DIV, 7)
        bus.write_byte_data(MPU_ADDRESS, PWR_MGMT_1, 1)
        bus.write_byte_data(MPU_ADDRESS, CONFIG, 0)
        bus.write_byte_data(MPU_ADDRESS, GYRO_CONFIG, 24)
        bus.write_byte_data(MPU_ADDRESS, INT_ENABLE, 1)

def read_raw_data(high_address):
        # Reads data from addresses of MPU
        low_address = high_address + 1
        high = bus.read_byte_data(MPU_ADDRESS, high_address)
        low = bus.read_byte_data(MPU_ADDRESS, low_address)

        #concatenate higher and lower value
        value = ((high << 8) | low)

        #to get signed value from mpu6050
        if value > 32768:
                value = value - 65536
        return value



def get_temp():
        return bmp_sensor.read_temperature()

def get_press_local():
        return bmp_sensor.read_pressure()

def get_alt():
        return bmp_sensor.read_altitude()

def get_press_sea():
        return bmp_sensor.read_sealevel_pressure()


global error_log
global flight_log

error_log, flight_log = [], []


def file_append(target_file, data):
    # VFS File Appending Tool
    opened_file = open(target_file, "a")
    opened_file.write(data + "\n")
    opened_file.close()

def file_init(target_file, title):
    # VFS File Creation Tool
    top_line = f"========== {title} ==========\n"
    bottom_line = "=" * (len(top_line)-1) + "\n"
    new_file = open(target_file, "w")
    new_file.write(top_line)
    new_file.write("VEGA v" + str(vega_version) + " / "+internal_version+"\n")
    new_file.write(bottom_line)
    new_file.write(" \n")
    new_file.close()

def flight_log_update(f_log):
    #print("DEBUG: UPDATING LOG")
    log_file = open(LOG_FILENAME, "a")

    for data in f_log:
        log_file.write(str(data) + "\n")

    log_file.close()



def flight_log_unload(flight_log, done=True):
    # VFS Flight Log Unloader Tool
    log_file = open(LOG_FILENAME, "a")
    print("DEBUG: LOADING TO LOG")

    for tuple in flight_log:
        log, timestamp = tuple
        log_file.write(f"- {timestamp} : {log}\n")

    if done:
        log_file.write("END OF LOG\n")
    log_file.close()

def error_unload(error_list):
    # at the end of flight/terminal event, save error list to errorlog file
    error_log_title = "vega_errorlog.txt"
    pave_file.create(error_log_title, "VEGA ERROR LOG", "Vega", internal_version)

    error_file = open(error_log_title, "a")

    for tuple in error_list:
        error, timestamp = tuple
        error_file.write(f"- {timestamp} : {error}\n")

    error_file.close()

def data_unload(data_output, variable_list=FILE_VARS):
    # Creates a new csv file and stores the input within
    file_code = randint(0, 100)
    f_name = f"data_log_{file_code}.csv"
    title = os.path.join("/home/pi/Flight_Data",f_name)


    with open(title, 'w', newline='') as file:

        # Initialise csv writer
        writer = csv.writer(file)

        # Write header line with column names
        writer.writerow(variable_list)
        unlisted_var_count = len(variable_list) - 7
        gyro_index = unlisted_var_count
        accel_index = gyro_index + 1

        # For every packet in the input, compile and write a line
        # to the csv file
        if not data_output:
            return

        for entry in data_output:

            new_line = []

            # Build list of gyro and acc values from input
            gyro_vals = [entry[gyro_index]["Gx"], entry[gyro_index]["Gy"], entry[gyro_index]["Gz"]]
            acel_vals = [entry[accel_index]["Ax"], entry[accel_index]["Ay"], entry[accel_index]["Az"]]



            # Add first unlisted variables
            for first in range(unlisted_var_count):
                new_line.append(str(entry[first]))

            # Add gyoscope measurments
            for g_index in range(3):
                new_line.append(gyro_vals[g_index])

            # Add accelerometer measurements
            for a_index in range(3):
                new_line.append(acel_vals[a_index])

            # Finally add packet ID
            new_line.append(entry[unlisted_var_count + 2])

            # Write the new input line to the csv file
            writer.writerow(new_line)
            print("-",new_line)


def checkComputer(command_p, computer_id):
    # check that command was intended for given computer
    if (len(str(command_p)) == 5):
        command_id = str(command_p)[0]
        computer_id = str(computer_id)

        if (command_id == computer_id):
            print(f"DEBUG: {command_id} = {computer_id}")
            return True

    else:
        print(f"DEBUG: {command_p}")
        return checkComputer(str(command_p).zfill(5), computer_id)

    return False

def flight_logger(event, time=0):
    # add event at given timestamp to flight log
    global flight_log

    new_log = (event, time)
    print(f" - {new_log[0]}")
    pave_file.append("debug.txt", str(new_log))
    flight_log.append(new_log)


def error_logger(error_code, time):
    # add error at given timestamp to error log
    global error_log

    new_error = (error_code, time)
    error_log.append(new_error)

def duration():
    # Returns current change in time
    return format(time.time() - init_time, '.2f')

def flight_time(launch_time):
    return format(time.time() - launch_time, '.2f')

def estimate_velocity():
    global flight_data
    flight_data["velocity"], last_r = 0, 0
    flight_logger("- VEST startup complete", duration())

    # Finds a poor estimate for velocity in increments of 0.5 seconds
    while flight_data["avionics_loop"]:
            init_alt = bmp_sensor.read_altitude()
            sleep(0.5)
            delta_y = ((bmp_sensor.read_altitude() - init_alt) / 0.5)
            if abs(delta_y - last_r) < 102:
                flight_data["velocity"] = delta_y
                last_r = delta_y
            sleep(0.08)

    flight_logger("- closing VEST thread", duration())

def run_MPU():
    # Logs acceleration and gyroscope data

    MPU_Init()    # Setup MPU6050
    flight_logger("- MPU startup complete", duration())
    global flight_data
    flight_data["accel"] = {
        "Ax" : 0,
        "Ay" : 0,
        "Az" : 0
    }

    flight_data["gyro"] = {
        "Gx" : 0,
        "Gy" : 0,
        "Gz" : 0
    }

    accel_hold, gyro_hold = {}, {}
    while flight_data["avionics_loop"]:
            #Read Accelerometer raw value
            acc_x = read_raw_data(ACCEL_XOUT_H)
            acc_y = read_raw_data(ACCEL_YOUT_H)
            acc_z = read_raw_data(ACCEL_ZOUT_H)

            if (acc_x < -10000):
                acc_x /= 2

            acc_x += RAW_AX_OFFSET

            #print("X DATA = " + str(acc_x) + " Z DATA = " + str(acc_z))

            #Read Gyroscope raw value
            gyro_x = read_raw_data(GYRO_XOUT_H)
            gyro_y = read_raw_data(GYRO_YOUT_H)
            gyro_z = read_raw_data(GYRO_ZOUT_H)

            ACC_DIVISOR = 16384.0
            GYRO_DIVISOR = 131.0

            #Full scale range +/- 250 degree/C as per sensitivity scale factor
            flight_data["accel"]["Ax"] = acc_x / ACC_DIVISOR
            flight_data["accel"]["Ay"] = acc_y / ACC_DIVISOR
            flight_data["accel"]["Az"] = acc_z / ACC_DIVISOR

            flight_data["gyro"]["Gx"] = gyro_x / GYRO_DIVISOR
            flight_data["gyro"]["Gy"] = gyro_y / GYRO_DIVISOR
            flight_data["gyro"]["Gz"] = gyro_z / GYRO_DIVISOR

            sleep(0.1)

    flight_logger("- closing MPU thread", duration())


def flight_status():
    global flight_data
    didUpdate = False

    flight_logger("- Status Watchdog startup complete", duration())
    while flight_data["avionics_loop"]:
        start_alt, status = get_alt(), ""
        old_status = status
        BUFFER = 8

        sleep(3.5)

        # positive difference
        if (get_alt() > start_alt):
            didUpdate = True
            status = 0

        # negative difference
        elif (get_alt() < start_alt - BUFFER):
            didUpdate = True
            status = 1

        # less than difference
        elif (abs(get_alt() - start_alt) < 4 ):
            didUpdate = True
            status = 2

        if (didUpdate):
            didUpdate = False
            #flight_logger(f"status update detected: {old_status} -> {status}", duration())

        flight_data["status"] = status

    flight_logger("- closing Status Watchdog thread", duration())



# Multi-threading Functions
def vel_start():
    global flight_data

    velocity_thread = threading.Thread(target=estimate_velocity)
    velocity_thread.start()

def status_start():
    status_thread = threading.Thread(target=flight_status)
    status_thread.start()

def mpu_start():
    mpu_thread = threading.Thread(target=run_MPU)
    mpu_thread.start()

def alt_start():
    altitude_thread = threading.Thread(target=altitude)
    altitude_thread.start()


# Flight functions

def pre_flight():
    return True

def go_launch():
    pf_checks = pre_flight()
    if pf_checks:
        return True
    else:
        return pf_checks


def start_recording(filename=VIDEO_FILENAME, savelocation=VIDEO_SAVELOCATION):
    # Initiate onboard recording
    try:
        file_name = filename + ".h264"
        file_out = save_location + file_name
        onboard_camera.start_recording(file_out)
        flight_logger("started video recording as |" +filename+"| ", duration())

    except:
        flight_logger("unable to start recording, check camera connection", duration())

def stop_recording(filename=VIDEO_FILENAME, savelocation=VIDEO_SAVELOCATION):
    # End onboard recording
    try:
        onboard_camera.stop_recording()
        flight_logger("stopped video recording as |" +filename+"| ", duration())
        flight_logger("video saved to: "+savelocation, duration())

    except:
        flight_logger("unable to stop recording, unknown error", duration())

def reject_outliers(data, m = 2.):
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d/mdev if mdev else 0.
    return data[s<m]


def getPastAltitude(current_time, second_ago, flight_data):
    # function to return altitude at (current_time - second_ago)

    target_time = current_time - second_ago

    for entry in flight_data[::-1]:
     entry_time = entry[0]

     if (entry_time > target_time):
         return entry[1]

def isAscending(current_time, current_alt, flight_data):

    TIME_DELTA = 2 # seconds ago to check

    past_alt = getPastAltitude(current_time, TIME_DELTA, flight_data)

    if (past_alt < current_alt):
        return True # rocket is ascending

    return False    # rocket not ascending


def armed():
    global configuration
    global flight_log
    global error_log
    # Confirm received:
    sleep(1)
    v, a, m, p = "21000", "0000", "0", "20000"
    command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
    vega_radio.write(command.encode())


    flight_logger("-> armed() initated", duration())
    # Update parkes

    flight_logger("armed_alt: " + str(get_alt()), duration())


    attempts = []
    for attempt in range(3):
        attempts.append(bmp_sensor.read_altitude())
    calibrated_alt = sum(attempts) // 3
    calibrated_acc = 0
    flight_logger("calibrated_alt: " + str(calibrated_alt), duration())
    flight_logger("entering arm loop", duration())


    flight_logger("go/no-go poll running...", duration())
    launch_poll = go_launch()

    if launch_poll == True:
        # send vega is ready
        sleep(1)
        v, a, m, p = "20202", "0", "1", "20202"
        command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
        vega_radio.write(command.encode())
        flight_logger("poll result: GO", duration())
    else:
        # send vega not ready
        v, a, m, p = "00000", "0000", "1", "21111"
        command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
        vega_radio.write(command.encode())
        flight_logger("poll result: NO GO", duration())
        flight_logger("go_launch() returned: "+ launch_poll, duration())
        error_logger("Exxx")
        flight_log_unload(flight_log, True)
        error_unload(error_log)
        return


    flight_log_update(flight_log)
    flight_log = []
    sleep(1)

    if (RUN_CAMERA):
        start_recording()

    flight_data["avionics_loop"] = True    # Allows avionics capture

    vel_start()
    status_start()
    mpu_start()
    flight_logger("all multithreads succesful", duration())
    flight_data["flight_record"] = []

    # enters flight loop
    flight_data["flight_record"] = flight(calibrated_alt, calibrated_acc)

    data_unload(flight_data["flight_record"])
    if RUN_CAMERA:
        stop_recording()

    error_unload(error_log)


def list_avg(array):
    sum = 0

    count = len(array)
    for element in array:
        sum += element
    return sum/count

def sanity_check(currentAlt, avg):
    # returns whether acceleration data should be stored or not

    # accel value would exceed expected max
    if (abs(currentAlt - list_avg(avg)) > configuration["rocket_data"]["max_accel"]):
        return False
    elif (currentAlt < -5):
        return False

    return True


def vamp_destruct(vamp):
    # Breaks vamp into tuple of values
    vamp_decom = []
    for element in vamp.split("_"):
        vamp_decom.append(element[1:])

    try:
        v, a, m, p = vamp_decom
        vamp = (floor(float(v)), floor(float(a)), int(m), int(p))
    except:
        print(f"vamp error {vamp} ")

    return vamp

# Data structure = [timestamp, altitude, velocity, data id]
def flight(calib_alt, calib_acc):
    global configuration
    flight_logger("-> flight() initated", duration())
    # This function is the main flight loop. Let's keep things light boys
    global flight_data

    # set flight variables
    flight_data["state"] = "flight"
    flight_data["status"] = 2
    data_store = []
    data_id = 0
    hold = True

    pave_file.create(LOG_FILENAME, "VEGA FLIGHT LOG", "Vega", internal_version)

    flight_logger("Flight log initialised")
    recent_vamp = pave_comms.vamp_compile(10000, 1000, 8, 1)

    flight_logger("flight variables set", duration())


    # time delays for this rocket
    burn_time = configuration["rocket_data"]["burn_time"]
    deploy_time = burn_time + configuration["rocket_data"]["deploy_time"]

    # altitude defaults
    last_a = bmp_sensor.read_altitude() - calib_alt
    running_avg = [last_a, last_a, last_a, last_a, last_a]


    flight_logger("Initialising Kalman Filter", duration())
    # initialise kalman state values
    K_f.x = np.array([last_a, 0.0])

    # state transition
    K_f.F = np.array([[1.0, 1.0],
                     [0.0, 1.0]])

    # observation model
    K_f.H = np.array([[1.0, 0.0]])

    # covariance matrix
    K_f.P = np.array([[1000.0, 0.0],
                      [0.0, 1000.0]])

    # covariance of observation noise
    K_f.R = np.array([[5.0]])

    # covariance of process noise
    K_f.Q = Q_discrete_white_noise(dim=2, dt=0.1, var=0.13)


    flight_logger("Kalman Filter ready", duration())
    flight_logger("holding for ignition", duration())

    hold_start = time.time()
    while hold:
        loop_time = time.time()
        # get confirmation
        new_command = improved_receive()

        # if command is not nonetype
        if new_command:
            if (vamp_destruct(new_command)[2] == 9):
                # check for epoch confirmation to parkes
                flight_logger(f"ignition detected! - {new_command}", duration())
                hold = False
                break
        else:
            flight_logger("no command available (L611)", duration())

        if (loop_time - hold_start > 10):
            # waited for more than 30 seconds
            flight_logger("hold timeout", duration())
            return


    # Timekeeping
    flight_logger("switching to flight time", duration())
    launch_time = time.time()
    flight_logger("flight() loop entered", flight_time(launch_time))
    sleep(1)


    preloop_time = time.time()
    count = 0
    command = ""


    # Flight Loop
    while (True):

        # assign timestamp to loop
        current_time = flight_time(launch_time)

        # increment loop count and set initial altitude
        loop_count += 1
        initial_alt = (bmp_sensor.read_altitude() - calib_alt)

        # run prediction for Kalman filter
        K_f.predict()

        # assign predictions
        alt_prediction = K_f.x[0]
        vel_prediction = K_f.x[1]

        # calculated velocity assignment
        vel_calculated = flight_data["velocity"]

        # check value is within expected range
        if (sanity_check(initial_alt, running_avg)):

            # update kalman filter with new reading
            new_altitude = math.floor(initial_alt)
            K_f.update(new_altitude)

            # get altitude and velocity from kalman filter
            alt_kalman = K_f.x[0]
            vel_kalman = K_f.x[1]

            # update running average with new altitude
            running_avg.pop(0)
            running_avg.append(alt_kalman)

            # update most recent 'good' altitude
            last_alt = alt_kalman

            # build vamp using most recent data and save vamp
            vamp = pave_comms.vamp_compile(vel_kalman, alt_kalman, current_mode, data_id)
            recent_vamp = vamp

            # send vamp
            pave_comms.send(vamp, vega_radio)

            # decide on final data values
            vel = vel_kalman
            alt = alt_kalman

        else:
            # sanity check failed, use prediction of what data *may* have been
            last_alt = alt_prediction

            # decide on final data values
            vel = vel_prediction
            alt = alt_prediction


        # update data store in format [t, a_k, v_c, v_k, m, gyro, accel, p]
        new_data = [current_time, alt, vel_calculated, vel, current_mode,
                    flight_data["gyro"], flight_data["accel"], data_id]

        data_store.append(copy.deepcopy(new_data))


        # keep track of generated data packets
        data_id += 1


        # --- flight status detection ---
        mode_data = (new_data[1], data_store)
        current_mode = determineMode(current_mode, current_time, calib_alt, mode_data)


        # --- check for loop end ---
        elapsed_time = current_time - preloop_time

        if (elapsed_time > AVIONICS_RUNTIME):
            # exhausted recording limit, end avionics loop
            flight_logger("avionics runtime met", duration())

            # tell parkes to end downlink
            kill_loop = pave_comms.vamp_compile(10000, 1000, 6, 20000)
            pave_comms.send(kill_loop, vega_radio)

            # kill avonics loops and merge threads
            flight_data["avionics_loop"] = False

            # compile flight log
            flight_log_update(flight_log)

            # return data and end flight loop
            return data_store

        sleep(0.02)

def determineMode(current_mode, current_time, calib_alt, data):
    mode = current_mode

    # detect unpowered flight
    if (float(current_time) > (burn_time + 1)):
        mode = "m3"

    # detect apogee
    if not (isAscending(current_time, data[0], data[1])):
        flight_logger(f"apogee detected!", current_time)
        mode = "m4"

    # detect parachute descent
    if (float(current_time) > deploy_time + 1) and (current_mode == "m4"):
        mode = "m5"

    # detect landed and safe
    if (abs(data[0] - calib_alt) < 5):
            mode = "m6"


    return mode

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
    # This entire function is some demo bullshit and will be removed when the connection issue
    # has been solved. Ignore it. Seriously.
    global data_store
    data_id=demo_vel=demo_alt=current_modetype=0

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
    flight_logger("opened port - vega_radio", duration())

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
        error("E310")
    command = "v"+str(v)+"_a"+str(a)+"_m"+str(m)+"_p"+str(p)+"\n"
    vega_radio.write(command.encode())

def receive():
    # Listens for a vamp from Vega. Simples
    data = vega_radio.read_until()
    to_return = data
    try:
        to_return = to_return.decode()
    except:
        print("Unable to decode - " + to_return)
    return to_return

def improved_receive(override_timeout=False, timeout_set=5):
    # Receives for command from vega_radio - waits indefinitely
    # unless timeout is specified

    if override_timeout:
        vega_radio.timeout = timeout_set
        data = vega_radio.read_until()
        to_return = data
        to_return = to_return.decode()
        vamp_decom = []
        vega_radio.timeout = None
        for element in to_return.split("_"):
            vamp_decom.append(element[1:])
        try:
            v, a, m, p = vamp_decom
            vamp = (floor(float(v)), floor(float(a)), int(m), int(p))
            return to_return
        except:
            flight_logger("- Timeout detected - " + str(vamp_decom), duration())
            return "timeout"

    # Listens for a vamp from parkes. Simples
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
        vamp = (int(v), int(a), int(m), int(p))
    except:
        flight_logger("Error: vamp overload, handling", duration())
        vamp = (0, 0, 0, 0)


    return vamp

def set_beep(value):
    global configuration
    flight_logger(f"beep_vol set to {value}", duration())
    configuration["beep_vol"] = int(value)

def set_debug(value):
    global configuration

    try:
        if value == "True":
            configuration["debug_mode"] = True
        else:
            configuration["debug_mode"] = False
        flight_logger(f"debug mode set to {value}", duration())
        return True
    except:
        flight_logger(f"debug could not be set to {value}", duration())
        return False

def config_update(data):
    target, value = data[0], data[1:]

    function_definitions = {
        "A" : set_beep,
        "B" : set_debug
    }
    try:
        return function_definitions[target](value)

    except:
        return False

def show_gyro():
    global flight_data
    print(flight_data["gyro"])


def altitude():
    global flight_data
    # Logs current alt to flight_data"""
    flight_logger("- BMP startup complete", duration())
    flight_data["altitude"] = get_alt()


def receive_config():
    new_command = vega_radio.read_until().decode().split("|")
    flight_logger("UPDATING CONFIG", duration())
    con_count, con_list = 0, ""

    for update in new_command:
        result = config_update(update)

        if result:
            con_count += 1
            con_list += "|" + update


    return_update = str(con_count) + "." + con_list
    flight_logger(return_update, duration())
    vega_radio.write(return_update.encode())
    flight_logger("CONFIG UPDATE COMPLETE", duration())



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
        to_send = to_send + str(beat).zfill(5) + "\n"

        vega_radio.write(to_send.encode())
        sleep(0.6)
        print("Heartbeat Away... (" +str(beat)+") ("+to_send[:-1]+")")
        beat += 1
        check_kill = ""
        check_kill = vega_radio.read_until().decode()
        if "v10000_a1000_m8_p" in check_kill:
            flight_logger("heartbeat() kill acknowledged", duration())
            heartbeat_loop = False
        if "config_update" in check_kill:
            flight_logger("config_update acknowledged", duration())
            receive_config()

    vega_radio.timeout = None


def arm():
    flight_logger("DEBUG: disabled rec_command", duration())
    armed()

def heartbeat_init():
    flight_logger("heartbeat command received", duration())
    vega_radio.write("v10000_a1000_m8_p00000\n".encode())
    heartbeat()

def force_launch():
    global flight_data
    flight_logger("FORCING LAUNCH", duration())
    flight_data["avionics_loop"] = True
    flight_logger("Avionics loop is active", duration())
    mpu_start()
    flight_logger("MPU is active", duration())
    vel_start()
    flight_logger("BMP is active")
    flight_logger("GO FOR FORCED LAUNCH", duration())
    flight(get_alt(), 0)

def compile_logs():
    flight_logger("COMPILING LOGS...", duration())
    flight_log_unload(flight_log)
    error_unload(error_log)
    sleep(1)

pave_file.create("debug.txt", "DEBUG FILE", "Vega", internal_version)


# STARTUP
init_time = time.time()
pave_graphics.startupDisplay(COMP_NAME, vega_version, internal_version)
flight_logger(f"startup", duration())
flight_logger("initialising vfs", duration())
open_port()
time.sleep(1)
flight_logger("port open", duration())

flight_logger("setup complete", duration())

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
    target_comp = int(str(new_command[3])[0])

    try:
        # Check vega was the intended target
        if (checkComputer(new_command[3], COMP_ID)):
            flight_logger(f"command [{target_program}] detected for vega", duration())
            command_dict[target_program]()
        else:

            intended_comp = ("Parkes" if target_comp == 2 else "Epoch")
            flight_logger("VEGA ID = " + str(COMP_ID) +", TARGET ID = " + str(target_comp))
            flight_logger(f"command detected - intended for {intended_comp}, not Vega"+"\n", duration())

    except KeyboardInterrupt:
        flight_logger("KeyboardInterrupt detected", duration())
        vega_radio.close()
        flight_logger("port closed", duration())
        compile_logs()


      # do noth
