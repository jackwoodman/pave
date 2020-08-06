# Parkes 0.5

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
from math import floor
from time import sleep
import RPi.GPIO as GPIO
from random import randint
from datetime import datetime
from RPLCD.gpio import CharLCD

# hot_run defines whether Parkes will run using hardware or simulation.
hot_run = True
parkes_version = 0.5


lcd = CharLCD(cols=16, rows=2, pin_rs=37, pin_e=35, pins_data=[33, 31, 29, 23], numbering_mode=GPIO.BOARD)

lcd.clear()
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

# Defining Hardware Buttons
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Back button - GPIO 23
GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Select button - GPIO 24
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Cycle button - GPIO 25

global configuration
configuration = {
    "go_reboot": True,
    "go_kill": False
    }

def dsp_vowel_remover(word):
    # This function removes vowels from words.
    vowels, new_word, has_taken = ["a","e","i","o","u"], [], False

    for x in list(word)[::-1]:
         if x not in vowels or has_taken is True:
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
    topline = "ERROR:  " + format_length(code, 8)
    current_select = False

    while True:
        if current_select == True:
            bottom_line = "|RBT| / SHUTDWN "
        else:
            bottom_line = " RBT / |SHUTDWN|"

        nf_display = (topline, bottom_line)
        update_display(nf_display)

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
    topline = "ERROR:  " + format_length(code, 8)
    bottom_line = " FATAL ERROR    "
    yesno_display = (topline, bottom_line)
    update_display(yesno_display)
    while True:
        waiting = True

def dsp_error_warning(code):
    topline = "ERROR:  " + format_length(code, 8)
    bottom_line = "   |CONTINUE|   "
    yesno_display = (topline, bottom_line)
    update_display(yesno_display)
    wait_select()

def dsp_error_passive(code):
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
        error_file = open("parkes_errorlog.txt", "a")
        new_error = "- " + error_codes[e_code[1]][1] + " ("+str(e_code)+")"

        if data:
            new_error += " => "
            new_error += str(data)
            new_error += "\n"
        else:
            new_error += "\n"
        print(new_error)
        error_file.write(new_error)
        error_file.close()
        error_type(e_code)
    else:
        error("E199", e_code)
#===============================================#

def dsp_menu(func_dict, menu_title):
    global Configuration
    current_select = 1

    while True:
        current_func_name, current_func = func_dict[current_select]
        title = menu_title + ":"
        top_line = format_length(menu_title, 13) + str(current_select) + "/" + str(len(func_dict))
        bottom_line = "=> " + format_length(current_func_name, 12)
        menu_display = (top_line, bottom_line)
        update_display(menu_display)
        choose = button_input()

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
    topline = format_length(message)
    bottomline = "      |OK|      "
    confirm_disp = (topline, bottomline)
    update_display(confirm_disp)
    wait_select()

def format_length(input_string, length=16, remove_vowel=False):
    # Formats string. Default len is 16, but can be changed. Won't remove vowels unless asked to
    output_string = ""

    if len(str(input_string)) > length:
        if remove_vowel is False:
            output_string = input_string[:length]

        elif remove_vowel is True:
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
        output_string = input_string
        for i in range(length - len(input_string)):
            output_string += " "
    else:
        output_string = input_string

    return output_string

def button_input():
    if hot_run:
        return hardware_button_input()

    elif not hot_run:
        return software_button_input()

    else:
        error("E107")


def update_display(to_display):
    top_line, bottom_line = to_display

    if hot_run:
        if len(top_line) <= 16 and len(bottom_line) <= 16:
            send_to_display = format_length(top_line) + format_length(bottom_line)
            lcd.write_string(send_to_display)
            return 1
        else:
            error("E203")

    elif not hot_run:
        print()
        print(" ________________")
        print("|" + str(top_line) + "|")
        print("|" + format_length(str(bottom_line),16) + "|")
        print("|________________|\n")
        return 1

    else:
        error("E107")


def hardware_button_input():
    # Input detection for flight mode
    button_pressed = ""
    while True:
        print("input_hold")

        if GPIO.input(16) == GPIO.HIGH:
            print("back")
            return "back"
        if GPIO.input(18) == GPIO.HIGH:
            print("select")
            return "select"
        if GPIO.input(22) == GPIO.HIGH:
            print("cycle")
            return "cycle"
    sleep(configuration["rep_delay"])


