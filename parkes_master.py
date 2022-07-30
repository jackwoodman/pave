# pgs

# requires parkes_edecode.py (1.4 and up)
# requires pave_comms.py (beta 1 and up)
# requires pave_file.py (beta 1 and up)

'''
    ==========================================================
    Parkes Ground Software, version 0.6.5
    Copyright (C) 2022 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    ==========================================================
'''

import os
import time
import copy
import pave
import random
import serial
import filecmp
import threading
from math import floor
from time import sleep
import RPi.GPIO as GPIO
from RPLCD import CharLCD
from parkes_edecode import error_decoder



# hot_run defines whether Parkes will run using hardware or simulation.
global hot_run
hot_run = True
# tested keeps track of if the current version has been live tested
tested = True
parkes_version = 0.6
internal_version = "0.6"


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
GPIO_LAMP = 36

DEFAULT_NUMSEL = [1, 2, 3, 4, 5, 6, 7, 8, 9]
VAMP_STRING_STANDARD = {"v":5, "a":4, "m": 1, "p":5}
VAMP_TUPLE_STANDARD = {0:5, 1:4, 2:1 , 3:5}


global configuration
configuration = {
    # super important configuration dictionary that has become severely bloated
    "go_reboot": True,
    "go_kill": False,
    "boot_time": time.time(),
    "vfs_update_queue": [],
    "internal_vers" : internal_version
    }

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

# Defining Hardware Output
GPIO.setup(GPIO_IGNITOR, GPIO.OUT) # Ignition Output - GPIO 18
GPIO.setup(GPIO_LIGHT, GPIO.OUT) # Light  - GPIO 17
GPIO.setup(GPIO_LAMP, GPIO.OUT) # Notification Lamp Output - GPIO 16


# System Functions

def sys_main_status():
    # checks if shutdown flags are true, used within function loops
    reboot, kill = configuration["go_reboot"], configuration["go_kill"]

    if (reboot and not kill):
        return "REBOOT"

    elif (not reboot and kill):
        return "KILL"

    else:
        return "CONTINUE"


def sys_set_output(gpio_pin, status):
    # set output status
    GPIO_SET = GPIO.HIGH if status else GPIO.LOW
    GPIO.output(gpio_pin, GPIO_SET)


def sys_check_status(gpio_pin):
    # check if input pin is pulled low or not
    return (GPIO.input(gpio_pin) == GPIO.LOW)


def sys_status_graphic(gpio_pin):
    # return graphic to match gpio status
    ON, OFF = ["X", " "]
    return (ON if sys_check_status(gpio_pin) else OFF)


def sys_check_cont():
    # originally from the days where parkes controlled ignition instead of
    # epoch. keeping here incase I work out how to do continuity check
    # with epoch - don't remove, as preflight checks poll this func
    continuity = True
    return continuity

def sys_fire(arm, ignition):
    # Local ignition command, only for single engine fire
    if (arm and ignition):
        GPIO.output(GPIO_IGNITOR, GPIO.HIGH)
        sleep(configuration["ignition_duration"])
        GPIO.output(GPIO_IGNITOR, GPIO.LOW)


def sys_epoch_test(arm, ignition, amount):
    # commands epoch to fire
    if (arm and ignition):
        # fire command
        reply = {
            "single" : 30000,
            "all"    : 20000
        }

        # send fire commmand
        vamp = (00000, 2000, 1, reply[amount])
        pave.comms.send(vamp, parkes_radio)

        # get confirmation
        final_command = pave.comms.receive(parkes_radio, timeout=True, timeout_duration=5)

        if str(final_command) == "timeout":
            return 2


        target_program = final_command[2]
        target_comp = int(str(final_command[3])[0])

        if (target_comp == COMP_ID and target_program == 9):
            return 1
        else:
            # epoch isn't ok to fire for whatever reason
            # TO-DO: sort reason from reason
            return 0

def sys_epoch_fire(arm, ignition):

    # commands epoch to fire
    if (arm and ignition):
        # fire command
        fire_epoch = (10101, 2000, 1, 10000)
        pave.comms.send(fire_epoch, parkes_radio)

        # get confirmation
        final_command = pave.comms.receive(parkes_radio, timeout=True, timeout_duration=5)

        if (str(final_command) == "timeout"):
            return 2

        target_program = get_vamp(final_command, "m")
        target_comp = int(str(get_vamp(final_command, "p"))[0])
        confirmation_code = get_vamp(final_command, "v")

        if (target_comp == COMP_ID and target_program == 9):
            if (confirmation_code != 10101):
                return 5
            return 1
        else:
            # epoch isn't ok to fire for whatever reason
            # TO-DO: sort reason from reason
            print("Final Command ="+str(final_command))
            print("Target Program =" +str(target_program))
            print("Target Computer ="+str(target_comp))
            print("Computer ID ="+str(COMP_ID))
            return 0
    else:
        # parkes triggered last minute abort
        return 3

    # unknown failure
    return 4

def dsp_scroll_tool(top_text, bottom_text):
    # allows to scroll through bottom text on display
    bottom_text += "  "
    current_position = -1

    while (True):
        last_input = button_input()

        if (last_input == "cycle" or last_input == "select"):
            if (current_position >= len(bottom_text) - 1):
                current_position = 0
            else:
                if (last_input == "cycle"):
                    current_position += 2
                elif (last_input == "select"):
                    current_position += 1

            top_line = top_text +str(current_position+1)+"/"+str(len(bottom_text)-2)
            bottom_line = bottom_text[current_position:] + bottom_text[:current_position]
            update_display(top_line, bottom_line)
        elif (last_input == "back"):
            break

def cne_epoch_menu():
    global configuration

    epoch_functions = {
        1 : ["TEST ALL", epc_test_all],
        2 : ["TEST SINGLE", epc_test_single],
        3 : ["ECHO", epc_echo],
        4 : ["SHUTDOWN", epc_shutdown]
        }

    dsp_menu(epoch_functions, "EPOCH FUNCS")

def epc_shutdown():
    # command epoch to shut down
    epc_command(6)

def epc_test_all():
    # send fireall (test) command to epoch
    epc_command(2)
    confirm("TESTING...")

    # get confirmation
    new_command = pave.comms.receive(parkes_radio, timeout=True, timeout_duration=25)

    if str(new_command) == "timeout":
        error("E264")
    else:
        confirm("TEST CONFIRMED")

def epc_command(command_id):
    # allowed commands
    accepted = [0, 1, 2, 3, 4, 5, 6]
    # open port if required
    if not (configuration["telemetry"]["port_open"]):
        cne_open_port(False)


    # check command is actually allowed
    if (command_id not in accepted):
        error("E268", f"tried command: {command_id}", True)
        return


    # format vamp with required command_id and send
    epc_com = (00000, 2000, command_id, 10000)
    pave.comms.send(epc_com, parkes_radio)
    error("E916", f"Sent command: {command_id}", True)

def epc_test_single():
    # send single fire command to epoch
    epc_command(3)

    confirm("TESTING...")
    # get confirmation
    new_command = pave.comms.receive(parkes_radio, timeout=True, timeout_duration=8)
    if str(new_command) == "timeout":
        error("E262")
    else:
        confirm("TEST CONFIRMED")

