from array import array
from settings import *

# this module contains objects that might need to be reference in the global namespace from various places
FILTER_VOLTAGE_CURVES = [None] * VOICE_COUNT  # fitters to get control voltage for a specified cof
PWM_CURVES = [None] * VOICE_COUNT  # fitters to map the slider to 50..95% duty cycle

VOICE_PARAMS = array("H", [0] * 9)  # baseline values for cutoff, res etc, set by sliders
# line fitter objects for each voice to calculate required voltage for a filter cof. Address this list by index.
FILTER_V_OCT = 65535  # the actual max for the controls is 65024, so apply an offset of 511. This scales the amount
# of volts per octave that we apply to the filter response. This variable is changed from within the controls module.
DISPLAYED_PARAMETER = 0  # for the LCD
DISPLAY_DIRTY = False
RANDOM_SLOPE = 128  # controls how often the random mod source changes direction

try:
    with open("OMNIDATA.bin", "rb") as f:
        print("Loading general settings")
        idx = 0
        while idx < 9:  # first read in 9 values for the voice params array
            raw_bytes = f.read(2)
            VOICE_PARAMS[idx] = int.from_bytes(raw_bytes, "little")
            idx += 1
        raw_bytes = f.read(2)  # the leftover value is volts per octave scaling
        FILTER_V_OCT = int.from_bytes(raw_bytes, "little")

except Exception as e:
    print("Generic settings file not found, using defaults")


def save_omni():

    with open("OMNIDATA.bin", "wb") as f:
        for val in VOICE_PARAMS:
            f.write(val.to_bytes(2, "little"))
        f.write(FILTER_V_OCT.to_bytes(2, "little"))

