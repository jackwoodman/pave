# novae file protocols

# pave_file - version beta 1

'''
    ==========================================================
    PAVE File Management Software, version beta 1
    Copyright (C) 2022 Jack Woodman - All Rights Reserved

    * You may use, distribute and modify this code under the
    * terms of the GNU GPLv3 license.
    ==========================================================
'''

def create(target_file, title, computer, version, id=None, extra=None):
    # File creation tool
    title_line = f"========== {title} ==========\n"
    bottom_line = "-" * len(title_line) + "\n"

    # open file
    with open(target_file, "w") as new_file:
        new_file.write(top_line)

        new_file.write(f"Software Version: {version}\n")

        # if software instance carries an id
        if (id and computer):
            new_file.write(f"{computer} ID: {id}\n")

        # add anything else required
        if (extra):
            new_file.write(f"{extra}\n")

        # finish up
        new_file.write(bottom_line)
        new_file.write("")

def append(target_file, data):
    # write to existing file
    with open(target_file, "a" open as opened_file:
        # write data to file
        opened_file.write(f"{data}\n")