def epc_echo():
    # send echo command to epoch
    epc_command(0)

    # get confirmation
    new_command = pave.comms.receive(parkes_radio, timeout=True, timeout_duration=5)
    if str(new_command) == "timeout":
        error("E266", "unable to confirm test command received")
    else:
        error("E915")



def dsp_vowel_remover(word):
    # This function removes vowels from words.
    vowels, new_word, has_taken = ["a","e","i","o","u"], [], False

    for x in list(word)[::-1]:
         if (x not in vowels or has_taken):
            new_word.append(x)
         else:
            has_taken = True

    to_return_word = "".join(new_word[::-1])

    return to_return_word, (to_return_word != word)

# Parkes Error Handler 2.0
#====================PEH 2.0====================#
def dsp_error_nonfatal(code):
    reboot_txt, shutdown_txt ="|RBT| / SHUTDWN ",  " RBT / |SHUTDWN|"
    top_line = "ERROR:  " + format_length(code, 8)
    current_select = False

    while True:
        bottom_line = (reboot_txt if current_select else shutdown_txt)
        update_display(top_line, bottom_line)

        choose = button_input()

        if choose == "cycle":
            # toggle variable
            current_select ^= True

        elif choose == "select":
            # use appropriate shutdown/reboot function
            (con_reboot if current_select else con_shutdown)()
            break;

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

def error(e_code, data=True, add_data=False):
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

    try:
        # get function associated with this type of error
        error_type = error_codes[e_code[1]][0]
    except:
        # ecode isn't correct, input must have been wrong
        error("E199", data=e_code, add_data=True)

    # Error display
    if e_code[1] in error_codes.keys():
        # If error code is correct
        code = e_code[1]
        max_error_len = 14

        # light error processing lamp
        GPIO.output(GPIO_LAMP, GPIO.HIGH)
        error_start = error_codes[code][1]
        new_error = "- " + error_start.ljust(max_error_len, " ") + " ("+str(e_code)+")"

        if (data):
            # if data exists, add to log
            new_error += " => "
            error_def = error_decoder(e_code[1:])
            new_error += str(error_def)

            # request to add the data param to the errotyul;r readout
            if (add_data == True):
                new_error += " => " + str(data)



        # display error in console and add to errorlog
        print(new_error)
        pave.file.append("errorlog.txt", new_error)

        #run associated error function
        error_type(e_code)

        # kill lamp
        GPIO.output(GPIO_LAMP, GPIO.LOW)

    else:
        # error code is incorrect
        error("E199", data=e_code, add_data=True)
#===============================================#

def dsp_menu(func_dict, menu_title, allow_kill=False):
    # displays menu items for user interaction
    global Configuration
    current_select = 1

    # selection loop
    while True:

        # get function address and name for current index
        if current_select in func_dict:
            current_func_name, current_func = func_dict[current_select]

        else:
            # this shouldn't occur in normal use, only if I forget to add index
            current_select = (1 if current_select == len(func_dict) else current_select + 1)

        # display menu status

        top_line = format_length(menu_title, 11) + format_length(str(current_select) + "/" + str(len(func_dict)),5, alignment="RIGHT")
        bottom_line = "=> " + format_length(current_func_name, 12)
        update_display(top_line, bottom_line)

        # get user input for selection
        choose = button_input(True)

        if choose == "cycle":
            current_select = (1 if current_select == len(func_dict) else current_select + 1)

        elif choose == "back":
            break

        elif choose == "select":
            current_func()

        # check if need to exit for kill reasons
        if (allow_kill and sys_main_status() == "KILL"):
            break

# General Functions
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

def button_input(allow_idle=False, slowdown=False):
    # Returns result of UI interaction
    if hot_run:
        return hardware_button_input(allow_idle)

    elif not hot_run:
        return software_button_input()

    else:
        error("E107")



def update_display(top_line, bottom_line, force_hotrun=False):
    # Function takes input for 16x2 screen and displays either on hardware or software

    if hot_run or force_hotrun:
        if len(top_line) <= DEFAULTLEN and len(bottom_line) <= DEFAULTLEN:
            send_to_display = format_length(top_line) + format_length(bottom_line)
            lcd.write_string(send_to_display)
            return 1
        else:
            send_to_display = format_length(top_line) + format_length(bottom_line)
            lcd.write_string(send_to_display)
            return 1

    elif not hot_run:
        update_display(format_length("-|   HOTRUN   |-"), format_length("-|  DISABLED  |-"), force_hotrun=True)
        t ={format_length(str(bottom_line), DEFAULTLEN)}
        print("")
        print(" ________________")
        print(f"|{str(top_line)}|        ({sys_status_graphic(GPIO_MISSILE)}) ({sys_status_graphic(GPIO_ARM)})")
        print(f"|{t}|")
        print("|________________|\n")
        return 1

    else:
        # issue with hotrun STATUS
        error("E107")


def hardware_button_input(allow_idle=False, slowdown=False):
    # Input detection for flight mode
    sleep_delay = (configuration["rep_delay"] if not (slowdown) else (2))

    last_interaction_time = time.time()
    while True:
        if (GPIO.input(GPIO_BACK) == GPIO.LOW):
            sleep(sleep_delay)
            return "back"

        if (GPIO.input(GPIO_SELECT) == GPIO.LOW):
            sleep(sleep_delay)
            return "select"

        if (GPIO.input(GPIO_CYCLE) == GPIO.LOW):
            sleep(sleep_delay)
            return "cycle"

        if (allow_idle):
            # if idle display is allowed, check if needs to show
            if (time.time() - last_interaction_time) > IDLE_TIME:
                error("E906", "Entering idle mode...")
                con_about()
                last_interaction_time = time.time()
                error("E907", "Exiting idle mode")


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
        error("E203", "Hardware display update error")

def software_update_display(display_input):
    # Driver code for display emulation
    top_line, bottom_line = display_input
    print()
    print(" ________________")
    print("|" + str(top_line) + "|")
    print("|" + format_length(str(bottom_line), DEFAULTLEN) + "|")
    print("|________________|\n")


def num_select(message, values, default_val=1):
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
            while builder[0] != default_val:
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
        # normal length format
        top_line = format_length(top)
        bottom_line = format_length(bottom)

    else:
        # allow reduction through extreme methods
        new_len, new_vowel = default
        top_line = format_length(top, new_len, new_vowel)
        bottom_line = format_length(bottom, new_len, new_vowel)

    return top_line, bottom_line


def wait_select(slowdown=False):
    # Waits for "select" confirmation
    while True:
        choose = button_input()

        if choose == "select":
            break

        if slowdown:
            sleep(1)

def yesno(message):
    # Basic bool select function, returns bool value
    top_line = message
    yes, no = "    |Y| / N     ", "     Y / |N|    "
    for i in range(DEFAULTLEN - len(message)):
        top_line += " "

    current_select = False
    while True:
        bottom_line = (yes if current_select else no)
        update_display(top_line, bottom_line)

        choose = button_input()

        if choose == "cycle":
            # Invert current select flag
            current_select ^= True

        elif choose == "select":
            return current_select

        elif choose == "back":
            break


