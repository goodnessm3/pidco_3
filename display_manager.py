from array import array

import omni
from dac_channels import PARAMETER_NAMES
from mydacs import DAC_MESSAGES
import controls

TOP_LINE = array("B", list([ord(" ") for x in range(16)]))  # initialize with spaces
BOTTOM_LINE = array("B", list([ord(" ") for x in range(16)]))
TO = 0  # where we filled the array to, so we know to overwrite
LAST_NUMBER = 0

def num2nums(num):

    """Decompose a number up to 1000 into the ASCII codes for each of its digits"""

    first = num // 100  # hundreds digit
    second = (num // 10) % 10  # tens digit
    third = num % 10

    return first+48, second+48, third+48  # offset to make printable ASCII character

def show_parameter():

    global TO

    old_to = TO
    name = PARAMETER_NAMES[omni.DISPLAYED_PARAMETER]
    TO = len(name)
    pos = 0
    for letter in name:
        TOP_LINE[pos] = ord(letter)
        pos += 1
    while pos < 16:
        TOP_LINE[pos] = 32  # space
        pos += 1  # todo - more advanced way to only update "dirty" cells on the LCD

    return 0, old_to

def show_number():

    global LAST_NUMBER

    v = DAC_MESSAGES.get(0, controls.SELECTED_PARAMETER)

    if not v == LAST_NUMBER:  # only ask the display to draw if something changed
        a, b, c = num2nums(v)
        BOTTOM_LINE[4] = a
        BOTTOM_LINE[5] = b
        BOTTOM_LINE[6] = c

        LAST_NUMBER = v

        return 3+16, 3  # +16 for bottom line