def software_button_input():
    # Input detection for emulation
    button_pressed = ""
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
    #lcd.clear()

    if len(top_line) <= 16 and len(bottom_line) <= 16:
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
    print("|" + format_length(str(bottom_line),16) + "|")
    print("|________________|\n")


def num_select(message, values):
    # Basic number selection UI, returns integer value
    current_num = values[0]
    topline = message
    builder = [values[0]]
    original = values
    count = 0
    for i in range(16 - len(message)):
        topline += " "

    while True:
        for number in original:
            builder.append(number)

        num_list = builder[1:]
        number_list = [x for x in num_list]
        bottom_line = "|" + str(number_list.pop(0)) + "| "

        if len(number_list) > 4:
            first_six = number_list[:6]
        else:
            for i in range(12 - (2*len(number_list))):
                           bottom_line += " "
            first_six = number_list[:6]

        for element in first_six:
            bottom_line += str(element) + " "

        num_display = (topline, bottom_line)
        update_display(num_display)

        choose = button_input()
        if choose == "cycle":
            original.append(original.pop(0))
            builder = [original[0]]

        elif choose == "select":
            return bottom_line[1]

        elif choose == "back":
            return "!"

def wait_select():
    # Waits for "select" confirmation
    while True:
        choose = button_input()

        if choose == "select":
            break

def yesno(message):
    # Basic bool select function, returns bool value
    topline = message
    for i in range(16 - len(message)):
        topline += " "
    current_select = False
    while True:
        if current_select == True:
            bottom_line = "    |Y| / N     "
        else:
            bottom_line = "     Y / |N|    "

        yesno_display = (topline, bottom_line)
        update_display(yesno_display)

        choose = button_input()
        if choose == "cycle":
            if current_select == True:
                current_select = False
            else:
                current_select = True

        elif choose == "select":
            if current_select == True:
                return True
            elif current_select == False:
                return False

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

        startup_display = (format_length("PARKES v" + str(parkes_version), 16), start_string)
        update_display(startup_display)
        count += 1
        sleep(time_del)


def sys_startup():

    sleep(1)
    startup_display = (format_length("PARKES v" + str(parkes_version), 16),  format_length("loading", 16))
    update_display(startup_display)
    sleep(0.4)

    sys_startup_animation()
    startup_display = (format_length("", 16), format_length(" READY", 16))
    update_display(startup_display)
    sleep(1)

def con_delay():
    # Config: set delay for button input recog
    global configuration
    new_val = "0." + str(num_select("SELECT DURATION:", [1,2,3,4,5,6,7,8,9]))
    if new_val != "0.!":
        configuration["rep_delay"] = float(new_val)

def con_beep():
    # Config: set volume for beeper
    global configuration
    new_val =str(num_select("SELECT VOLUME:", [1,2,3,4,5,6,7,8,9]))
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
    # About the program
    about_display = (format_length("PARKES v" + str(parkes_version), 16), format_length("novae space 2020"))
    update_display(about_display)
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
        topline = format_length("CONFG VALS: ", 16 - len(current_sel)) + current_sel;

        current_con = conf_list[current]
        con_line = bottom_line + format_length(current_con + ": " + str(configuration[current_con]), 16)
        config_dis = (topline, con_line)
        update_display(config_dis)
        choose = button_input()

        if choose == "cycle":
            if current != (len(conf_list) - 1):
                current += 1
            else:
                current = 0
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
        topline = format_length("CNCT VALS: ", 16 - len(current_sel)) + current_sel;

        current_con = cne_list[current]
        con_line = bottom_line + format_length(current_con + ": " + str(configuration["telemetry"][current_con]), 16)
        config_dis = (topline, con_line)
        update_display(config_dis)
        choose = button_input()

        if choose == "cycle":
            if current != (len(cne_list) - 1):
                current += 1
            else:
                current = 0
        elif choose == "back":
            break

def check_vamp_string(vamp):
    vamp_lengths = {"v":5, "a":4, "m": 1, "p":5}
    vamp_decom = []
    for element in vamp.split("_"):
        vamp_decom = element[1:]

        if len(vamp_decom) != vamp_lengths[element[0]]:
            error("E122")


        vamp_decom = element[1:]
        v, a, m, p = vamp_decom