def sys_parkes_intro():
    # quick animation to spice things up

    title = "PARKES"
    name = "J.Woodman"
    MAX = 5
    MIN = 3
    top_line = 5*" " + title + 5*" "
    # waves
    for go in range(MIN):
        place = 0
        # bottom line
        b_middle = ""

        # if second iteration (go=1) show vers
        if (go == 2):
            b_middle = format_length(internal_version, length=6)
            last = ""
        else:
            b_middle = 6*" "

        for i in range(3):
            # might be the ugliest line of code i've ever written
            side = (MAX*" ") + (MAX-i*" ") + "|" + (i-MIN*" ")
            expansion_result = side + b_middle[MIN-i:MIN+i] + side[::-1]
            update_display(format_length(top_line), format_length(bottom_line))
            sleep(0.1)


        for i in range(5):
            line = []
            for space in range(5):
                line.append(("|" if (space == place) else " "))

            place += 1
            left, right = "".join(line[::-1]), "".join(line)

            top_line = left + title + right
            bottom_line = left + 6*" " + right

            update_display(format_length(top_line), format_length(bottom_line))
            sleep(0.1)


    # slide over
    sleep(1)
    x, y, z = 5, 5, 3

    for i in range(6):
        top_line = x*" " + title + y*" "
        bottom_line = z*" " + name + x*" "
        x-=1
        y+=1
        z+=3
        update_display(format_length(top_line), format_length(bottom_line))
        sleep(0.08)
    sleep(2)


def sys_startup_animation():
    # Loading bar, will tie into actual progress soon

    count = 0
    sleep(0.3)



    for i in range(11):
        time_del = 0.001 + (0.001 *random.randint(1, 5))
        filler = ""
        for i in range(count):
            filler += "="
        for i in range(10 - count):
            filler += " "
        start_string = "  |" + filler + "|  "

        update_display(format_length("PARKES v" + str(parkes_version), DEFAULTLEN), start_string, force_hotrun=True)
        count += 1
        sleep(time_del)


def sys_startup():
    global hot_run
    # Everything in here is done as part of the loading screen
    GPIO.output(GPIO_LIGHT, GPIO.HIGH)
    GPIO.output(GPIO_LAMP, GPIO.HIGH)
    error("E903", "PARKES WAKEUP")

    # set uptime start
    configuration["start_time"] = time.time()
    error("E904", "Startup initiated")
    sleep(1)

    # Assign ID number
    configuration["parkes_id"] = cfg_id_gen()


    sys_parkes_intro()
    update_display(format_length("PARKES v" + str(parkes_version), DEFAULTLEN),  format_length("loading", DEFAULTLEN), force_hotrun=True)
    sleep(0.4)
    sys_startup_animation()
    update_display(format_length("PARKES v" + str(parkes_version), DEFAULTLEN), format_length(" READY", DEFAULTLEN))
    sleep(1.2)
    GPIO.output(GPIO_LIGHT, GPIO.LOW)
    GPIO.output(GPIO_LAMP, GPIO.LOW)
    error("E905", "Startup complete")

def stg_delay():
    # Config: set delay for button input recog
    global configuration
    current_delay = configuration["rep_delay"]
    new_val = "0." + str(num_select("SELECT DURATION:", DEFAULT_NUMSEL, current_delay))
    if new_val != "0.!":
        configuration["rep_delay"] = float(new_val)

def stg_beep():
    # Config: set volume for beeper
    global configuration
    new_val = str(num_select("SELECT VOLUME:", DEFAULT_NUMSEL, configuration["beep_volume"]))
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


def dsp_format_uptime():
    c_uptime = time.time() - configuration["start_time"]

    # format for minutes
    if (c_uptime > 60):
        n_uptime = c_uptime / 60
        classifier = "mins"
    else:
        #format for seconds
        n_uptime = c_uptime
        classifier = "secs"

    return (n_uptime, classifier)


def con_uptime():
    global configuration
    top_line = format_length("Current uptime: ")

    # grab uptime
    uptime, classifier = dsp_format_uptime()

    while True:
        res = button_input(slowdown=False)
        if (res == "select"):
            return

        uptime, classifier = dsp_format_uptime()
        update_display(top_line, format_length(f" {uptime:.2f} {classifier}"))


def con_about():
    # About the program - also used for idle screen
    top_line = f"  PARKES v{parkes_version}   "
    bottom_line = format_length(" J.Woodman 2022 ")
    update_display(top_line, bottom_line)
    while True:
        res = button_input(slowdown=True)

        if (res == "select"):
            return
        elif (res == "cycle"):
            con_uptime()


def stg_cursor():
    # Config: manually reset cursor
    result = yesno("RESET CURSOR")
    if result == True:
        lcd.cursor_pos = (0, 0)
        sleep(0.2)

def stg_clear():
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
            current = (0 if current == (len(conf_list)-1) else current + 1)

        elif choose == "select":
            top_line = format_length(current_con, DEFAULTLEN-5)+ ": "
            bottom_line = str(configuration[current_con])
            dsp_scroll_tool(top_line, bottom_line)

        elif choose == "back":
            break

def bug_etest():
    # Config: create false error for testing
    error_type = num_select("SET ERROR CODE:", [0,1,2,3])

    if (error_type != "!"):
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
            current = (0 if current == (len(cne_list)-1) else current + 1)

        elif choose == "back":
            break
        
        elif (choose == "select"):
            top_line = format_length(top_line, DEFAULTLEN-5)+ ": "
            dsp_scroll_tool(top_line, con_line)

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
    global configuration
    global DEFAULT_RADIO
    # Opens the default port for Parkes transceiver

    # check that port isn't already open
    if configuration["telemetry"]["port_open"]:
        error("E314", "Error opening port - port already open!")
        return

    parkes_radio = serial.Serial(
        port = "/dev/serial0",
        baudrate = 9600,
        parity = serial.PARITY_NONE,
        stopbits = serial.STOPBITS_ONE,
        bytesize = serial.EIGHTBITS,

        # You might need a timeout here if it doesn't work, try a timeout of 1 sec
        )
    error("E910", "opened port - parkes_radio")

    DEFAULT_RADIO = parkes_radio

    configuration["telemetry"]["port_open"] = True  # Set port_open config flag

    if user_conf is True:
        confirm("PORT OPENED")

def cne_send(vamp):
    # depreciated in version 0.5.20
    # Sends command over radio
    try:
        v, a, m, p = vamp
    except:
        print(vamp)
        error("E310", str(vamp))
    command = "v"+str(v)+"_a"+str(a)+"_m"+str(m)+"_p"+str(p)+"\n"
    parkes_radio.write(command.encode())

def cne_receive(override_timeout=False, timeout_set=5):
    # Receives for command from parkes_radio - waits indefinitely
    # unless timeout is specified

    if (override_timeout):
        parkes_radio.timeout = timeout_set
        data = parkes_radio.read_until()
        to_return = data
        to_return = to_return.decode()
        vamp_decom = []
        parkes_radio.timeout = None
        for element in to_return.split("_"):

            vamp_decom.append(element[1:])
        try:
            v, a, m, p = vamp_decom
            vamp = (floor(float(v)), floor(float(a)), int(m), int(p))
            return to_return
        except:
            print("- Timeout detected - " + str(vamp_decom) +" " + str(to_return))
            error("E313", "cne_receive() - Connection timeout")
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

        # remove letter signifier (if is actually a letter)
        if (element):
            if (element.split()[0].isalpha()):
                vamp_decom.append(element[1:])

    try:
        v, a, m, p = vamp_decom
        vamp = (floor(float(v)), floor(float(a)), int(m), int(p))
    except:

        error("E311", vamp)


    return vamp


