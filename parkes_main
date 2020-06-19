# Parkes UI

from time import sleep
from random import randint
import threading
##from datetime import datetime
##from RPLCD.gpio import CharLCD
##import RPi.GPIO as GPIO

# To-Do:

#  


""" cha cha real smooth """



##lcd = CharLCD(cols=16, rows=2, pin_rs=37, pin_e=35, pins_data=[33, 31, 29, 23], numbering_mode=GPIO.BOARD)

parkes_version = 0.3
##GPIO.setwarnings(False)
##GPIO.setmode(GPIO.BOARD)
##
### Button setup
##GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Back button - GPIO 23
##GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Select button - GPIO 24
##GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Cycle button - GPIO 25

global configuration

configuration = {
    "go_reboot": True,
    "go_kill": False}

def vowel_remover(word):
    # This function removes vowels from words
    # It took far too long to make
    vowels = ["a","e","i","o","u"]
    new_word = []

    word_list = list(word)
    has_taken = False
    for x in word_list[::-1]:
         if x not in vowels or has_taken is True:
            new_word.append(x)
         else:
            has_taken = True

    to_return_list = new_word[::-1]
    to_return_word = "".join(to_return_list)
    
    if to_return_word != word:
        return to_return_word, True

    else:
        return to_return_word, False
            


def error(e_code):
    # Error driver: don't fuck with this
    if e_code[1] == "0":
        error_type = "nonfatal"
    elif e_code[1] == "1":
        error_type = "fatal"
    elif e_code[1] == "2":
        error_type = "warning"
    else:
        error_type = "invalid"

    topline = "ERROR:  " + format_length(e_code, 8)

    if error_type == "nonfatal":
        current_select = False

        while True:
            if current_select == True:
                bottom_line = "|RBT| / SHUTDWN "
            else:
                bottom_line = " RBT / |SHUTDWN|"

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
                    con_reboot()
                    break
                elif current_select == False:
                    con_shutdown()
                    break
    elif error_type == "fatal":
        bottom_line = " FATAL ERROR    "
        yesno_display = (topline, bottom_line)
        update_display(yesno_display)
        while True:
            waiting = True

    elif error_type == "warning":
        bottom_line = "   |CONTINUE|   "
        yesno_display = (topline, bottom_line)
        update_display(yesno_display)
        wait_select()
        

    elif error_type == "invalid":
        error("E199")
        
        
    
    

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
                result = vowel_remover(new_string)
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
        
            
def Pbutton_input():
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


def button_input():
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
            

def Pupdate_display(display_input):
    # Checks length of top and bottom line
    # If suitable, combines and updates display
    # Else, returns error code
    top_line, bottom_line = display_input


    if len(top_line) <= 16 and len(bottom_line) <= 16:
        send_to_display = top_line + bottom_line
        lcd.write_string(send_to_display)
        return 1
    else:
        error("E107")



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

        
            
def startup_animation():
    # Loading bar, will tie into actuall progress soon
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
            
def startup():
    sleep(1)
    startup_display = (format_length("PARKES v" + str(parkes_version), 16),  format_length("loading", 16))
    update_display(startup_display)
    sleep(0.4)
    
    startup_animation()
    startup_display = (format_length("", 16), format_length(" READY", 16))
    update_display(startup_display)
    sleep(1)

def launch_launch():
    if_we_ever = "have to use this i'll be surprised"
    error("E001")


def launch_arm():
    this_one = "will hopefully be used god forbid"
    error("E001")

def launch():

    launch_func_dict = {
        1 : ["ARM VEGA", launch_arm],
        2 : ["LAUNCH", launch_launch]
        }
    
    current_select = 1
    while True:
        current_func_name, current_func = launch_func_dict[current_select]

        top_line = "LAUNCH:      " + str(current_select) + "/" +str(len(launch_func_dict))
        bottom_line = "=> " + format_length(current_func_name, 13)
        launch_menu_display = (top_line, bottom_line)
        update_display(launch_menu_display)

        choose = button_input()
        if choose == "cycle":
            if current_select != len(launch_func_dict):
                current_select += 1
            else:
                current_select = 1
        elif choose == "back":
            break
        elif choose == "select":
            current_func()

        # Exit to menu, don't write below here

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

def con_cursor():
    # Config: manually reset cursor
    result = yesno("RESET CURSOR")
    if result == True:
        lcd.cursor_mode = hide
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
    
    