def check_vamp_tuple(vamp):
    vamp_lengths = {0:5, 1:4, 2: 1, 3:5}
    for element in vamp:
        if vamp_lengths[vamp.index(element)] != len(str(element)):
            error("E123")

def cne_open_port():
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

def cne_receive(override_timeout=False):
    if override_timeout:
        parkes_radio.timeout = 5
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
            return "timeout"

    # Listens for a vamp from Vega. Simples
    data = parkes_radio.read_until()
    to_return = data
    to_return = to_return.decode()

    return to_return


def cne_vamp_destruct(vamp):
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
    # Heatbeat func - will be threading
    configuration["telemetry"]["hb_active"] = True
    configuration["telemetry"]["hb_force_kill"] = False
    receiving = True
    heartbeat_init_vamp = (10000, 0000, 8, 00000)

    cne_send(heartbeat_init_vamp)
    hb_count = 0
    if hb_count < 0:
        error("E251")
        hb_count = 0

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

    configuration["telemetry"]["hb_active"] = False
    configuration["telemetry"]["hb_data"] = []
    configuration["telemetry"]["hb_sigstrn"] = 0


def cne_heartbeat_thread():
    force_kill = False
    global cne_hb_thread
    # Moves the heartbeat function into its own function
    cne_hb_thread = threading.Thread(target=cne_heartbeat)
    cne_hb_thread.start()


def cne_heartbeat_confirmation():
    rec_con = False
    while rec_con == False:
        result = cne_receive(override_timeout=True)
        if "v10000_a1000_m8_p" in str(result):

            rec_con = True
            return rec_con
        elif str(result) == "timeout":
            error("E312", "Heartbeat connection timeout: could not establish connection")
            return False


def dsp_handshake(status):
    # Displays current handshake status in a fun and easy to read way kill me please
    if status == False:
        topline = format_length("  <|3 - HB OFF  ")
        bottom_line = format_length(" P-----/x/----V ")
        dsp = (topline, bottom_line)
        update_display(dsp)

    if status == True:
        topline = format_length("  <3 - HB ON  ")
        bottom_line = format_length(" P------------V ")
        dsp = (topline, bottom_line)
        update_display(dsp)

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
                topline = format_length("<3 - HB ON")
                dsp = (topline, bottom_line)
                update_display(dsp)
                sleep(0.1)

        confirm("HANDSHAKE GOOD")


def cne_handshake():
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
    dsp_handshake(True)
    cne_heartbeat_thread()

def cne_kill_heartbeat():
    # Finish the heartbeat thread
    global configuration
    parkes_radio.write("v10000_a1000_m8_p00000\n".encode())
    configuration["telemetry"]["hb_force_kill"] = True
    cne_hb_thread.join()


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
            hb_ciew = (top_line, bottom_line)
            update_display(hb_ciew)
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
    cne_open_port()
    cne_handshake()
    configuration["telemetry"]["connected"] = True


def sys_connect():
    global configuration

    connect_func_dict = {
        1 : ["HANDSHAKE", cne_connect],
        2 : ["STATUS", cne_status],
        3 : ["HEARTBEAT", cne_hb_menu]
        }

    dsp_menu(connect_func_dict, "CONNECT")
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
        9 : ["ABOUT", con_about]
        }

    dsp_menu(config_func_dict, "CONFIG")
        # Exit to menu, don't write below here
    # Exit to menu, don't write below here


def lch_force_launch():
    cne_open_port()
    # Forces launch, skipping prep and arm phase. Used for testing only. May be removed from use
    error("E210")
    force_vamp = (10000, 1000, 2, 00000)
    confirm("FORCE CMMND SENT")

    # Loop to send handshake / await response
    cne_send(force_vamp)
    sleep(0.2)
    lch_downlink()

def lch_loop():
    cne_open_port()
    # Forces launch, skipping prep and arm phase. Used for testing only. May be removed from use
    error("E210")
    force_vamp = (10000, 1000, 3, 00000)
    confirm("FORCE LOOP SENT")

    # Loop to send handshake / await response
    cne_send(force_vamp)
    sleep(0.2)
    lch_downlink()


def lch_arm():
    cne_open_port()
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

            flight_downlink = (modetype[m], "V:"+str(v)+"  A:"+str(a)+"m")
            update_display(flight_downlink)
        except:
            error("E310", incoming.decode())