def cne_heartbeat():
    # Threaded function to monitor connection with Vega
    configuration["telemetry"]["hb_active"] = True
    configuration["telemetry"]["hb_force_kill"] = False
    receiving = True
    heartbeat_init_vamp = (10000, 0000, 8, 00000)

    pave.comms.send(heartbeat_init_vamp, parkes_radio)

    hb_count = 0
    if (hb_count < 0):
        error("E251")
        hb_count = 0

    error("E911", "Heartbeat loop initiated")

    # Main heartbeat loop - continues until hb_force_kill is triggered
    while configuration["telemetry"]["hb_force_kill"] == False:
        #GPIO.output(GPIO_LAMP, GPIO.HIGH)

        rec_vamp = pave.comms.receive(parkes_radio)
        configuration["telemetry"]["hb_data"].append(rec_vamp)
        configuration["telemetry"]["hb_pid"] = int(rec_vamp[3])
        #GPIO.output(GPIO_LAMP, GPIO.LOW)
        sleep(1)

        hb_count += 1
        AVG_SAMPLE = 10
        try:
            avg = 0
            # find avg value of last AVG_SAMPLE sig strengths
            for i in range(AVG_SAMPLE):
                avg += (hb_count / int(configuration["telemetry"]["hb_data"][-i][3]))

            avg /= AVG_SAMPLE
            configuration["telemetry"]["hb_sigstrn"] = avg


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


def cne_compare_vamp(vamp_1, vamp_2):
    # return true if two vamps are equal
    for (e_1, e_2) in zip(vamp_1, vamp_2):
        if (str(e_1) != str(e_2)):
            return False

    return True


def get_vamp(vamp, data):
    indexes = {
        "v" : 0,
        "a" : 1,
        "m" : 2,
        "p" : 3
    }

    return vamp[indexes[data]]

def cne_heartbeat_confirmation():
    # Waits for hb conf from Vega, supports timeout of 5 seconds
    rec_con = False
    while rec_con == False:
        result = pave.comms.receive(parkes_radio, timeout=True, timeout_duration=5)

        if (get_vamp(result, "m") == 8):
            error("E912", "Heartbeat confirmation received")
            rec_con = True
            return rec_con

        elif (result == "timeout"):
            error("E312", "Heartbeat connection timeout: could not establish connection")
            return False

        elif (result == "unknown failure"):
            print(result)


def dsp_handshake(status):
    # Displays current handshake status in a fun and easy to read way kill me please
    if (status == False):
        top_line = format_length("  NO CONNECTION ")
        bottom_line = format_length(" P ----/x/--- V ")

        update_display(top_line, bottom_line)

    if (status == True):
        top_line = format_length("  CONNECTING  ")
        bottom_line = format_length(" P ---------- V ")
        update_display(top_line, bottom_line)

        sleep(1)
        line_length = 10

        for t in range(3):
            GPIO.output(GPIO_LAMP, GPIO.HIGH)
            for i in range(0, line_length):
                start = ""
                for x in range(i):
                    start += "-"
                start += ">"

                for y in range(line_length-(i+1)):
                    start += "-"
                bottom_line = format_length(" P "+start+" V ")
                top_line = format_length("  CONNECTING  ")
                update_display(top_line, bottom_line)
                sleep(0.1)
            GPIO.output(GPIO_LAMP, GPIO.LOW)

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
    pave.comms.send(handshake_vamp, parkes_radio)

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

    kill_hb = (10000, 1000, 8, 00000)
    pave.comms.send(kill_hb, parkes_radio)

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
    messages = {
        "uploading" : "uploading...",
        "complete"  : "complete!",
        "total"     : "failed to update"
    }

    if (status in messages.keys()):
        bottom_line = messages[status]
    elif status == "partial":
        if data:
            con_count, param_count = data
            fract = con_count + "/" + param_count
            bottom_line = "partial: "+ data
        else:
            bottom_line = "partial: unknown"
            error("E322")
    else:
        error("E323", status)

    update_display(top_line, format_length(bottom_line))



def dsp_hb_view(status):
    if (status == True):
        while True:
            run_view = True
            top_line = format_length("HEARTBEAT:  LIVE")
            init_time = time.time()
            sig = str(int(configuration["telemetry"]["hb_sigstrn"])) + "%"


            if (len(sig) < 4):
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

            if (button_input() == "select"):
                break
    elif status == False:
        confirm("HEARTBEAT DEAD")

    else:
        error("E252")


def cne_hb_view():
    # show active heartbeat data
    if configuration["telemetry"]["hb_active"] == True:
        dsp_hb_view(True)
    else:
        dsp_hb_view(False)

def cne_hb_kill():
    # disable the heartbeat cleanly, if active
    if configuration["telemetry"]["hb_active"] == True:
        go_kill = yesno("KILL HRTBT?")
        if go_kill == True:
            cne_kill_heartbeat()
            confirm("HEARTBEAT DEAD")
    else:
        error("E250")

def cne_hb_menu():
    # hearbeat function menu
    global configuration

    hb_func_dict = {
        1 : ["HB VIEW", cne_hb_view],
        2 : ["HB KILL", cne_hb_kill],
        }

    dsp_menu(hb_func_dict, "HEARTBEAT")
    # Exit to menu, don't write below here

def cne_connect():
    # runs the handshake protocol
    global configuration
    cne_open_port(False)
    cne_handshake()
    configuration["telemetry"]["connected"] = True

def cne_vfs_beep():
    # set the beep volume for Vega's buzzer
    new_val =str(num_select("SELECT VOLUME:", DEFAULT_NUMSEL))
    if new_val != "!":
        cne_vfs_updater("beep_vol", new_val)
        sleep(0.2)

def cne_vfs_debug():
    # switches between debug mode on Vega
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
    # begins uploading the new update data to vega
    global configuration
    if yesno("UPDATE VFS?"):
        cne_upload_config(configuration["vfs_update_queue"])
        confirm("UPDATE COMPLETE")

def cne_vfs_compiler():
     # send and compile the vfs update
     cne_open_port(False)
     compile_vamp = (10000, 1000, 4, 00000)
     confirm("VFS LOG COMPILER")

     # Loop to send handshake / await response
     pave.comms.send(compile_vamp, parkes_radio)
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

def cne_update_cleanup(update_folder):
    os.system("rmdir " + update_folder)

