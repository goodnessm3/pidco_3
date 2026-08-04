from array import array

VOICE_COUNT = 1
SM_FREQ = 100_000_000
MAX_F = [2200, 2200]   # per voice, need to manually measure the freq at which 5 volts integrator charge
# gives a 0 to 9.6 V signal (build in a comparator and peak detector to calibrate this)

# TODO: calibration routine
