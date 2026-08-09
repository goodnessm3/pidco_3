from array import array

VOICE_COUNT = 1
SM_FREQ = 100_000_000  # the speed that the frequency counter runs. Too fast and we might underflow if using 16 bit cnt
MAX_F = [2200, 2200, 2200, 2200, 2200, 2200]   # per voice, need to manually measure the freq at which 5 volts integrator charge
# gives a 0 to 9.6 V signal (build in a comparator and peak detector to calibrate this)
FILTER_MOD_OFFSET = 16000  # subtracted from the filter signal and sets the max difference between the played note freq
# and the filter cutoff freq. Value chosen so that it will be > 20 kHz at the highest note
DCO_PINS = [13, 12, 11, 10, 9]
DCO_FREQ = 1953125  # magic number from some internet article, maybe the precise value isn't important??

# TODO: calibration routine