def cne_update():
    global configuration

    update_folder = "update_tool"
    update_target = "/home/pi/" + update_folder + "/parkes_master.py"
    grab_command = "scp jackwoodman@corvette.local:/Users/jackwoodman/Desktop/novae/parkes_master.py /home/pi/" + update_folder

    top_line = format_length("PGS UPDATE TOOL")
    bottom_line = format_length("finding update..")
    update_display(top_line, bottom_line)
    cne_update_cleanup(update_folder)
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
        bottom_line = "search failed!  "
        error("E352", "update failed - could not connect to Corvette")

        update_display(top_line, bottom_line)
        wait_select()
        error("E350", "PGS update comparison failed")
        return

    # check if update is required or not
    if comparison:
        update_display(top_line, bottom_line)
        bottom_line = "no updates!"
        error("E351", "no PGS updates found")
        wait_select()
        cne_update_cleanup(update_folder)
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
            cne_update_cleanup(update_folder)
            return

    # check the update has worked
    if not filecmp.cmp("parkes_master.py", update_target):
        bottom_line = "update failed!  "
        error("E353", "update failed - update corruption detected")
        update_display(top_line, bottom_line)
        wait_select()
        cne_update_cleanup(update_folder)
        return

    bottom_line = "update success! "
    update_display(top_line, bottom_line)
    wait_select()

    bottom_line = format_length("cleaning up...")
    update_display(top_line, bottom_line)


    os.system("rmdir " + update_folder)
    sleep(4)

    bottom_line = "reboot to finish"
    update_display(top_line, bottom_line)
    wait_select()

    # runs recursive iteration of self, to work until next full shutdown
    os.system("python3 parkes_master.py")


def cne_parkes_menu():
    global configuration

    cne_parkes_dict = {
        1 : ["STATUS", cne_status],
        2 : ["OPEN PORT", cne_open_port],
        3 : ["UPDATE", cne_update]
    }

    dsp_menu(cne_parkes_dict, "PARKES CNE")

def cne_vega_menu():
    global configuration

    cne_vega_dict = {
        1 : ["HANDSHAKE", cne_connect],
        2 : ["HEARTBEAT", cne_hb_menu],
        3 : ["VFS CONFIG", cne_vfs_menu]
    }

    dsp_menu(cne_vega_dict, "VEGA CNE")


def sys_connect():
    global configuration

    connect_submen_dict = {
        1 : ["PARKES", cne_parkes_menu],
        2 : ["VEGA", cne_vega_menu],
        3 : ["EPOCH", cne_epoch_menu]
    }

    dsp_menu(connect_submen_dict, "CONNECT")

    # Exit to menu, don't write below here

def sys_debug():
    global configuration

    debug_func_dict = {
        1 : ["HARDWARE DIAG", bug_hardware_diag],
        2 : ["ERROR TEST", bug_etest],
        3 : ["HOTRUN SET", bug_hotrun]
        }


    dsp_menu(debug_func_dict, "DEBUG")
        # Exit to menu, don't write below here
    # Exit to menu, don't write below here

def sys_settings():
    global configuration

    settings_func_dict = {
        1 : ["INPUT DELAY", stg_delay],
        2 : ["BEEP", stg_beep],
        3 : ["CURSOR RESET", stg_cursor],
        4 : ["LCD CLEAR", stg_clear],
    }

    dsp_menu(settings_func_dict, "SETTINGS", True)


def sys_config():
    # Main: select config function
    global configuration

    config_func_dict = {
        1 : ["SETTINGS", sys_settings],
        2 : ["CONFIG VALUES", con_display],
        3 : ["ERROR TYPE", con_error_type],
        4 : ["ABOUT", con_about],
        5 : ["DEBUG", sys_debug],
        6 : ["REBOOT", con_reboot],
        7 : ["SHUTDOWN", con_shutdown]
        }

    dsp_menu(config_func_dict, "CONFIG", True)
        # Exit to menu, don't write below here
    # Exit to menu, don't write below here


def con_error_type():
    while True:
        code = ["E", "_", " ", " "]
        index = 1

        while (index < 4):
            code[index] = num_select("NEXT DIGIT:",[0,1,2,3,4,5,6,7,8,9])
            code[index + 1] = "_"
            index += 1


def lch_parkes_fire():
    global configuration
    # Used for testing engines without the preflight tests

    sure_go = yesno("RUN HOTFIRE?")
    if not sure_go:
        return
    error("E290")

    if not (configuration["parkes_ignitor"]):
        error("E204")
        return

    confirm("HOTFIRE ACTIVE")
    sleep(2)

    top_line = format_length("DISARMED")
    bottom_line = format_length("key to arm...")
    hold, armed = True, False


    while hold:
        # Loop to check for arming status
        update_display(top_line, bottom_line)
        if sys_check_status(GPIO_ARM):
            top_line = format_length("ARMED!")
            bottom_line = format_length("ready...")
            armed = True
        else:
            top_line = format_length("DISARMED")
            bottom_line = format_length("key to arm...")
            armed = False

        if armed and sys_check_status(GPIO_LAUNCH):
            hold = False
        sleep(0.2)

    top_line = format_length("AUTOSEQUENCE")
    bottom_line = format_length("-----active-----")
    update_display(top_line, bottom_line)

    sleep(3)
    # COUNTDOWN
    continue_launch = True
    for count in range(11):
        current = str(10 - count).zfill(2)
        top_line = format_length("    COUNTDOWN   ")
        bottom_line = format_length("      |"+current+"|      ")
        update_display(top_line, bottom_line)
        sleep(0.95)
        if not sys_check_status(GPIO_ARM):
            top_line, bottom_line =  display_format("DISARMED", "ending countdown")
            update_display(top_line, bottom_line)
            sleep(3)
            continue_launch = False
            break

    if continue_launch:
        sys_fire(sys_check_status(GPIO_ARM), True)
        top_line, bottom_line =  display_format("    COUNTDOWN   ", "    ignition    ")
        sleep(10)


def dsp_arm_status(missile="unknown", key="unknown"):
    # display the current status of the arm inputs during fire idle
    status = [" ","x","?"]

    if (missile == True):
        missile_status = status[1]
    elif (missile == False):
        missile_status = status[0]
    else:
        missile_status = status[2]

    if (key == True):
        key_status = status[1]
    elif (key == False):
        key_status = status[0]
    else:
        key_status = status[2]

    top_line = " SAFETY | ARMED "
    bottom_line = f"   [{missile_status}]  |  [{key_status}]  "
    update_display(top_line, bottom_line)


def dsp_parkes_title():
    # this was an attempt to display customer characters
    # it doesn't work, there might be a better way so leaving here ftm
    title_display_length = 5

    P = [[0b00000,0b01110,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110],
    [0b10000,0b10000,0b10000,0b10000,0b10000,0b10000,0b10000,0b00000]]

    A = [[0b00000,0b01110,0b10001,0b10001,0b10001,0b10001,0b10001,0b10001],
    [0b11111,0b10001,0b10001,0b10001,0b10001,0b10001,0b10001,0b00000]]

    R = [[0b00000,0b11110,0b10001,0b10001,0b10001,0b10001,0b10001,0b11110],
    [0b10010,0b10001,0b10001,0b10001,0b10001,0b10001,0b10001,0b00000]]

    K = [[0b00000,0b10001,0b10001,0b10001,0b10010,0b10010,0b10100,0b11100],
    [0b11000,0b10100,0b10010,0b10010,0b10001,0b10001,0b10001,0b00000]]

    E = [[0b00000,0b01111,0b10000,0b10000,0b10000,0b10000,0b10000,0b10000],
    [0b11111,0b10000,0b10000,0b10000,0b10000,0b10000,0b01111,0b00000]]

    S = [[0b00000,0b01111,0b10000,0b10000,0b10000,0b10000,0b10000,0b01110],
    [0b00001,0b00001,0b00001,0b00001,0b00001,0b00001,0b11110,0b00000]]

    s_time = time.time()
    lcd.create_char(7, [0b00000,0b00000,0b00000,0b00000,0b00000,0b00000,0b00000,0b00000])

    # display title for title_display_length seconds
    while (time.time() - s_time < title_display_length):

        # switch between top and bottom frames
        for index_set in range(0, 1):

            # define character frames for either top or bottom of display
            for (index, frame_set) in enumerate([P,A,R,K,E,S]):
                lcd.create_char(index, frame_set[index_set])

            # print spacing
            for i in range(5):
                lcd.write(7)

            # print letter row
            for frame in range(0, 5):
                lcd.write(frame)

            # print spacing
            for i in range(5):
                lcd.write(7)


