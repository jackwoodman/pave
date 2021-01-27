# pgs
# internal verion 0.5.8

'''
    ==========================================================
    Parkes Ground Software, version 0.5
    Copyright (C) 2020 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    ==========================================================
'''

import time
import serial
import threading
import copy
import filecmp
from math import floor
from time import sleep
import RPi.GPIO as GPIO
from random import randint
from datetime import datetime
from RPLCD import CharLCD
import os

# hot_run defines whether Parkes will run using hardware or simulation.
global hot_run
hot_run = True
# tested keeps track of if the current version has been live tested
tested = False
parkes_version = 0.5
internal_version = "0.5.8"


# Constants
COMP_ID = 2
DEFAULTLEN = 16
IDLE_TIME = 35
ID_LEN = 10

# Default pin constants for GPIO in/out
GPIO_BACK = 16     # back button input
GPIO_SELECT = 18   # select button input
GPIO_CYCLE = 22    # cycle button input
GPIO_ARM = 13      # arm keyswitch input
GPIO_MISSILE = 15  # missile switch input
GPIO_LAUNCH = 11   # launch button input
GPIO_IGNITOR = 12  # ignitor trigger output
GPIO_LIGHT = 32    # launch light output

DEFAULT_NUMSEL = [1,2,3,4,5,6,7,8,9]
VAMP_STRING_STANDARD = {"v":5, "a":4, "m": 1, "p":5}
VAMP_TUPLE_STANDARD = {0:5, 1:4, 2:1 , 3:5}



# Initial LCD Setup
lcd = CharLCD(cols=16,
              rows=2,
              pin_rs=37,
              pin_e=35,
              pins_data=[33, 31, 29, 23],
              numbering_mode=GPIO.BOARD)

lcd.clear()
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

