# Oh boy here we go


# You're gonna want the bmp_functions stored in the same folder
# https://github.com/jackwoodman/vega/blob/master/bmp_functions.py
#import bmp_functions
import time
import math
import threading

# The following assumes we only have an altimeter

# Look out we're using global variables fuck fuckfuckfuck
global flight_data
global data_store

flight_data = {}
test_shit = {}
data_store = []


""" The RPI needs an internet connection to keep time. Since the rocket won't
    be able to keep an internect connection, I'm going to have to make my own
    shitty timer. The issue: I'm going to use multi-threading to do this. Is
    that bad? Very. Will it work?"""


def timer():
    flight_data["current_time"] = 0
    flight_data["boot_time"] = 0
    current_time = 0.000


    # The value 0.008865 gives the least time drift on within 20 seconds of launch
    while True: 
        flight_data["current_time"] += 0.01
        time.sleep(0.008865)

def estimate_velocity():
    initial_time_one = flight_data["current_time"]
    alts_one = []

    while (initial_time_one - flight_data["current_time"]) < 0.5:
        alts_one.append(bmp_functions.get_altitude())

    alt_one_dis = alts_one[-1] - alts_one[0]

    alts_one_average = alt_one_dis / 2

    flight_data["velocity"] = alts_one_average

    
def altitude():
    flight_data["altitude"] = bmp_functions.get_altitude()



# Multi-threading Functions
def timer_start():

    timer_thread = threading.Thread(target=timer)
    timer_thread.start()

def vel_start():
    velocity_thread = threading.Thread(target=estimate_velocity)
    velocity_thread.start()

def alt_start():
    altitude_thread = threading.Thread(target=altitude)
    altitude_thread.start()

def armed():
    # Initialising stuff
    armed_alt = bmp_functions.get_altitude()
    while True:
        current_alt = bmp_functions.get_altitude()
        # Look out for the one
        if current_alt - armed_alt > 1:
            break
    timer_start()
    vel_start()
    alt_start()
    flight_data["flight_record"] = flight()
        
        



# Data structure = [timestamp, altitude, velocity, data id]
def flight():
    flight_data["status"] = "flight"
    data_id = 0
    while True:
        
        data_store.append[flight_data["current_time"], flight_data["altitude"], flight_data["velocity"], data_id]
    return data_store


    