def dsp_countdown(lcc=0, am=0):
    # entering countdown display
    launch_decision = True

    # display countdown in cute way
    for count in range(11):

        current = 10 - count
        current_str = str(current).zfill(2)

        loaded = ""
        for i in range(count):
            loaded += " "
        for j in range(current):
            loaded += "="
        bottom_line = f"  [{loaded}]  "


        top_line = f"     - {current_str} -     "
        update_display(top_line, bottom_line)
        GPIO.output(GPIO_LAMP, GPIO.HIGH)
        sleep(0.7)
        GPIO.output(GPIO_LAMP, GPIO.LOW)
        sleep(0.25)

        if not sys_check_status(GPIO_ARM) or not sys_check_status(GPIO_MISSILE):
            # either arm keyswtich or missile disengaged, abort countdown
            top_line, bottom_line =  display_format("DISARMED", "ending countdown")
            error("E989", "Countdown ABORT")
            update_display(top_line, bottom_line)
            sleep(3)
            sys_set_output(GPIO_LIGHT, False)
            launch_decision = False
            return (launch_decision, lcc)

    # left countdown loop, return ultimate decision
    return (launch_decision, lcc + (am * launch_decision))

def dsp_arm_sequence(hold=True, armed=False):
    global configuration
    # arming and countdown sequences, returns ultimate arming status

    if not armed:
        # some programming error calling the function has occured
        error("E289", "Serious error calling dsp_arm_sequence")
        return False


    while hold:
        mis_status = sys_check_status(GPIO_MISSILE)
        key_status = sys_check_status(GPIO_ARM)

        dsp_arm_status(mis_status, key_status)  # show gui for arm stat

        # both arms triggered, ready for button press
        armed = (sys_check_status(GPIO_ARM) and sys_check_status(GPIO_MISSILE))

        # ready to enter coutndown
        if armed and sys_check_status(GPIO_LAUNCH):
            hold = False

        elif not armed and sys_check_status(GPIO_LAUNCH):
            # allow to leave launch arm sequence
            end_seq = confirm("END SEQUENCE?")
            if end_seq:
                return False

        sys_set_output(GPIO_LIGHT, armed)
        sleep(0.1)

    top_line = format_length("  AUTOSEQUENCE  ")
    bottom_line = format_length("     active     ")
    update_display(top_line, bottom_line)
    sleep(3.5)

    return True


def lch_epoch_fire():
    # Function to manually fire epoch
    cne_open_port()

    # get hotfire confirmation
    sure_go = yesno("HOTFIRE EPOCH?")
    if not sure_go:
        return

    else:
        sleep(2)
        hold, armed = True, True

    # enter arm and countdown phase
    continue_launch = dsp_arm_sequence(hold, armed)
    if continue_launch:
        continue_launch, code = dsp_countdown()

    if continue_launch:
        # if we're here, we're launching boys

        # check reply from epoch
        mis_status = sys_check_status(GPIO_MISSILE)
        key_status = sys_check_status(GPIO_ARM)
        com_res = sys_epoch_fire(mis_status, key_status)

        if com_res == 0:
            # epoch not ok with the lauch
            error("E261", "Epoch aborted ignition")

        elif com_res == 1:
            # got confirmation of the ignition
            top_line, bottom_line =  display_format("    IGNITION    ","   confirmed    ")
            update_display(top_line, bottom_line)
            wait_select()

        elif com_res == 2:
            # connection to epoch timed out
            error("E260", "Timeout - unable to connect to Epoch")
        elif com_res == 3:
            error("E262")

        elif com_res == 4:
            error("E263", "Ignition confirmation not available")

    # end of hotfire, cleanup
    sys_set_output(GPIO_LIGHT, False)


def lch_flight_configure():
    # all functions required to prepare for flight
    GPIO.output(GPIO_IGNITOR, GPIO.LOW)

    return True


def lch_preflight_parkes():
    global configuration
    # Parkes onboard checks

    # Check configured for flight
    if not lch_flight_configure():
        return "lch_flight_configure() failed"

    # Check system armed
    if not sys_check_status(GPIO_ARM):
        return True
        #return "disarm detected"

    # Check ignition continuity
    if not sys_check_cont():
        return "discontinuity in ignition loop detected"

    # Check UART port is open
    try:
        if not configuration["telemetry"]["port_open"]:
            return "parkes_radio port is closed"
    except:
        return "parkes_radio port has not been initialised"

    # Checks heartbeat has been disabled
    if configuration["telemetry"]["hb_active"] == True:
        return "heartbeat is active"

    # Check system armed
    if not sys_check_status(GPIO_ARM):
        return True
        #return "disarm detected"


    return True


def lch_quick_check():
    # This gets run during the countdown

    # Check continuity
    if not sys_check_cont():
        return "discontinuity in ignition loop detected"

    # Check system armed
    if not sys_check_status(GPIO_ARM):
        return "disarm detected"

    return True


def lch_countdown():
    # Local fire command - used when Parkes is commanding a local ignition only
    sleep(2)
    continue_launch = True

    for second in range(11):
        s = "s" * (second > 1)
        current = str(10 - second).zfill(2)
        top_line = format_length("    COUNTDOWN   ")
        bottom_line = format_length("      |"+current+"|      ")
        update_display(top_line, bottom_line)

        qc_results = lch_quick_check()
        if not qc_results:
            
            continue_launch = False
            error("E293", f"(failed at t-{second}{s}) " + qc_results)
            sleep(3)
            break
        sleep(0.95)
        qc_results = lch_quick_check()
        
        if not qc_results:
            continue_launch = False
            error("E294", f"(failed at t-{second}{s}) " + qc_results)
            sleep(3)
            break


    if continue_launch:
        # Passed launch checks, proceed with ignition command
        sys_fire(sys_check_status(GPIO_ARM), True)

        top_line = format_length("    COUNTDOWN   ")
        bottom_line = format_length("    ignition    ")
        error("E999", "ignition")
        wait_select()

def dsp_preflight_show():
    global configuration

    status = configuration["launch"]["preflight_status"]

    top_line = format_length("PREFLIGHT CHECK:")
    bottom_line = format_length(status)
    update_display(top_line, bottom_line)
    sleep(1.5)