# Defining Hardware Input
GPIO.setup(GPIO_BACK, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Back button - GPIO 23
GPIO.setup(GPIO_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Select button - GPIO 24
GPIO.setup(GPIO_CYCLE, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Cycle button - GPIO 25
GPIO.setup(GPIO_ARM, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Arm key - GPIO 27
GPIO.setup(GPIO_MISSILE, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Arm key - GPIO 22
GPIO.setup(GPIO_LAUNCH, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Launch button - GPIO 17
GPIO.setup(GPIO_LIGHT, GPIO.OUT) # Light  - GPIO 17

# Defining Hardware Output
GPIO.setup(GPIO_IGNITOR, GPIO.OUT) # Ignition Output - GPIO 18

def sys_check_status(gpio_pin):
    # check if input pin is pulled low or not
    if GPIO.input(gpio_pin) == GPIO.LOW:
        return True
    else:
        return False




global configuration
configuration = {
    # super important configuration dictionary that has become severely bloated
    "go_reboot": True,
    "go_kill": False,
    "vfs_update_queue": []
    }


def sys_check_arm():
    if GPIO.input(GPIO_ARM) == GPIO.LOW:
        return True
    else:
        return False

def sys_check_launch():
    if GPIO.input(GPIO_LAUNCH) == GPIO.LOW:
        return True
    else:
        return False

def sys_check_cont():
    # Not-yet-implemeneted function to check for continuity in launchpad
    # will likely be removed as from pre-Epoch ignition system
    # still here because backwards compat
    return True

def sys_fire(arm, ignition):
    # Local ignition command, only for single engine fire
    if arm and ignition:
        GPIO.output(GPIO_IGNITOR, GPIO.HIGH)
        sleep(5)
        GPIO.output(GPIO_IGNITOR, GPIO.LOW)

def sys_epoch_fire(arm, ignition):
    print("firing...")

    # commands epoch to fire
    if arm and ignition:
        # fire command
        v, a, m, p = "00000", "0000", "1", "10000"
        command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
        parkes_radio.write(command.encode())


        # get confirmation
        new_command = cne_vamp_destruct(cne_receive())

        target_program = new_command[2]
        target_comp = int(str(new_command[3])[0])

        if target_comp == COMP_ID and target_program == 9:
            return 1
        else:
            return 0


def sys_file_append(target_file, data):
    # File appending tool, imported from VFS 0.3
    opened_file = open(target_file, "a")
    opened_file.write(data + "\n")
    opened_file.close()

def sys_file_init(target_file, title, id="unavailable"):
    # File creation tool, imported from VFS 0.3
    top_line = f"========== {title} ==========\n"
    bottom_line = "-" * len(top_line) + "\n"
    new_file = open(target_file, "w")
    new_file.write(top_line)
    new_file.write("Parkes Version: " + str(parkes_version) + "\n")
    new_file.write("Parkes ID: " + str(id) + "\n")
    new_file.write(bottom_line)
    new_file.write("")
    new_file.close()


def dsp_vowel_remover(word):
    # This function removes vowels from words.
    vowels, new_word, has_taken = ["a","e","i","o","u"], [], False

    for x in list(word)[::-1]:
         if x not in vowels or has_taken:
            new_word.append(x)
         else:
            has_taken = True

    to_return_word = "".join(new_word[::-1])

    if to_return_word != word:
        return to_return_word, True
    else:
        return to_return_word, False

# Parkes Error Handler 2.0
#====================PEH 2.0====================#
def dsp_error_nonfatal(code):
    top_line = "ERROR:  " + format_length(code, 8)
    current_select = False

    while True:
        if current_select == True:
            bottom_line = "|RBT| / SHUTDWN "
        else:
            bottom_line = " RBT / |SHUTDWN|"

        update_display(top_line, bottom_line)

        choose = button_input()
        if choose == "cycle":
            if current_select == True:
                current_select = False
            else:
                current_select = True

        elif choose == "select":
            if current_select == True:
                con_reboot()
                break
            elif current_select == False:
                con_shutdown()
                break

def dsp_error_fatal(code):
    # Handle fatal errors
    top_line = "ERROR:  " + format_length(code, 8)
    bottom_line = " FATAL ERROR    "

    update_display(top_line, bottom_line)
    while True:
        waiting = True

def dsp_error_warning(code):
    # Handle warning errors
    top_line = "ERROR:  " + format_length(code, 8)
    bottom_line = "   |CONTINUE|   "

    update_display(top_line, bottom_line)
    wait_select()

def dsp_error_passive(code):
    # handle system passive errors
    passive_error = code

def dsp_error_sysmess(code):
    sysmess = code

def error(e_code, data=None):
    # Parkes Error Handler 2.0 - PEH2.0
    # Full support for Parkes v.5 and upwards, with backwards compatability
    # for all versions of Parkes that support PEH1.X

    error_codes = {
        "0" : (dsp_error_nonfatal, "Non-Fatal Error"),
        "1" : (dsp_error_fatal, "Fatal Error"),
        "2" : (dsp_error_warning, "Warning"),
        "3" : (dsp_error_passive, "Passive Error"),
        "9" : (dsp_error_sysmess, "System Message")
    }

    error_type = error_codes[e_code[1]][0]

    # Error display
    if e_code[1] in error_codes.keys():
        # If error code is correct

        new_error = "- " + error_codes[e_code[1]][1] + " ("+str(e_code)+")"

        if data:
            # if data exists, add to log
            new_error += " => "
            new_error += str(data)

        # display error in consol and add to errorlog
        print(new_error)
        sys_file_append("parkes_errorlog.txt", new_error)

        #run associated error function
        error_type(e_code)

    else:
        # error code is incorrect
        error("E199", e_code)
#===============================================#

def dsp_menu(func_dict, menu_title):
    # displays menu items for user interaction
    global Configuration
    current_select = 1

    while True:
        current_func_name, current_func = func_dict[current_select]
        title = menu_title + ":"
        top_line = format_length(menu_title, 11) + format_length(str(current_select) + "/" + str(len(func_dict)),5, alignment="RIGHT")
        bottom_line = "=> " + format_length(current_func_name, 12)
        update_display(top_line, bottom_line)
        choose = button_input(True)

        if choose == "cycle":
            if current_select != len(func_dict):
                current_select += 1
            else:
                current_select = 1
        elif choose == "back":
            break

        elif choose == "select":
            current_func()


def confirm(message):
    # asks user to confirm message before continuing
    top_line = format_length(message)
    bottom_line = "      |OK|      "
    update_display(top_line, bottom_line)
    wait_select()

def format_length(input_string, length=DEFAULTLEN, remove_vowel=False, alignment="LEFT"):
    # Formats string. Default len is 16, but can be changed. Won't remove vowels unless asked to
    output_string = ""

    if len(str(input_string)) > length:
        if not remove_vowel:
            output_string = input_string[:length]

        elif remove_vowel:
            unfinished = True
            new_string = input_string
            while unfinished == True:
                result = dsp_vowel_remover(new_string)
                new_string, unfinished = result

                if len(new_string) <= length:
                    unfinished = False

            output_string = new_string

            output_string = format_length(output_string, length)

    elif len(input_string) < length:
        # Haven't reached length, so extend per alignment rules
        if alignment == "LEFT":
            output_string = input_string
            for i in range(length - len(input_string)):
                output_string += " "
        else:
            # attempt right alignment
            output_string = input_string
            for i in range(length - len(input_string)):
                output_string = " " + output_string
    else:
        output_string = input_string

    return output_string

def button_input(allow_idle=False):
    # Returns result of UI interaction
    if hot_run:
        return hardware_button_input(allow_idle)

    elif not hot_run:
        return software_button_input()

    else:
        error("E107")



def update_display(top_line, bottom_line):
    # Function takes input for 16x2 screen and displays either on hardware or software

    if hot_run:
        if len(top_line) <= DEFAULTLEN and len(bottom_line) <= DEFAULTLEN:
            send_to_display = format_length(top_line) + format_length(bottom_line)
            lcd.write_string(send_to_display)
            return 1
        else:
            send_to_display = format_length(top_line) + format_length(bottom_line)
            lcd.write_string(send_to_display)
            return 1

    elif not hot_run:
        print()
        print(" ________________")
        print("|" + str(top_line) + "|")
        print("|" + format_length(str(bottom_line), DEFAULTLEN) + "|")
        print("|________________|\n")
        return 1

    else:
        error("E107")


def hardware_button_input(allow_idle=False):
    # Input detection for flight mode
    sleep_delay = configuration["rep_delay"]
    last_interaction_time = time.time()
    #print("awaiting input...")
    while True:
        if GPIO.input(GPIO_BACK) == GPIO.LOW:
            #print("input detected: back")
            sleep(sleep_delay)
            return "back"

        if GPIO.input(GPIO_SELECT) == GPIO.LOW:
            #print("input detected: select")
            sleep(sleep_delay)
            return "select"

        if GPIO.input(GPIO_CYCLE) == GPIO.LOW:
            #print("input detected: cycle")
            sleep(sleep_delay)
            return "cycle"

        if allow_idle:
            # if idle display is allowed, check if needs to show
            if (time.time() - last_interaction_time) > IDLE_TIME:
                error("E904", "Entering idle mode...")
                con_about()
                last_interaction_time = time.time()
                error("E905", "Exiting idle mode")





def software_button_input():
    # Input detection for emulation
    new_com = input(": ")
    if new_com == "c":
        return "cycle"
    elif new_com == "b":
        return "back"
    elif new_com == "s":
        return "select"

    sleep(configuration["rep_delay"])

def hardware_update_display(display_input):
    # Checks length of top and bottom line
    # If suitable, combines and updates display
    # Else, returns error code
    top_line, bottom_line = display_input

    if len(top_line) <= DEFAULTLEN and len(bottom_line) <= DEFAULTLEN:
        send_to_display = format_length(top_line) + format_length(bottom_line)
        lcd.write_string(send_to_display)
        return 1
    else:
        error("E203")

def software_update_display(display_input):
    # Driver code for display emulation
    top_line, bottom_line = display_input
    print()
    print(" ________________")
    print("|" + str(top_line) + "|")
    print("|" + format_length(str(bottom_line), DEFAULTLEN) + "|")
    print("|________________|\n")


def num_select(message, values, cur_val=1):
    # Basic number selection UI, returns integer value AS STRING
    template, top_line = copy.copy(values), message
    current_num, builder, original = template[0], [template[0]], template
    count, has_run = 0, False

    # Pad missing spaces
    for i in range(DEFAULTLEN - len(message)):
        top_line += " "

    while True:
        for number in original:
            builder.append(number)

        # If first loop, start at the current value
        if not has_run:
            while builder[0] != cur_val:
                original.append(original.pop(0))
                builder = [original[0]]
            has_run = True
            continue


        num_list = builder[1:]
        number_list = [x for x in num_list]
        bottom_line = "|" + str(number_list.pop(0)) + "| "

        # If more than four numbers, only preview the first six
        if len(number_list) > 4:
            first_six = number_list[:6]
        else:
            for i in range(12 - (2*len(number_list))):
                bottom_line += " "

            first_six = number_list[:6]

        # Show first six elements of number list
        for element in first_six:
            bottom_line += str(element) + " "

        update_display(top_line, bottom_line)

        # look for UI interaction
        choose = button_input()
        if choose == "cycle":
            original.append(original.pop(0))
            builder = [original[0]]

        elif choose == "select":
            return bottom_line[1]

        elif choose == "back":
            # When this function is called, "!" is used to handle a
            # back button press.
            return "!"

def display_format(top, bottom, default=True):
    # Formats top and bottom line, allowing for change in default

    if default is True:
        top_line = format_length(top)
        bottom_line = format_length(bottom)

    else:
        new_len, new_vowel = default
        top_line = format_length(top, new_len, new_vowel)
        bottom_line = format_length(bottom, new_len, new_vowel)

    return top_line, bottom_line


def wait_select():
    # Waits for "select" confirmation
    while True:
        choose = button_input()

        if choose == "select":
            break

def yesno(message):
    # Basic bool select function, returns bool value
    top_line = message
    for i in range(DEFAULTLEN - len(message)):
        top_line += " "
    current_select = False
    while True:
        if current_select == True:
            bottom_line = "    |Y| / N     "
        else:
            bottom_line = "     Y / |N|    "

        update_display(top_line, bottom_line)

        choose = button_input()
        if choose == "cycle":
            # Invert current select flag
            if current_select == True:
                current_select = False
            else:
                current_select = True

        elif choose == "select":
            return current_select

        elif choose == "back":
            break



def sys_startup_animation():
    # Loading bar, will tie into actual progress soon
    count = 0

    for i in range(11):
        time_del = float((randint(1, 3)) / 10)
        filler = ""
        for i in range(count):
            filler += "="
        for i in range(10 - count):
            filler += " "
        start_string = "  |" + filler + "|  "

        update_display(format_length("PARKES v" + str(parkes_version), DEFAULTLEN), start_string)
        count += 1
        sleep(time_del)


def sys_startup():
    # Everything in here is done as part of the loading screen
    GPIO.output(GPIO_LIGHT, GPIO.HIGH)
    error("E903", "PARKES WAKEUP")
    error("E904", "Startup initiated")

    sleep(1)
    update_display(format_length("PARKES v" + str(parkes_version), DEFAULTLEN),  format_length("loading", DEFAULTLEN))
    sleep(0.4)

    # Assign ID number
    configuration["parkes_id"] = cfg_id_gen()


    sys_startup_animation()
    update_display(format_length("", DEFAULTLEN), format_length(" READY", DEFAULTLEN))
    sleep(1.2)
    GPIO.output(GPIO_LIGHT, GPIO.LOW)
    error("E905", "Startup complete")

def con_delay():
    # Config: set delay for button input recog
    global configuration
    new_val = "0." + str(num_select("SELECT DURATION:", DEFAULT_NUMSEL))
    if new_val != "0.!":
        configuration["rep_delay"] = float(new_val)

def con_beep():
    # Config: set volume for beeper
    global configuration
    new_val = str(num_select("SELECT VOLUME:", DEFAULT_NUMSEL))
    if new_val != "!":
        configuration["beep_volume"] = int(new_val)


def con_reboot():
    # Config: set reboot status
    result = yesno("SURE REBOOT?")
    if result == True:
        configuration["go_reboot"] = True
        configuration["go_kill"] = False


def con_shutdown():
    # Config: set shutdown status
    result = yesno("SURE SHUTDOWN?")
    if result == True:
        configuration["go_reboot"] = False
        configuration["go_kill"] = True


def con_about():
    # About the program - also used for idle screen
    top_line = "  PARKES v" + str(parkes_version) + "   "
    bottom_line = format_length("   novae 2021   ")
    update_display(top_line, bottom_line)
    wait_select()


def con_cursor():
    # Config: manually reset cursor
    result = yesno("RESET CURSOR")
    if result == True:
        lcd.cursor_pos = (0, 0)
        sleep(0.2)

def con_clear():
    # Config: manually clear lcd
    result = yesno("CLEAR LCD")
    if result == True:
        lcd.clear()
        sleep(0.2)

def con_display():
    # Config: display all current config values
    conf_list = [con for con in configuration.keys()]

    current = 0

    while True:
        bottom_line = ""
        current_sel = str(current+1) + "/"+str(len(configuration))
        top_line = format_length("CONFG VALS: ", DEFAULTLEN - len(current_sel)) + current_sel;

        current_con = conf_list[current]
        con_line = bottom_line + format_length(current_con + ": " + str(configuration[current_con]), DEFAULTLEN)
        update_display(top_line, con_line)
        choose = button_input()

        if choose == "cycle":
            if current != (len(conf_list) - 1):
                current += 1
            else:
                current = 0

        elif choose == "select":
            bottom_line = format_length(str(configuration[current_con]))
            update_display(top_line, bottom_line)
            wait_select()

        elif choose == "back":
            break

def con_etest():
    # Config: create false error for testing
    error_type = num_select("SET ERROR CODE:", [0,1,2,3])
    error("E"+str(error_type)+"##")

def cne_status():
    # Displays the status values for telemtry downlink
    global configuration
    cne_list = [cne for cne in configuration["telemetry"].keys()]
    if len(cne_list) == 0:
        error("E010")

    current = 0

    while True:
        bottom_line = ""
        current_sel = str(current+1) + "/"+str(len(cne_list))
        top_line = format_length("CNCT VALS: ", DEFAULTLEN - len(current_sel)) + current_sel;

        current_con = cne_list[current]
        con_line = bottom_line + format_length(current_con + ": " + str(configuration["telemetry"][current_con]), DEFAULTLEN)

        update_display(top_line, con_line)
        choose = button_input()

        if choose == "cycle":
            if current != (len(cne_list) - 1):
                current += 1
            else:
                current = 0
        elif choose == "back":
            break

def check_vamp_string(vamp):
    # Takes vamp as string and makes sure it conforms to standard

    vamp_decom = []
    for element in vamp.split("_"):
        vamp_decom = element[1:]

        if len(vamp_decom) != VAMP_STRING_STANDARD[element[0]]:
            error("E122")
            return False


        vamp_decom = element[1:]
        v, a, m, p = vamp_decom

def check_vamp_tuple(vamp):
    # Takes vamp as tuple and makes sure it conforms to standard
    for element in vamp:
        if VAMP_TUPLE_STANDARD[vamp.index(element)] != len(str(element)):
            error("E123")

def cne_open_port(user_conf=True):
    global parkes_radio
    # Opens the default port for Parkes transceiver

    parkes_radio = serial.Serial(
        port = "/dev/serial0",
        baudrate = 9600,
        parity = serial.PARITY_NONE,
        stopbits = serial.STOPBITS_ONE,
        bytesize = serial.EIGHTBITS,

        # You might need a timeout here if it doesn't work, try a timeout of 1 sec
        )
    error("E910", "opened port - parkes_radio")
    if user_conf is True:
        confirm("PORT OPENED")

def cne_send(vamp):
    # Sends command over radio
    try:
        v, a, m, p = vamp
    except:
        print(vamp)
        error("E310")
    command = "v"+str(v)+"_a"+str(a)+"_m"+str(m)+"_p"+str(p)+"\n"
    command = command.encode()
    parkes_radio.write(command)

def cne_receive(override_timeout=False, timeout_set=5):
    # Receives for command from parkes_radio - waits indefinitely
    # unless timeout is specified

    if override_timeout:
        parkes_radio.timeout = timeout_set
        data = parkes_radio.read_until()
        to_return = data
        to_return = to_return.decode()
        vamp_decom = []
        parkes_radio.timeout = None
        print(to_return)
        print(to_return.split("_"))
        for element in to_return.split("_"):
            vamp_decom.append(element[1:])
        try:
            v, a, m, p = vamp_decom
            vamp = (floor(float(v)), floor(float(a)), int(m), int(p))
            return to_return
        except:
            print(vamp_decom)
            return "timeout"

    # Listens for a vamp from Vega. Simples
    data = parkes_radio.read_until()
    to_return = data
    to_return = to_return.decode()

    return to_return


def cne_vamp_destruct(vamp):
    # Breaks vamp into tuple of values
    vamp_decom = []
    for element in vamp.split("_"):
        vamp_decom.append(element[1:])

    try:
        v, a, m, p = vamp_decom
        vamp = (floor(float(v)), floor(float(a)), int(m), int(p))
    except:
        print(vamp)
        error("E311")


    return vamp


def cne_heartbeat():
    # Threaded function to monitor connection with Vega
    configuration["telemetry"]["hb_active"] = True
    configuration["telemetry"]["hb_force_kill"] = False
    receiving = True
    heartbeat_init_vamp = (10000, 0000, 8, 00000)

    cne_send(heartbeat_init_vamp)
    hb_count = 0
    if hb_count < 0:
        error("E251")
        hb_count = 0

    error("E911", "Heartbeat loop initiated")

    # Main heartbeat loop - continues until hb_force_kill is triggered
    while configuration["telemetry"]["hb_force_kill"] == False:

        rec_string = cne_receive()
        rec_vamp = cne_vamp_destruct(rec_string)
        configuration["telemetry"]["hb_data"].append(rec_vamp)
        configuration["telemetry"]["hb_pid"] = rec_vamp[3]
        sleep(1)

        hb_count += 1
        try:
            configuration["telemetry"]["hb_sigstrn"] = (hb_count / rec_vamp[3]) * 100
        except:
            has_failed = True

    # Reset config values for heartbeat close
    configuration["telemetry"]["hb_active"] = False
    configuration["telemetry"]["hb_data"] = []
    configuration["telemetry"]["hb_sigstrn"] = 0


def cne_heartbeat_thread():
    # Initiates heartbeat in thread, thread close not yet handled
    force_kill = False
    global cne_hb_thread
    # Moves the heartbeat function into its own function
    cne_hb_thread = threading.Thread(target=cne_heartbeat)
    cne_hb_thread.start()


def cne_heartbeat_confirmation():
    # Waits for hb conf from Vega, supports timeout of 5 seconds
    rec_con = False
    while rec_con == False:
        result = cne_receive(override_timeout=True, timeout_set=5)
        if "v10000_a1000_m8_p" in str(result):
            error("E912", "Heartbeat confirmation received")
            rec_con = True
            return rec_con
        elif str(result) == "timeout":
            error("E312", "Heartbeat connection timeout: could not establish connection")
            return False


def dsp_handshake(status):
    # Displays current handshake status in a fun and easy to read way kill me please
    if status == False:
        top_line = format_length("  <|3 - HB OFF  ")
        bottom_line = format_length(" P-----/x/----V ")

        update_display(top_line, bottom_line)

    if status == True:
        top_line = format_length("  <3 - HB ON  ")
        bottom_line = format_length(" P------------V ")
        update_display(top_line, bottom_line)

        sleep(1)

        for t in range(3):
            for i in range(0, 12):
                start = ""
                for x in range(i):
                    start += "="
                start += ">"

                for y in range(12-(i+1)):
                    start += "-"
                bottom_line = format_length(" P"+start+"V ")
                top_line = format_length("<3 - HB ON")
                update_display(top_line, bottom_line)
                sleep(0.1)

        confirm("HANDSHAKE GOOD")


def cne_handshake():
    # Function to initiate connection between Vega and Parkes for heartbeat
    # support.
    global configuration
    dsp_handshake(False)
    handshake_confirmed = False

    configuration["telemetry"]["active"] = True
    sleep(3)
    # Set handshake vamp
    handshake_vamp = (10000, 1000, 8, 00000)

    # Loop to send handshake / await response
    cne_send(handshake_vamp)

    # Might need to put some sort of stopper here, in case it just steamrolls ahead
    heartbeat_conf_result =  cne_heartbeat_confirmation()
    if not heartbeat_conf_result:
        return
    error("E913", "Handshake good - entering multithread")
    dsp_handshake(True)
    cne_heartbeat_thread()

def cne_kill_heartbeat():
    # Finish the heartbeat thread
    global configuration
    parkes_radio.write("v10000_a1000_m8_p00000\n".encode())
    configuration["telemetry"]["hb_force_kill"] = True
    error("E914", "Hb_force_kill is True, joining thread...")
    cne_hb_thread.join()

def cne_vfs_updater(target, value):
    # Takes the target config to chane, and the value to set it to
    global configuration
    target_dict = {
        "beep_vol"  : "A",
        "debug_mode": "B"
    }
    command = target_dict[target] + str(value)
    configuration["vfs_update_queue"].append(command)


def cne_upload_config(params):
    # Take the current list of update params and send to Vega
    dsp_upload_config("uploading")
    command, param_len = "", len(params)
    param_count = 0
    for update in params:
        param_count += 1
        command += "|" + update
    command += "\n"
    parkes_radio.write(command.encode())
    sleep(0.5)
    confirmation = parkes_radio.read_until().decode()

    con_count, con_list = confirmation.split(".")
    if int(con_count) != param_count:
        if int(con_count) == 0:
            dsp_upload_config("total")
            error("E320")
        else:
            dsp_upload_config("partial", (con_count, str(param_count)))
            message = con_count + "/" + str(param_count) + " updates complete"
            error("E321", message)
    else:
        dsp_upload_config("complete")


def dsp_upload_config(status, data=False):
    # Moves param list to parkes_radio for upload to vega
    top_line = format_length("VFS UPDATE TOOL")
    if status == "uploading":
        bottom_line = "uploading..."
    elif status == "complete":
        bottom_line = "complete!"
    elif status == "partial":
        if data:
            con_count, param_coun = data
            fract = con_count + "/" + param_count
            bottom_line = "partial: "+ data
        else:
            bottom_line = "partial: unknown"
            error("E322")
    elif status == "total":
        bottom_line = "failed to update"

    update_display(top_line, format_length(bottom_line))



def dsp_hb_view(status):
    if status == True:
        desired_time = 10
        run_view = True
        top_line = format_length("HEARTBEAT:  LIVE")
        init_time = time.time()
        while run_view == True:

            sig = str(int(configuration["telemetry"]["hb_sigstrn"])) + "%"
            if len(sig) < 4:
                sig = " "+sig
            final_sig = "sig:"+sig

            pid = configuration["telemetry"]["hb_pid"]
            builder = ""
            for i in range(5-len(str(pid))):
                builder += "0"
            builder += str(pid)
            final_pid = "P:"+builder
            bottom_line = final_sig + " " + final_pid
            update_display(top_line, bottom_line)
            time_diff = time.time() - init_time
            sleep(0.1)
            if time_diff > 10:
                run_view = False
    elif status == False:
        confirm("HEARTBEAT DEAD")

    else:
        error("E252")


def cne_hb_view():
    if configuration["telemetry"]["hb_active"] == True:
        dsp_hb_view(True)
    else:
        dsp_hb_view(False)

def cne_hb_kill():
    if configuration["telemetry"]["hb_active"] == True:
        go_kill = yesno("KILL HRTBT?")
        if go_kill == True:
            cne_kill_heartbeat()
            confirm("HEARTBEAT DEAD")
    else:
        error("E250")

def cne_hb_menu():
    global configuration

    hb_func_dict = {
        1 : ["HB VIEW", cne_hb_view],
        2 : ["HB KILL", cne_hb_kill],
        }

    dsp_menu(hb_func_dict, "HEARTBEAT")
    # Exit to menu, don't write below here

def cne_connect():
    global configuration
    cne_open_port(False)
    cne_handshake()
    configuration["telemetry"]["connected"] = True

def cne_vfs_beep():
    new_val =str(num_select("SELECT VOLUME:", DEFAULT_NUMSEL))
    if new_val != "!":
        cne_vfs_updater("beep_vol", new_val)
        sleep(0.2)

def cne_vfs_debug():
    set_debug = yesno("SET DEBUG?")
    if set_debug:
        cne_vfs_updater("debug_mode", "True")
    else:
        cne_vfs_updater("debug_mode", "False")
    sleep(0.2)

def cne_vfs_config():

    cne_vfs_dict = {
        1 : ["BEEP", cne_vfs_beep],
        2 : ["DEBUG", cne_vfs_debug]
    }

    #cne_vfs_updater(target, value)
    dsp_menu(cne_vfs_dict, "VFS CONFIG")
    # Exit to menu, don't write below here


def cne_vfs_update():
    global configuration
    if yesno("UPDATE VFS?"):
        cne_upload_config(configuration["vfs_update_queue"])
        confirm("UPDATE COMPLETE")

def cne_vfs_compiler():
     cne_open_port(False)
     compile_vamp = (10000, 1000, 4, 00000)
     confirm("VFS LOG COMPILER")

     # Loop to send handshake / await response
     cne_send(compile_vamp)
     confirm("COMMAND SENT")


def cne_vfs_menu():
    global configuration

    vfs_config_dict = {
        1 : ["CONFIG", cne_vfs_config],
        2 : ["UPDATE", cne_vfs_update],
        3 : ["COMPILER", cne_vfs_compiler]
        }

    dsp_menu(vfs_config_dict, "VFS CONFIG")
    # Exit to menu, don't write below here

def cne_update_cleanup():
    os.system("rm " + update_folder)

def cne_update():
    global configuration

    update_folder = "update_tool"
    update_target = "/" + update_folder + "/parkes_master.py"
    grab_command = "scp jackwoodman@corvette.local:/Users/jackwoodman/Desktop/novae/parkes_master.py /home/pi/" + update_folder

    top_line = format_length("PGS UPDATE TOOL")
    bottom_line = format_length("finding update..")
    update_display(top_line, bottom_line)
    # create temporary folder
    os.system("mkdir " + update_folder)

    try:
        os.system(grab_command)

    except:
        bottom_line = "search failed!  "
        error("E352", "update failed - could not connect to Corvette")

        update_display(top_line, bottom_line)
        wait_select()
        return

    # check if same
    try:
        comparison = filecmp.cmp("parkes_master.py", update_target)
    except:
        error("E350", "PGS update comparison failed")

    # check if update is required or not
    if comparison:
        update_display(top_line, bottom_line)
        bottom_line = "no updates!"
        error("E351", "no PGS updates found")
        wait_select()
        cne_update_cleanup()
        return

    else:
        update_display(top_line, bottom_line)
        bottom_line = "update found!"
        wait_select()

        bottom_line = "updating..."

        # copy new file across to old file
        try:
            os.system("cp -f parkes_master.py " + update_target)

        except:
            bottom_line = "update failed!  "
            error("E352", "update failed - could not update file")
            update_display(top_line, bottom_line)
            wait_select()
            cne_update_cleanup()
            return

    # check the update has worked
    if not filecmp.cmp("parkes_master.py", update_target):
        bottom_line = "update failed!  "
        error("E353", "update failed - update corruption detected")
        update_display(top_line, bottom_line)
        wait_select()
        cne_update_cleanup()
        return

    bottom_line = "update success! "
    update_display(top_line, bottom_line)
    wait_select()

    bottom_line = format_length("cleaning up...")
    update_display(top_line, bottom_line)


    os.system("rm " + update_folder)
    sleep(4)

    bottom_line = "reboot to finish"
    update_display(top_line, bottom_line)
    wait_select()

    # runs recursive iteration of self, to work until next full shutdown
    os.system("python3 parkes_master.py")



def sys_connect():
    global configuration

    connect_func_dict = {
        1 : ["HANDSHAKE", cne_connect],
        2 : ["STATUS", cne_status],
        3 : ["HEARTBEAT", cne_hb_menu],
        4 : ["VFS CONFIG", cne_vfs_menu],
        5 : ["PORT OPEN", cne_open_port]
        }

    dsp_menu(connect_func_dict, "CONNECT")
    # Exit to menu, don't write below here

def sys_debug():
    global configuration

    debug_func_dict = {
        1 : ["HARDWARE DIAG", bug_hardware_diag],
        2 : ["HOTRUN SET", bug_hotrun]
        }

    dsp_menu(debug_func_dict, "DEBUG")
        # Exit to menu, don't write below here
    # Exit to menu, don't write below here

def sys_config():
    # Main: select config function
    global configuration

    config_func_dict = {
        1 : ["INPUT DELAY", con_delay],
        2 : ["BEEP", con_beep],
        3 : ["CURSOR RESET", con_cursor],
        4 : ["LCD CLEAR", con_clear],
        5 : ["CONFIG VALUES", con_display],
        6 : ["REBOOT", con_reboot],
        7 : ["ERROR TEST", con_etest],
        8 : ["SHUTDOWN", con_shutdown],
        9 : ["ABOUT", con_about],
        10 : ["DEBUG", sys_debug]
        }

    dsp_menu(config_func_dict, "CONFIG")
        # Exit to menu, don't write below here
    # Exit to menu, don't write below here







def lch_hotfire():
    # Used for testing engines without the preflight tests

    sure_go = yesno("RUN HOTFIRE?")
    if not sure_go:
        return
    error("E290")
    top_line = format_length("HOTFIRE ACTIVE")
    bottom_line = "   |CONTINUE|   "
    update_display(top_line, bottom_line)
    wait_select()
    sleep(2)

    top_line = format_length("DISARMED")
    bottom_line = format_length("key to arm...")
    hold, armed = True, False


    while hold:
        update_display(top_line, bottom_line)
        if sys_check_arm():
            top_line = format_length("ARMED!")
            bottom_line = format_length("ready...")
            armed = True
        else:
            top_line = format_length("DISARMED")
            bottom_line = format_length("key to arm...")
            armed = False

        if armed and sys_check_launch():
            hold = False
        sleep(0.2)

    top_line = format_length("AUTOSEQUENCE")
    bottom_line = format_length("-----active-----")
    update_display(top_line, bottom_line)

    sleep(4)
    # COUNTDOWN
    continue_launch = True
    for count in range(11):
        current = str(10 - count).zfill(2)
        top_line = format_length("    COUNTDOWN   ")
        bottom_line = format_length("      |"+current+"|      ")
        update_display(top_line, bottom_line)
        sleep(0.95)
        if not sys_check_arm():
            top_line, bottom_line =  display_format("DISARMED", "ending countdown")
            update_display(top_line, bottom_line)
            sleep(3)
            continue_launch = False
            break

    if continue_launch:
        sys_fire(sys_check_arm(), True)
        top_line, bottom_line =  display_format("    COUNTDOWN   ", "    ignition    ")
        sleep(10)

def lch_epoch_fire():
    cne_open_port()
    sure_go = yesno("HOTFIRE EPOCH?")
    if not sure_go:
        return

    sleep(2)

    top_line = format_length("DISARMED")
    bottom_line = format_length("key to arm...")
    hold, armed = True, False


    while hold:
        update_display(top_line, bottom_line)
        if sys_check_arm() and sys_check_status(GPIO_MISSILE):
            GPIO.output(GPIO_LIGHT, GPIO.HIGH)
            top_line = format_length("ARMED!")
            bottom_line = format_length("ready...")

            armed = True
        else:
            GPIO.output(GPIO_LIGHT, GPIO.LOW)
            top_line = format_length("DISARMED")
            bottom_line = format_length("key to arm...")
            armed = False

        if armed and sys_check_launch():
            hold = False
        sleep(0.2)

    top_line = format_length("AUTOSEQUENCE")
    bottom_line = format_length("-----active-----")
    update_display(top_line, bottom_line)

    sleep(4)
    # COUNTDOWN
    continue_launch = True
    for count in range(11):
        current = str(10 - count).zfill(2)
        top_line = format_length("    COUNTDOWN   ")
        bottom_line = format_length("      |"+current+"|      ")
        update_display(top_line, bottom_line)
        sleep(0.95)
        if not sys_check_arm():
            top_line, bottom_line =  display_format("DISARMED", "ending countdown")
            update_display(top_line, bottom_line)
            sleep(3)
            continue_launch = False
            break

    if continue_launch:
        com_res = sys_epoch_fire(sys_check_arm(), True)

        if com_res == 1:
            top_line, bottom_line =  display_format("EPOCH CONFIRM", "    ignition    ")
            update_display(top_line, bottom_line)
            wait_select()








def lch_flight_configure():
    # all functions required to prepare for flight
    GPIO.output(GPIO_IGNITOR, GPIO.LOW)

    return True


def lch_preflight():
    # Parkes onboard checks

    # Check configured for flight
    if not lch_flight_configure():
        return "lch_flight_configure() failed"

    # Check system armed
    if not sys_check_arm():
        return True
        #return "disarm detected"

    # Check ignition continuity
    if not sys_check_cont():
        return "discontinuity in ignition loop detected"

    # Check UART port is open
    try:
        if not parkes_radio.is_open():
            return "parkes_radio port is closed"
    except:
        return "parkes_radio port has not been initialised"

    # Checks heartbeat has been disabled
    if configuration["telemetry"]["hb_active"] == True:
        return "heartbeat is active"

    # Check system armed
    if not sys_check_arm():
        return True
        #return "disarm detected"

    # Check ignition pin is LOW
    if not GPIO.input(GPIO_IGNITOR):
        return "ignition pin was not pulled low"

    return True


def lch_quick_check():
    # This gets run during the countdown

    # Check continuity
    if not sys_check_cont():
        return "discontinuity in ignition loop detected"

    # Check system armed
    if not sys_check_arm():
        return "disarm detected"

    return True


def lch_countdown():
    # Local fire command - used when Parkes is commanding a local ignition only
    sleep(2)
    continue_launch = True

    for second in range(11):
        current = str(10 - count).zfill(2)
        top_line = format_length("    COUNTDOWN   ")
        bottom_line = format_length("      |"+current+"|      ")
        update_display(top_line, bottom_line)

        qc_results = lch_quick_check()
        if not qc_results:
            continue_launch = False
            error("E295", qc_results)
            sleep(3)
            break
        sleep(0.95)
        qc_results = lch_quick_check()
        if not qc_results:
            continue_launch = False
            error("E295", qc_results)
            sleep(3)
            break


    if continue_launch:
        # Passed launch checks, proceed with ignition command
        sys_fire(sys_check_arm(), True)

        top_line = format_length("    COUNTDOWN   ")
        bottom_line = format_length("    ignition    ")
        error("E999", "ignition")
        wait_select()

def lch_launch_program():
    sure_go = yesno("COMMIT LAUNCH?")
    if not sure_go:
        return

    # Ask for flight configuration and preflight checks
    pf_results = lch_preflight()

    if pf_results != True:
        error("E291", pf_results)
        return

    if vega_in_loop:
        # Time to ask Vega to launch_poll
        v, a, m, p = "00000", "0000", "0", "00000"
        command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
        parkes_radio.write(command.encode())

        vega_confirmed = cne_vamp_destruct(cne_receive())
        if vega_confirmed[2] != 0:
            error("E294", str(vega_confirmed))
            return

        sleep(0.4)
        vega_poll_results = cne_vamp_destruct(cne_receive())

        if vega_poll_results[3] == "21111":
            error("E292", str(vega_poll_results))
            return

        elif vega_poll_results[3] == "20000":
            error("E990", "vega is configured for flight")

        else:
            error("E293", str(vega_poll_results))
            return


    # Time to ask Epoch to launch_poll
    v, a, m, p = "00000", "0000", "0", "10000"
    command = "v"+v+"_a"+a+"_m"+m+"_p"+p+"\n"
    parkes_radio.write(command.encode())

    epoch_poll_results = cne_vamp_destruct(cne_receive())

    if vega_poll_results[3] == "11111":
        error("E298", str(vega_poll_results))
        return

    elif vega_poll_results[3] == "20000":
        error("E990", "Epoch is configured for flight")

    else:
        error("E296", str(epoch_poll_results))
        return

    sleep(2)
    error("E998", "launch countdown commit")

    lch_countdown()

def lch_force_launch():
    # Forces launch, skipping prep and arm phase. Used for testing only. May be removed from use
    cne_open_port(False)
    error("E210")
    force_vamp = (10000, 1000, 2, 00000)
    confirm("FORCE CMMND SENT")

    # Loop to send handshake / await response
    cne_send(force_vamp)
    sleep(0.2)
    lch_downlink()

def lch_loop():
    # Forces launch, skipping prep and arm phase. Used for testing only. May be removed from use
    cne_open_port(False)
    error("E210")
    force_vamp = (10000, 1000, 3, 00000)
    confirm("FORCE LOOP SENT")

    # Loop to send handshake / await response
    cne_send(force_vamp)
    sleep(0.2)
    lch_downlink()

def lch_arm():
    # arms vega for flight
    cne_open_port(False)
    arm_vamp = (10000, 1000, 0, 00000)
    # Loop to send handshake / await response
    cne_send(arm_vamp)

def lch_downlink():
    flight_downlink = []
    modetype = {
        0 : " VEGA IDLE      ",
        1 : " ARMED & READY  ",
        2 : " POWERED FLIGHT ",
        3 : " UNPWRED FLIGHT ",
        4 : " BALLISTIC DESC ",
        5 : " PARACHUTE DESC ",
        6 : " LANDED & SAFE  ",
        7 : " ERROR / UNKNWN "
        }
    # Designed as a lightweight function to display data directly
    while True:
        incoming = parkes_radio.read_until()
        try:
            v,a,m,p = cne_vamp_destruct(incoming.decode())

            update_display(modetype[m], "V:"+str(v)+"  A:"+str(a)+"m")
        except:
            error("E311", incoming.decode())


def sys_launch():

    launch_func_dict = {
        1 : ["AUTOSEQUENCE", lch_launch_program],
        2 : ["ARM VEGA", lch_arm],
        3 : ["LAUNCH", lch_force_launch],
        4 : ["HOTFIRE", lch_hotfire],
        5 : ["DOWNLINK", lch_downlink],
        6 : ["LCH LOOP", lch_loop],
        7 : ["EPOCH FIRE", lch_epoch_fire]
        }

    current_select = 1
    dsp_menu(launch_func_dict, "LAUNCH")
        # Exit to menu, don't write below here


def sys_main_menu():
    # Parkes: main menu selection
    global configuration
    title = "PARKES v"+str(parkes_version)

    main_func_dict = {
        1 : ["CONFIG", sys_config],
        2 : ["CONNECT", sys_connect],
        3 : ["LAUNCH", sys_launch]
        }
    while True:
        if configuration["go_reboot"] or configuration["go_kill"]:
            error("E399", "go_kill / go_reboot detected")
            return
        else:
            dsp_menu(main_func_dict, title)

def sys_shutdown_process():
    # Function to handle all the pre-shutdown cleanup

    sleep(1)
    top_line, bottom_line = "PARKES v" + str(parkes_version) + "     ", format_length("shutting down", DEFAULTLEN)
    update_display(top_line, bottom_line)
    error("E900", "Shutdown process initiated")
    sleep(4)

    top_line, bottom_line = format_length(" ", DEFAULTLEN), format_length(" done", DEFAULTLEN)
    error("E901", "Shutdown process complete")
    update_display(top_line, bottom_line)
    sleep(2)

def sys_type_get(newval):
    # Get variable type, return string output
    try:
        int(newval)
        return "int"
    except ValueError:
        try:
            float(newval)

            return "float"
        except ValueError:
            if newval != "True\n" and newval != "False\n":
                return "string"

            else:
                return "bool"

def sys_startup_tests(ex_value, config_vals):
    # Startup test functions, don't fuck with these

    if len(config_vals) != ex_value:
        return False, "c_v_failure"

    if parkes_version > configuration["parkes_vers"]:
        return False, "c_f_failure"

    if parkes_version < configuration["parkes_vers"]:
        return False, "p_v_failure"

    return True, "tests_passed"

# Parkes Configuration Interpreter 2.0 - PCI2.0c
def cfg_type_set(definition):
    # function takes string description of desired type and converts
    # input to required type

    def_type = sys_type_get(definition)

    if def_type == "int":
        return int(definition)

    elif def_type == "bool":
        if definition == "True":
            return True
        else:
            return False

    elif def_type == "float":
        return float(definition)

    elif def_type == "string":
        return str(definition)[:-1]

def cfg_set_value(content):
    # recevies set value command and passes value name and res to type_set
    global configuration
    value = content[1:]

    key, definition = value.split("=")
    configuration[key] = cfg_type_set(definition)


def cfg_homedir(data):
    # allow config to set new home dir
    global configuration
    home_dir = data[4:]

    configuration["home_dir"] = home_dir

def cfg_telemetry(data):
    # telem configuration functions
    global configuration

    if data == "init":
        configuration["telemetry"] = {}

    elif "set" in data:
        if "default" in data:
            configuration["telemetry"] = {"active": False, "connected": False, "sig_strength": 0, "hb_active": False, "hb_data":[], "hb_sigstrn":0, "hb_force_kill": False}

def cfg_errlog(data):
    # error log configuration functions
    global configuration
    if data == "init":
        sys_file_init("parkes_errorlog.txt", "PARKES ERROR LOG", configuration["parkes_id"])

    elif data == "clear":
        new_file = open("parkes_errorlog.txt", "w")
        new_file.close()

def cfg_exval(data):
    # handles value set with expected value
    global expected_value
    if data == "init":
        expected_value = 0

    elif data[:4] == "set=":
        try:
            value = int(data[4:])
        except:
            error("E102", value)
    else:
        error("E103", data)

def cfg_run_command(target, command):
    command_funcs = {
        "home_dir" : cfg_homedir,
        "telemetry": cfg_telemetry,
        "error_log": cfg_errlog,
        "expected_value": cfg_exval
    }

    command_funcs[target](command)

def cfg_startuptest_modify(set_to=False):
    global run_startup_test
    run_startup_test = set_to

    if not set_to:
        error("E202")

def cfg_include_vega():
    global vega_in_loop
    vega_in_loop = True


def cfg_kill_setup():
    return

def cfg_id_gen():
    # produces random ID_LEN-digit ID for file generation
    id = ""

    for digit in range(ID_LEN):
        # create random digit from 0-9
        new_digit = str(randint(0,9))
        id += new_digit

    return id



def sys_config_interpreter(config_file):
    # func accepts configuration file and interprets it

    # list of line identifiers
    identifier_type = {
        "!" : "value",
        "$" : "command"
    }

    #possible configuration commands
    config_commands = {
        "ignore_startup_tests" : cfg_startuptest_modify,
        "end_setup" : cfg_kill_setup,
        "expect_vega" : cfg_include_vega
    }

    config_lines = config_file.readlines()

    for entry in config_lines:

        if entry[0] not in identifier_type.keys():
            # could not identify identifier
            continue

        identifier, content = entry[0], entry[1:]

        if identifier_type[identifier] == "value":
            # pass detected value set off to value set func
            cfg_set_value(content)

        elif identifier_type[identifier] == "command":
            # command detected

            if "." in content:
                # unique command detected, pass to command runner
                target, command = content.split(".")

                cfg_run_command(target, command.rstrip())

            else:
                # predefined command detected, run command
                command = content.rstrip()
                config_commands[command]()

def sys_startup_test():
    # function to run startup tests as required
    startup_errors = {
        "p_v_failure"  :  "E105",
        "c_v_failure"  :  "E103",
        "c_f_failure"  :  "E106"
        }

    passed_test, reason = sys_startup_tests(expected_value, configuration)

    if passed_test and reason in startup_errors.keys():
        # error passing startup tests, log error and reason
        error(startup_errors[reason], "startup_error: " + reason)
    else:
        # unknown error found
        error("E101")

def bug_hotrun():
    # Allows for on the fly switching between hardware and software UI
    global hot_run

    hot_run = yesno("SET HOTRUN?")

    confirm("CONFIRM OK")
    error("E333", "hotrun set - " + str(hot_run))


def bug_hardware_inp(input_name, input_pin):
    # tests individual hardware components\
    display_off = "---[ ]----------"
    display_on = "---[x]----------"
    break_loop, has_changed = False, False

    topline = "testing: " + format_length(input_name)
    bottomline = display_off
    start_time = 0
    hold_time = 3
    update_display(topline, bottomline)

    while not break_loop:

        if sys_check_status(input_pin):
            # if input has been activated
            if not has_changed:
                # start of new unique input press, begin timer
                bottomline = display_on
                start_time = time.time()
                update_display(topline, bottomline)
                has_changed = True

            if (time.time() - start_time) > hold_time:
                # checks if given input has been held for required time
                break_loop = True

        else:
            # input is not detected
            if has_changed:
                # input is flipping from true to false, update display
                start_time = 0
                bottomline = display_off
                update_display(topline, bottomline)
                has_changed = False

def bug_hardware_out(output_name, output_pin):
    # tests outputs of given lights
    topline = "testing: " + format_length(output_name)
    display_off = "---[ ]----------"
    display_on = "---[x]----------"
    bottomline = display_off

    update_display(topline, bottomline)
    seco, counter, loop_extend = 0, 1, 10

    # flip high and low, wait 2 seconds
    sleep(1)
    GPIO.output(output_pin, GPIO.HIGH)
    bottomline = display_on
    update_display(topline, bottomline)
    sleep(1)
    GPIO.output(output_pin, GPIO.LOW)
    bottomline = display_off
    update_display(topline, bottomline)
    sleep(2)


    while counter > 0:
        # loop that flips output high and low with reduced delay

        GPIO.output(output_pin, GPIO.HIGH)
        bottomline = display_on
        update_display(topline, bottomline)
        sleep(counter)

        GPIO.output(output_pin, GPIO.LOW)
        bottomline = display_off
        update_display(topline, bottomline)
        sleep(counter)

        counter -= 0.1

        if seco < loop_extend and counter < 0.1:
            # extends loop for loop_extend iterations
            counter += 0.1
            seco += 1




def bug_hardware_diag():
    # used to loop through and test hardware

    hardware_input = {
        "missile" : GPIO_MISSILE,
        "key"     : GPIO_ARM,
        "launch"  : GPIO_LAUNCH,
        "back"    : GPIO_BACK,
        "select"  : GPIO_SELECT,
        "cycle"   : GPIO_CYCLE
    }

    hardware_output = {
        "light"   : GPIO_LIGHT
    }

    confirm("HARDWARE DIAG")
    confirm("testing input...")

    for input in hardware_input.keys():
        # test all hardware inputs
        bug_hardware_inp(input, hardware_input[input])
        sleep(1)

    confirm("testing output...")

    for output in hardware_output.keys():
        # test all hardware outputs
        bug_hardware_out(output, hardware_output[output])
        sleep(1)

    confirm("DIAG COMPLETE")

# Main running loop
while configuration["go_reboot"] and not configuration["go_kill"]:
    global run_startup_test
    global exptected_value
    global vega_in_loop

    run_startup_test, expected_value, configuration["go_reboot"], vega_in_loop = True, 0, False, False
    config_file = open("/home/pi/parkes_config.txt", "r")

    # run startup functions and setup processes
    sys_startup()

    # pass config file to file interpreter to complete config
    sys_config_interpreter(config_file)

    # run startup tests if required
    if run_startup_test:
        sys_startup_test()

    config_file.close()

    lcd.clear()
    sys_main_menu()


# If we're here, we've left the running loop. Time to clean up.
sys_shutdown_process()
lcd.clear()

# clean shutdown, disconnects SSH and prevents SD corruption
from subprocess import call
call("sudo poweroff", shell=True)