def sys_launch():

    launch_func_dict = {
        1 : ["ARM VEGA", lch_arm],
        2 : ["LAUNCH", lch_force_launch],
        3 : ["DOWNLINK", lch_downlink],
        4 : ["LCH LOOP", lch_loop]
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
        if configuration["go_reboot"] is True or configuration["go_kill"] is True:
            error("E399", "go_kill / go_reboot detected")
            return
        else:
            dsp_menu(main_func_dict, title)

def sys_shutdown_process():

    sleep(1)
    startup_display = ("PARKES v" + str(parkes_version) + "     ", format_length("shutting down", 16))
    update_display(startup_display)
    error("E900", "Shutdown process initiated")
    sleep(4)


    startup_display = (format_length("", 16), format_length(" done", 16))
    error("E901", "Shutdown process complete")
    update_display(startup_display)

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

def sys_startup_test(ex_value, config_vals):
    # Startup test functions, don't fuck with these

    if len(config_vals) != ex_value:
        return False, "c_v_failure"

    if parkes_version > configuration["parkes_vers"]:
        return False, "c_f_failure"

    if parkes_version < configuration["parkes_vers"]:
        return False, "p_v_failure"

    return True, "tests_passed"

# Parkes Configuration Interpreter 2.0 - PCI2.0

def cfg_type_set(definition):

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
    global configuration
    value = content[1:]

    key, definition = value.split("=")
    configuration[key] = cfg_type_set(definition)


def cfg_homedir(data):
    global configuration
    home_dir = data[4:]

    configuration["home_dir"] = home_dir

def cfg_telemetry(data):
    global configuration

    if data == "init":
        configuration["telemetry"] = {}

    elif data == "set":
        if "default" in data:
            configuration["telemetry"] = {"active": False, "connected": False, "sig_strength": 0, "hb_active": False, "hb_data":[], "hb_sigstrn":0, "hb_force_kill": False}

def cfg_errlog(data):
    if data == "init":
        new_file = open("parkes_errorlog.txt", "w")
        new_file.write("========== PARKES ERROR LOG ==========\n")
        new_file.write("Parkes Version: " + str(configuration["parkes_vers"])+"\n")
        new_file.write("--------------------------------------\n")
        new_file.write("")
        new_file.close()

    elif data == "clear":
        new_file = open("parkes_errorlog.txt", "w")
        new_file.close()

def cfg_exval(data):
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

def cfg_startuptest_ignore():
    global run_startup_test
    run_startup_test = False
    error("E202")

def cfg_kill_setup():
    return


def sys_config_interpreter(config_file):

    identifier_type = {
        "!" : "value",
        "$" : "command"
    }

    config_commands = {
        "ignore_startup_tests" : cfg_startuptest_ignore,
        "end_setup" : cfg_kill_setup
    }
    config_lines = config_file.readlines()

    for entry in config_lines:
        if entry[0] not in identifier_type.keys():
            continue
        identifier, content = entry[0], entry[1:]

        if identifier_type[identifier] == "value":
            cfg_set_value(content)

        elif identifier_type[identifier] == "command":

            if "." in content:

                target, command = content.split(".")

                cfg_run_command(target, command.rstrip())

            else:
                command = content.rstrip()

                config_commands[command]()

def sys_startup_test():
    startup_errors = {
        "p_v_failure"  :  "E105",
        "c_v_failure"  :  "E103",
        "c_f_failure"  :  "E106"
        }
    passed_test, reason = sys_startup_test(expected_value, configuration)

    if passed_test is True and reason in startup_errors.keys():
            error(startup_errors[reason], "startup_error: " + reason)
    else:
            error("E101")



# Main running loop
while configuration["go_reboot"] is True and configuration["go_kill"] is False:
    global run_startup_test
    global exptected_value
    run_startup_test, expected_value, configuration["go_reboot"] = True, 0, False
    config_file = open("/home/pi/Desktop/parkes_config.txt", "r")
    #config_lines = config_file.readlines()

    sys_config_interpreter(config_file)

    if run_startup_test is True:
        sys_startup_test()

    config_file.close()
    sys_startup()
    sleep(1)
    sys_main_menu()

sys_shutdown_process()
lcd.clear()