def lch_preflight_all():
    global configuration
    v_count, e_count, p_count = 0,0,0
    continue_poll = True
    error("E994", "Entering preflight checks")

    # Ask for flight configuration and preflight checks
    error("E940")
    configuration["launch"]["preflight_status"] = "parkes..."
    dsp_preflight_show()
    pf_results = lch_preflight_parkes()
    sleep(1.5)

    if pf_results != True:
        error("E291", pf_results)
        configuration["launch"]["in_preflight"] = False

    else:
        # parkes is good to go
        error("E991", "Parkes is GO")
        configuration["launch"]["preflight_status"] = "parkes is GO"
        dsp_preflight_show()
        p_count += 1



    # Time to ask Epoch to launch_poll
    configuration["launch"]["preflight_status"] = "epoch..."
    error("E942")
    dsp_preflight_show()

    attempts = 0
    while True:
        epoch_pre = (0, 2000, 0, 10000)
        pave.comms.send(epoch_pre, parkes_radio)

        error("E983")
        sleep(0.3)
        epoch_poll_results = pave.comms.receive(parkes_radio, True)

        if (get_vamp(epoch_poll_results, "p") == 11111):
            error("E298", str(epoch_poll_results))
            break

        elif get_vamp(epoch_poll_results, "p") == 20000 and get_vamp(epoch_poll_results, "m") == 2:
            error("E992")
            configuration["launch"]["preflight_status"] = "epoch is GO"
            dsp_preflight_show()
            e_count += 1
            break

        if (epoch_poll_results == "timeout"):
            error("E284")
            attempts += 1

        if (attempts == 3):
            break

    if (epoch_poll_results == "timeout"):
        error("E285")
        continue_poll = False


    if vega_in_loop:
        # Time to ask Vega to launch_poll
        error("E941")
        configuration["launch"]["preflight_status"] = "vega..."
        dsp_preflight_show()

        vega_pre = (0, 2000, 0, 00000)
        pave.comms.send(vega_pre, parkes_radio)

        sleep(0.3)
        loop_start = time.time()
        while True:
            error("E984")
            vega_confirmed = pave.comms.receive(parkes_radio, True, 10)

            if (get_vamp(vega_confirmed, "a") == 0):
                # vega has confirmed poll receipt
                print("yas")
                break

            if (vega_confirmed == "timeout"):
                # vega confirm timed out
                break

            else:
                # never got confirmation code
                print(vega_confirmed)


        if (vega_confirmed == "timeout"):
            error("E286")
            continue_poll = False

        else:

            if vega_confirmed[2] != 0:
                # did not get proper confirmation from vega
                error("E294", f"Reason: {str(vega_confirmed)}")
                print(f"Reason: {str(vega_confirmed)}")

                continue_poll = False

        sleep(0.2)

        # check if worth continuing anyway
        if continue_poll:
            vega_poll_results = pave.comms.receive(parkes_radio, True)

            if (get_vamp(vega_poll_results, "p") == 21111):

                error("E292", str(vega_poll_results))


            elif (get_vamp(vega_poll_results, "p") == 20202):
                error("E990", "Vega is GO")
                configuration["launch"]["preflight_status"] = "vega is GO"
                dsp_preflight_show()
                v_count += 1

            else:
                error("E293", str(vega_poll_results))
    else:
        # no vega in loop, increment to override
        v_count += 1


    # calculate go counts and set final preflight status
    pass_count = v_count + e_count + p_count
    pf_stat = lch_status_compile(v_count, e_count, p_count)
    error("E986", pf_stat)
    configuration["launch"]["preflight_status"] = pf_stat

    # if three GO counts, return good to go
    if pass_count == 3:
        # confirm launch is go
        dsp_preflight_show()
        sleep(2)
        error("E993")
        top_line = "  ALL SYSTEMS  "
        bottom_line = "    ARE GO     "
        update_display(top_line, bottom_line)
        sleep(3)
        return True

    elif pass_count > 3:
        # oh no do something TODO
        error("E288", f"Pass count = {pass_count}")
        return False
    else:
        # not enough GO counts, returning abort
        dsp_preflight_show()
        wait_select()
        return False

def lch_status_compile(v,e,p):
    # build display status for go/no go poll
    state = {
        0 : "NO",
        1 : "GO"
    }
    status = "p:"+state[p]+" v:"+state[v]+" e:"+state[e]+"  "

    return status


def lch_launch_program():
    # this is the big one
    global configuration

    # two random ints that are part of launch confirmation
    launch_commit_code = random.randint(0, 10000)
    inc_amount = random.randint(0, 100)

    sure_go = yesno("COMMIT LAUNCH?")
    if not sure_go:
        return

    error("E987", "Launch commit marked")

    # get gui confirmation to arm for launch
    cne_open_port()
    arm_sequence = dsp_arm_sequence(True,True)
    error("E988", "entering autosequence...")

    if not arm_sequence:
        sys_set_output(GPIO_LIGHT, False)
        return

    # good to launch, set preflight flags
    configuration["launch"]["in_preflight"] = True

    passed_preflights = lch_preflight_all()

    if (not passed_preflights):
        sys_set_output(GPIO_LIGHT, False)
        error("E287")
        return

    configuration["launch"]["in_preflight"] = False

    sleep(2)
    error("E998", "launch countdown commit")


    # seek arm confirmation
    continue_launch, code = dsp_countdown(launch_commit_code, inc_amount)

    if (continue_launch == True) and (code == launch_commit_code + inc_amount):
        # finally ok to launch, send command to epoch
        mis_status = sys_check_status(GPIO_MISSILE)
        key_status = sys_check_status(GPIO_ARM)
        com_res = sys_epoch_fire(mis_status, key_status)

        if com_res == 0:
            # epoch not ok with the lauch
            error("E261", "Epoch aborted ignition")
            sys_set_output(GPIO_LIGHT, False)

        elif com_res == 1:
            # got confirmation of the ignition, enter downlink
            error("E995", "Ignition confirmed, entering downlink mode")
            dsp_downlink()

        elif com_res == 2:
            # connection to epoch timed out
            error("E260", "Timeout - unable to connect to Epoch")
            sys_set_output(GPIO_LIGHT, False)

        elif com_res == 5:
            error("E267")
            sys_set_output(GPIO_LIGHT, False)

    else:
        if (continue_launch) and (code != launch_commit_code + inc_amount):
            error("E944", f"{code} != {launch_commit_code} + {inc_amount}")

        else:
            error("E943", f"{code} != {launch_commit_code} + {inc_amount}")
            sys_set_output(GPIO_LIGHT, False)



def lch_force_launch():
    # Forces launch, skipping prep and arm phase. Used for testing only. May be removed from use
    cne_open_port(False)
    error("E210")
    force_vamp = (10000, 1000, 2, 00000)
    confirm("FORCE CMMND SENT")

    # Loop to send handshake / await response
    pave.comms.send(force_vamp, parkes_radio)
    sleep(0.2)
    dsp_downlink()

def lch_vega_demo():
    # Forces launch, skipping prep and arm phase. Used for testing only. May be removed from use
    cne_open_port(False)
    error("E210")
    force_vamp = (10000, 1000, 3, 00000)
    confirm("FORCE LOOP SENT")

    # Loop to send handshake / await response
    pave.comms.send(force_vamp, parkes_radio)
    sleep(0.2)
    dsp_downlink(True)

def lch_arm():
    # arms vega for flight
    cne_open_port(False)
    arm_vamp = (10000, 1000, 0, 00000)
    # Loop to send handshake / await response
    pave.comms.send(arm_vamp, parkes_radio)