def cne_send(vamp):
    # Sends command over radio
    try:
        v, a, m, p = vamp
    except:
        error("E121")
    command = "v"+str(v)+"_a"+str(a)+"_m"+str(m)+"_p"+str(p)

    print(command)

def cne_vamp_destruct(vamp):
    vamp_decom = []
    for element in vamp.split("_"):
        vamp_decom = element[1:]

    try:
        v, a, m, p = vamp_decom
    except:
        error("E120")
    vamp = (int(v), int(a), int(m), int(p))
     
    return vamp


def cne_heartbeat():
    # Heatbeat func - will be threading
    configuration["telemetry"]["hb_active"] = True
    receiving = True
    heartbeat_init_vamp = (10000, 0000, 8, 00000)

    cne_send(heartbeat_init_vamp)
    hb_count = 0
    
    while configuration["telemetry"]["hb_force_kill"] == False:
        rec_string = "received data"  # PLACEHOLDER
        rec_vamp = cne_vamp_destruct(rec_string)
        configuration["telemetry"]["hb_data"].append(rec_vamp)
        sleep(1)
        
        hb_count += 1
        
        configuration["telemetry"]["hb_sigstrn"] = hb_count // rec_vamp[3]

    configuration["telemetry"]["hb_active"] = False
    configuration["telemetry"]["hb_data"] = []
    configuration["telemetry"]["hb_sigstrn"] = 0
      

def cne_heartbeat_thread():
    force_kill = False
    # Moves the heartbeat function into its own function
    cne_hb_thread = theading.Thead(target=cne_heartbeat)
    cne_hb_thread.start()
            

def cne_handshake():
    global configuration
    handshake_confirmed = False

    configuration["telemetry"]["active"] = True

    # Set handshake vamp
    handshake_vamp = (10000, 1000, 0, 00000)

    # Loop to send handshake / await response
    while handshake_confirmed == False:
        cne_send(handshake_vamp)

        if received_confirmation is True:   # PLACEHOLDER
            handshake_confirmed = True

    cne_heartbeat_thread()

def cne_kill_heartbeat():
    # Finish the heartbeat thread
    cne_hb_thread.join()
    configuration["telemetry"]["hb_force_kill"] = True

def cne_connect():
    global configuration

    cne_handshake()
    configuration["telemetry"]["connected"] = True
    
    
def connect():
    global configuration

    connect_func_dict = {
        1 : ["CONNECT", cne_connect],
        2 : ["STATUS", cne_status]
        }

    current_select = 1
    while True:

        current_func_name, current_func = connect_func_dict[current_select]
        
        top_line = "CONNECT:     " + str(current_select) + "/" +str(len(connect_func_dict))
        bottom_line = "=> " + format_length(current_func_name, 12)  # IF THIS BREAKS, ITS THE FUCKING FORMAT_LENGTH FUNC
        connect_menu_display = (top_line, bottom_line)
        update_display(connect_menu_display)

        choose = button_input()
        if choose == "cycle":
            if current_select != len(connect_func_dict):
                current_select += 1
            else:
                current_select = 1
        elif choose == "back":
            break
        elif choose == "select":
            if current_select == 7:
                current_func()
            else:
                current_func()



def config():
    # Main: select config function
    global configuration

    config_func_dict = {
        1 : ["INPUT DELAY", con_delay],
        2 : ["BEEP", con_beep],
        3 : ["CURSOR RESET", con_cursor],
        4 : ["CONFIG VALUES", con_display],
        5 : ["REBOOT", con_reboot],
        6 : ["ERROR TEST", con_etest],
        7 : ["SHUTDOWN", con_shutdown]
        }

        
    current_select = 1
    while True:

        current_func_name, current_func = config_func_dict[current_select]
        
        top_line = "CONFIG:      " + str(current_select) + "/" +str(len(config_func_dict))
        bottom_line = "=> " + format_length(current_func_name, 12)  # IF THIS BREAKS, ITS THE FUCKING FORMAT_LENGTH FUNC
        config_menu_display = (top_line, bottom_line)
        update_display(config_menu_display)

        choose = button_input()
        if choose == "cycle":
            if current_select != len(config_func_dict):
                current_select += 1
            else:
                current_select = 1
        elif choose == "back":
            break
        elif choose == "select":
            if current_select == 7:
                current_func()
            else:
                current_func()
            
        # Exit to menu, don't write below here
    # Exit to menu, don't write below here

        
