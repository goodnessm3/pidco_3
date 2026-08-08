from array import array
from settings import *

# this module contains objects that might need to be reference in the global namespace from various places

VOICE_PARAMS = array("H", [0] * 9)  # baseline values for cutoff, res etc, set by sliders
FILTER_VOLTAGE_CURVES = [None] * VOICE_COUNT
# line fitter objects for each voice to calculate required voltage for a filter cof. Address this list by index.
FILTER_V_OCT = 65535  # the actual max for the controls is 65024, so apply an offset of 511. This scales the amount
# of volts per octave that we apply to the filter response.