def dsp_downlink(demo=False):
    global configuration
    flight_downlink = []
    error("E985")

    # keep track of highest re corded altitude
    downlinking = True
    max_altitude = 0

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

    exit_triggers = [6, 7]

    # Designed as a lightweight function to display data directly
    while (downlinking):

        if not (configuration["telemetry"]["port_open"]):
            cne_open_port()
        incoming = pave.comms.receive(parkes_radio, True, 5)

        if (incoming != "timeout"):

            try:
                v,a,m,p = incoming
                if (a > max_altitude):
                    max_altitude = a
                update_display(modetype[m], "V:"+str(v).ljust(4," ")+"  A:"+str(a)+"m")
                unable_check = False
            except Exception as e:
                unable_check = True
                t = f"incoming: {incoming}, excpetion: {e}"
                error("E311", t)
                print(f"ex: {e}")
                print(f"in: {incoming}")



        elif (incoming == "timeout"):
            # timeout detected
            error("E309")
            parkes_radio.reset_input_buffer()
            parkes_radio.flush()
            unable_check = True

        elif (incoming == "unknown failure"):
            error("E307")
            unable_check = True

        else:
            error("E308")
            unable_check = True

        if not demo:
            # not in demo mode, check for triggers to leave downlink
            if not unable_check:
                # only check if appropriate packet
                if m in exit_triggers:
                    error_code = "E99" + str(m)
                    error(error_code)
                    downlinking = False

    # finished with flight, go to postflight
    lch_landed(max_altitude)

def lch_landed(m_alt):
    # function to handle any postflight stuff
    confirm("FLIGHT ENDED")
    confirm(f"MAX: {str(m_alt)}")
    confirm(f"Ended Downlink")


def sys_launch():

    launch_func_dict = {
        1 : ["AUTOSEQUENCE", lch_launch_program],   # main launch program
        2 : ["ARM VEGA", lch_arm],                  # arm vega for flight
        3 : ["LCH + VEGA", lch_force_launch],     # vega downlink mode
        4 : ["VEGA DOWNLNK", dsp_downlink],         # parkes downlink mode
        5 : ["EPOCH FIRE", lch_epoch_fire],         # commands epoch ignition
        6 : ["PARKES FIRE", lch_parkes_fire],       # commands parkes ignition
        7 : ["VEGA DEMO", lch_vega_demo]            # vega demo downlink
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
        if sys_main_status() != "CONTINUE":
            error("E399", "go_kill / go_reboot detected")
            return
        else:
            dsp_menu(main_func_dict, title)

def sys_shutdown_process():
    # Function to handle all the pre-shutdown cleanup
    sleep(1)
    top_line, bottom_line = "PARKES v" + str(parkes_version) + "     ", format_length("shutting down", DEFAULTLEN)
    update_display(top_line, bottom_line)
    error("E908", "Shutdown process initiated")
    sleep(4)

    # Non-system shutdown stuff here





    top_line, bottom_line = format_length(" ", DEFAULTLEN), format_length(" done", DEFAULTLEN)
    error("E909", "Shutdown process complete")
    update_display(top_line, bottom_line)
    sleep(2)

def sys_type_get(newval):
    # Get variable type, return string output
    # this feels like there are better ways to write this
    try:
        int(newval)
        return "int"
    except ValueError:
        try:
            float(newval)

            return "float"
        except ValueError:
            return ("string" if  newval != "True\n" and newval != "False\n" else "bool")


def sys_startup_tests(ex_value, config_vals):
    # Startup test functions, don't fuck with these

    # check number of config values matches expectations
    if len(config_vals) != ex_value:
        return False, "c_v_failure"

    # checks config file version supports parkes version
    if parkes_version > configuration["parkes_vers"]:
        return False, "c_f_failure"

    # check parkes version supports config file
    if parkes_version < configuration["parkes_vers"]:
        return False, "p_v_failure"

    # passed all checks
    return True, "tests_passed"

# Parkes Configuration Interpreter 2.0 - PCI2.0c
def cfg_type_set(definition):
    # function takes string description of desired type and converts
    # input to required type

    def_type = sys_type_get(definition)

    if (def_type == "int"):
        return int(definition)

    elif (def_type == "bool"):
        return (True if (definition == "True") else False)

    elif (def_type == "float"):
        return float(definition)

    elif (def_type == "string"):
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

def cfg_launch(data):
    # launch program config functions
    global configuration

    if data == "init":
        configuration["launch"] = {}

    elif "set" in data:
        if "default" in data:
            configuration["launch"] = {
                            "in_preflight"     : False,
                            "preflight_status" : "Inactive"

            }

        # TO-DO - add non default support

def cfg_telemetry(data):
    # telem configuration functions
    global configuration

    if data == "init":
        configuration["telemetry"] = {}

    elif "set" in data:
        if "default" in data:
            configuration["telemetry"] = {
                            "active": False,
                            "connected": False,
                            "sig_strength": 0,
                            "port_open": False,
                            "hb_active": False,
                            "hb_data":[],
                            "hb_sigstrn":0,
                            "hb_force_kill": False
                            }
        # TO-DO - add non default support

def cfg_errlog(data):
    # error log configuration functions
    global configuration
    if data == "init":
        pave.file.create("errorlog.txt", "PARKES ERROR LOG", "Parkes", internal_version, id=configuration["parkes_id"])

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
        "expected_value": cfg_exval,
        "launch" : cfg_launch
    }

    command_funcs[target](command)

def cfg_startuptest_modify(set_to=False):
    global run_startup_test
    run_startup_test = set_to

    if not set_to and not sys_check_status(GPIO_MISSILE):
        error("E202")

def cfg_include_vega():
    # includes vega in pre-launch checks
    global vega_in_loop
    vega_in_loop = True


def cfg_kill_setup():
    return

def cfg_id_gen():
    # produces random ID_LEN-digit ID for file generation
    id = ""

    for digit in range(ID_LEN):
        # create random digit from 0-9
        new_digit = str(random.randint(0,9))
        id += new_digit

    return id



def sys_config_interpreter(config_file):
    # func accepts configuration file and interprets it
    global hot_run
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

    # check for hotrun force command
    if (sys_check_status(GPIO_MISSILE)):
        hot_run = True
        error("E902", "HOTRUN forced on startup")
        error("E211")

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

    hot_run = yesno("HOTRUN TRUE?")

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
                # saturday
                update_display(topline, bottomline)
                #saturday

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
        "light"   : GPIO_LIGHT,
        "lamp"    : GPIO_LAMP
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
while sys_main_status() == "REBOOT":
    global run_startup_test
    global exptected_value
    global vega_in_loop

    # set default config values
    run_startup_test, expected_value, configuration["go_reboot"], vega_in_loop = True, 0, False, False

    # find config file
    try:
        config_file = open("/home/pi/parkes_config.txt", "r")
    except:
        error("108")

    # run startup functions and setup processes
    sys_startup()

    # pass config file to file interpreter to complete config
    sys_config_interpreter(config_file)

    # run startup tests if required
    if (run_startup_test):
        sys_startup_test()

    config_file.close()

    lcd.clear()

    sys_main_menu()


# If we're here, we've left the running loop. Time to clean up.

# Non-system shutdown stuff
sys_shutdown_process()

# System shutdown stuff
lcd.clear()
GPIO.cleanup()
if (configuration["telemetry"]["port_open"]):
    parkes_radio.close()

# clean shutdown, disconnects SSH and prevents SD corruption
from subprocess import call
call("sudo poweroff", shell=True)
