from array import array
from fastlog2 import fast_log2
from settings import SM_FREQ, VOICE_COUNT, MAX_F
from dco_controls import freq2count

# lowest note on keyboard = 36
# highest note = 96

ARR_LENGTH = 140  # could be optimized. 33 plus however big the keyboard is plus some extra.
A1 = 55.00
NOTES = [0.0] * ARR_LENGTH  # there are unused very low notes
NOTE_VOLTAGES = array("I", [0] * ARR_LENGTH * VOICE_COUNT)  # what integrator voltage do we need for this freq?
NOTE_COUNTS = array("I", [0] * ARR_LENGTH)

# going from A1 as it's the lowest integer number
# 96 is the highest MIDI note on the keyboard
for q in range(VOICE_COUNT):
    max_freq = MAX_F[q]  # look up the highest possible freq this voice can play, which we measure manually
    for x in range(97):
        freq = round(A1 * 2**(x/12.0), 2)
        NOTES[x + 33] = freq  # store freq for diagnostic purposes but probably not used in any calculations
        NOTE_VOLTAGES[x + 33 + q * ARR_LENGTH] = int(freq/max_freq * 255)
        # take this freq as a proportion of the max freq and the integrator voltage scales linearly.

        cnt = freq2count(freq)
        NOTE_COUNTS[x+33] = cnt  # todo: we are redundantly writing these once per voice


def get_note_voltage(voice, note):

    """Returns the required integrator voltage for a given note and voice."""

    return NOTE_VOLTAGES[ARR_LENGTH * voice + note]

def get_note_sm_value(note):

    return NOTE_COUNTS[note]