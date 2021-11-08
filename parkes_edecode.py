# error decoder

# dependency of parkes_master.py, version 5.15 and up
vers = 1.2
def setup():
    nonfatal = {
        "00" : "Non-fatal runtime error",
        "01" : "Function could not run",
        "10" : "Telemetry dictionary is corrupted"
    }

    fatal = {
        "00" : "Fatal configuration error",
        "01" : "Failed startup_test()",
        "02" : "$expected_value.set=int command missing int argument",
        "03" : "$expected_value command missing operation argument",
        "04" : "Found configuration values does not equal expected configuration values",
        "05" : "Parkes version is out of date, update required",
        "06" : "Configuration file is out of date, update required",
        "07" : "hot_run not configured to bool",
        "20" : "DEPRECATED",
        "21" : "DEPRECATED",
        "22" : "VAMP could not be verified as string",
        "23" : "VAMP could not be verified as tuple",
        "99" : "error() function unable to determine error type"
    }

    warning = {
        "00" : "Could not complete operation",
        "01" : "Could not set value",
        "02" : "Startup tests have been disabled, proceed with caution",
        "03" : "Hardware display update error",
        "04" : "Parkes does not have an ignition system connected",
        "10" : "Forcing launch may cause fatal issues, proceed with caution",
        "50" : "Heartbeat couldn't be killed: no heartbeat active",
        "51" : "hb_count not 0 - resetting hb_count",
        "52" : "hb_status could not be determined",
        "60" : "Timeout - unable to connect to Epoch",
        "61" : "Epoch aborted ignition",
        "89" : "Serious error calling dsp_arm_sequence",
        "90" : "Hotfire is dangerous, proceed with caution",
        "92" : "Vega poll returned NO GO - autosequence abort",
        "93" : "Vega poll could not be resolved - autosequence abort",
        "94" : "Vega did not confirm autosequence start - autosequence abort",
        "95" : "Parkes QuickCheck failed - countdown abort",
        "96" : "Epoch poll could not be resolved - autosequence abort",
        "97" : "Epoch did not confirm autosequence start - autosequence abort",
        "98" : "Epoch poll returned NO GO - autosequence abort"
    }

    passive = {
    "02" : "Display update function failed - length error",
    "10" : "Error creating VAMP - not enough variables",
    "11" : "Error deconstructing VAMP - data may be corrupted",
    "12" : "Heartbeat connection timeout: could not establish connectionr",
    "13" : "cne_receive() - Connection timeout",
    "14" : "Error opening port - port already open",
    "20" : "Vega config update totally failed",
    "21" : "Vega config update partially failed",
    "22" : "Expected E321 data but did not receive it",
    "50" : "PGS update comparison failed",
    "51" : "No update found for PGS",
    "52" : "Update failed - could not connect",
    "53" : "Update failed - could not update file",
    "54" : "Update failed - update corruption detected",
    "99" : "go_reboot / go_kill detected",

    }

    message = {
        "00" : "Generic system message",
        "01" : "Shutdown process initiated",
        "03" : "PARKES WAKEUP",
        "04" : "Startup initiated",
        "09" : "Shutdown complete",
        "10" : "Opened port - parkes_radio",
        "11" : "Heartbeat loop initiated",
        "12" : "Heartbeat confirmation received",
        "13" : "Heartbeat confirmation received",
        "14" : "Heartbeat kill command received",
        "87" : "Launch commit marked",
        "88" : "Entering auto sequence",
        "89" : "Countdown ABORT",
        "90" : "Vega poll returned GO - Vega is configured for flight",
        "91" : "Parkes poll returned GO - Parkes is configured for flight",
        "92" : "Epoch poll returned GO - Epoch is configured for flight",
        "93" : "All systems are go!",
        "94" : "Entering preflight checks",
        "95" : "Ignition confirmation - entering downlink mode",
        "96" : "Exiting downlink on mode 6 - landed and safe!",
        "97" : "Exiting downlink on mode 7 - error or unknown",
        "98" : "Launch countdown commit",
        "99" : "Ignition!"
    }

    errors = [nonfatal, fatal, warning, passive, message]
    index_count = 0
    for errorType in errors:
        index_count += len(errorType)
    return (errors, index_count)

def error_decoder(key):
    errors, index_count = setup()
    nonfatal, fatal, warning, passive, message = errors
    if (len(key) > 3):
        return f"Error code is too long. ({key})"
    error_type = key[0]
    error_id = key[1:3]

    type_dict = {
        "0" : nonfatal,
        "1" : fatal,
        "2" : warning,
        "3" : passive,
        "9" : message
    }

    try:
        error_definition = type_dict[error_type][error_id]
    except:
        error_definition = f"Error code does not exist/is not indexed. ({key})"

    return error_definition

def console_gui():
    errors, index_count = setup()
    print(f"\nPAVE Error Decoder v{vers}")
    print(f" - {index_count} errors indexed")
    print()
    while True:
        print('Input error code below: ')
        error = str(input("E"))
        print("\n")

        type_dict = {
            "0" : "non-fatal",
            "1" : "fatal",
            "2" : "warning",
            "3" : "passive",
            "9" : "message"
        }

        try:
            e_type = type_dict[error[0]]
        except:
            e_type = "unknown"

        print("----------------------------")
        print("ERROR CODE: E" + error)
        print("ERROR TYPE: " + e_type)
        print("----------------------------")
        print('Defintion: ')
        print("    " +error_decoder(error))
        print(" ")
        print(" \n")