def main_menu():
    # Parkes: main menu selection 
    global configuration

    main_func_dict = {
        1 : ["CONFIG", config],
        2 : ["CONNECT", connect],
        3 : ["LAUNCH", launch]
        }
    
    current_select = 1
    while True:

        current_func_name, current_func = main_func_dict[current_select]

        top_line = "PARKES v" + str(parkes_version) + "  " + str(current_select) + "/" +str(len(main_func_dict))
        bottom_line = "=> " + format_length(current_func_name, 13)
        main_menu_display = (top_line, bottom_line)
        update_display(main_menu_display)

        choose = button_input()
        if choose == "cycle":
            if current_select != len(main_func_dict):
                current_select += 1
            else:
                current_select = 1
        elif choose == "select":
            current_func()
        
        if configuration["go_reboot"] is True or configuration["go_kill"] is True:
            break

        
        
        
    
def update_display(display_input):
    # Driver code for display emulation
    top_line, bottom_line = display_input
    print()
    print(" ________________")
    print("|" + str(top_line) + "|")
    print("|" + format_length(str(bottom_line),16) + "|")
    print("|________________|")
    print()

def shutdown_process():
    
    sleep(1)
    startup_display = ("PARKES v" + str(parkes_version) + "     ", format_length("shutting down", 16))
    update_display(startup_display)
    sleep(4)
    

    startup_display = (format_length("", 16), format_length(" done", 16))
    update_display(startup_display)
    sleep(2)
    



def get_type(newval):
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
            
def startup_test(ex_value, config_vals):
    # Startup test functions, don't fuck with these

    if len(config_vals) != ex_value:
        return False, "c_v_failure"

    if parkes_version > configuration["parkes_vers"]:
        return False, "c_f_failure"

    if parkes_version < configuration["parkes_vers"]:
        return False, "p_v_failure"

    return True, "tests_passed"
        

# Main running loop
while configuration["go_reboot"] is True and configuration["go_kill"] is False:
    run_startup_test = True
    expected_value = 0
    configuration["go_reboot"] = False
    config_file = open("parkes_config.txt", "r")
    config_lines = config_file.readlines()


    for entry in config_lines:

        # Configuration Import Values
        if entry[0] == "!":
            entry_val = entry[2:]
            key, definition = entry_val.split("=")
            
            if get_type(definition) == "int":
                newdef = int(definition)
                
            elif get_type(definition) == "bool":
                if definition == "True":
                    newdef = True
                else:
                    newdef = False
                    
            elif get_type(definition) == "float":
                newdef = float(definition)
                
            elif get_type(definition) == "string":
                newdef = str(definition)[:-1]

            configuration[key] = newdef

        # Configuration Import Commands
        elif entry[0] == "$":
            command = entry[1:]
            print(command)
            if "." in command:
                split_command = command.split(".")


                if split_command[0] == "telemetry":
                    if split_command[1][:-1] == "init":
                        configuration["telemetry"] = {}
                        
                    elif "set" in split_command[1]:
                        if "default" in split_command[1]:
                            configuration["telemetry"] = {"active": False, "connected": False, "sig_strength": 0, "hb_active": False, "hb_data":[], "hb_sigstrn":0, "hb_force_kill": False}
                            
                            

                if split_command[0] == "expected_value":

                    if split_command[1][:-1] == "init":
                        expected_value = 0

                    elif split_command[1][:-2] == "set=":
                        value = split_command[1].split("=")
                        try:
                            expected_value = int(value[1])

                        except:
                            error("E102")
                    else:
                        error("E103")
                        
            command = command[:-1]

            if command == "ignore_startup_tests":
                run_startup_test = False
                error("E202")    

            elif command == "end_setup":
                break

    # Startup test results
    if run_startup_test is True:
        passed_test, reason = startup_test(expected_value, configuration)

        if passed_test is False:
            startup_errors = {
                "p_v_failure"  :  "E105",
                "c_v_failure"  :  "E103",
                "c_f_failure"  :  "E106"
                }
            if reason in startup_errors.keys():
                error(startup_errors[reason])

            else:
                error("E101")
            
    config_file.close()
    startup()
    sleep(1)
    main_menu()


shutdown_process()
lcd.clear()
