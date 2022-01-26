# novae communications protocols

# pave_comms - version beta 1

'''
    ==========================================================
    PAVE Communication Software, version beta 1
    Copyright (C) 2022 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    ==========================================================
'''

# everything here is very, very new. 

def e_log(e, xtra=""):
    print(e, xtra)
    opened_file = open("er.txt", "a")
    opened_file.write(f"{e} - {xtra}\n")
    opened_file.close()

def vamp_compile(v_in, a_in, m_in, p_in):
    # create string from vamp
    command = f"v{v_in}_a{a_in}_m{m_in}_p{str(p_in).zfill(5)}\n"
    return command


def send(vamp, computer_radio):
    # accepts vamp in array/tuple form and sends

    # check enough components in VAMP to be split
    if (len(vamp) < 4):
        print("E205")

    try:
        # split VAMP into components
        v, a, m, p = vamp


    except:
        # could not split VAMP
        e_log("E310", str(vamp))

    # grab string of VAMP and encode
    command = vamp_compile(v, a, m, p)
    command_e = command.encode()

    # send command
    computer_radio.write(command_e)


def vamp_decompile(input_data):
    # break raw input into vamp list
    decom = []

    # break vamp by underscores into form ["vxxxx", "axxx", "mx", "pxxxx"]
    for element in input_data.split("_"):

        # remove letter signifier if is actually a letter
        if (element[0].isalpha()):
            decom.append(element[1:])

        else:
            # already been stripped of signifier
            decom.append(element)


    # check length of split vamp
    if (len(decom) < 4):
        # too short
        e_log("E206", decom)
        return

    elif (len(decom) > 4):
        # too long
        e_log("E207", decom)
        return

    try:
        # attempt decompile
        v, a, m, p = decom

        try:
            vamp = (int(v), int(a), int(m), int(p))
        except:
            vamp = (int(float(v)), int(float(a)), int(m), int(p))

    except:
        # could not decompile
        e_log("E311", (v,a,m,p))
        return

    # decompile succesful
    return vamp






def receive(computer_radio, timeout=False, timeout_duration=5):
    # receives command from required radio, allowing for timeout

    if (timeout):
        # set radio to timeout
        computer_radio.timeout = timeout_duration

    # receive from radio
    raw_data = computer_radio.read_until()

    # reset timeout flag (if originally set)
    if (timeout):
        computer_radio.timeout = None

    # decode
    try:
        data = raw_data.decode()
    except:
        e_log(raw_data)
        return "unknown failure"

    print(f"data is - {data}, raw is {raw_data}")
    if not (data):

        return "timeout"

    # convert to tuple
    final_data = vamp_decompile(data)

    # check timeout
    if not (final_data):
        # likely timeout
        e_log("E313", f"receive() - Connection timeout {final_data}")
        return "timeout"



    # succesfully received complete data
    return final_data
