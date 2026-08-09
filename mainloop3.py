import wavecount_table
from custom_fifo import CustomFIFO
from settings import *  # definitions of all constants used in the code
from pin_assignments import *
from machine import Pin, I2C
import time
from sys import exit
import _thread
from fastlog2 import fast_log2
from array import array

from dac_channels import *

from voice_allocator import VoiceAllocator

from readmidi import MidiReader
from voice2 import Voice
from controls import Controls, configure_voice_list

from mydacs import send_dac_value, dac_setup, ADDRESS_MANAGER, DAC_MESSAGES, send_dac_value_mcp

time.sleep(1)

from filter_calibration import get_frequency_counts
from line_fitter_fixedpoint import FitterFP

from omni import FILTER_VOLTAGE_CURVES

from lcd1602 import LCD
from ADSR3 import save_adsrs


i2c = I2C(1, scl=Pin(P_I2C_SCL), sda=Pin(P_I2C_SDA))  # for driving the LCD
# I2C block 1 is associated with pins 26 and 27 (defined in pin assignments file)
DISPLAY = LCD(i2c)  # set up the text display

for x in range(VOICE_COUNT):
    #prepare_tune_latch()
    ADDRESS_MANAGER.put(x)
    time.sleep(0.1)
    dac_setup()  # manages reset pin


################### TESTING SETUP CODE #######################

cnt = 0
loopcount = 0
loopstart = time.ticks_ms()

################### END OF SETUP FUNCTIONS #######################

RUNNING = False
NOTE_QUEUE = CustomFIFO(size=8)  # new notes we want to play. upper 4 bits: voice address, lower 8: MIDI note number

def shut_down():

    global RUNNING

    DAC_MESSAGES.set(0, 2, 0)
    DAC_MESSAGES.set(1, 2, 0)

    time.sleep(0.5)

    save_adsrs()
    print("ADSR data saved")

    RUNNING = False

    print("Shutting down...")
    #print("count", loopcount)
    total_time = time.ticks_diff(time.ticks_ms(), loopstart)

    lps = loopcount / total_time * 1000
    print(f"Averaged {lps} loops per second over {total_time} ms.")
    #send_dac_value(2, 0)
    print("VCA muted")
    time.sleep(1)  # make sure other core has time to exit
    print("Shutdown function finished")

    time.sleep(0.5)

    exit()


MR = MidiReader()
CONTROLS = Controls()
VOICES = []
for x in range(VOICE_COUNT):
    VOICES.append(Voice(x))

configure_voice_list(VOICES)
HELD_NOTES = array("B", [0] * 150)  # record which voice is playing which note
VOICE_ALLOCATOR = VoiceAllocator(VOICE_COUNT)

"""
DAC_MESSAGES.set(0, DAC_WAVESELECT, 255)
time.sleep(0.001)
ADDRESS_MANAGER.put(7)
time.sleep(0.001)
send_dac_value_mcp(0, 255)
time.sleep(0.001)
ADDRESS_MANAGER.put(0)
time.sleep(0.001)
"""

def calibrate_voices():

    for x in range(VOICE_COUNT):
        startup_calibration(x, FILTER_VOLTAGE_CURVES=FILTER_VOLTAGE_CURVES)

def startup_calibration(voiceno, FILTER_VOLTAGE_CURVES):

    calcurve = FitterFP(size=5)  # important to give it the right number of samples for its size!!
    FILTER_VOLTAGE_CURVES[voiceno] = calcurve

    ADDRESS_MANAGER.put(voiceno)
    calibration_messages = [(DAC_VCA, 255),  # VCA fully open
                            (DAC_PWM, 127),  # PWM comparator at half
                            (DAC_RESONANCE, 255),  # full self resonance to calibrate filter response
                            ]

    for msg in calibration_messages:
        dest, value = msg
        time.sleep(0.001)
        send_dac_value(dest, value)

    time.sleep(0.001)
    for q in (100, 200, 150, 120, 220):

        ADDRESS_MANAGER.put(CUTOFF_FREQUENCY_DAC_ADDRESS)  # always 8
        send_dac_value_mcp(0, q)  # channel 0 of the 2-ch 12 bit DAC is the COF, chan 1 probably unused
        time.sleep(0.001)
        ADDRESS_MANAGER.put(voiceno)
        send_dac_value(DAC_DUMMY, 0)  # force a new sample of the COF voltage by asserting chip select
        time.sleep(0.1)  # temp to see on the scope, make shorter after
        hi, lo = get_frequency_counts()
        logcnt = fast_log2(hi + lo)
        print(f"logcnt at {q} is {logcnt} Hz from {hi} {lo}")
        calcurve.add(q, logcnt)

    calcurve.fit_line()  # curve established. Can predict the log2(wavecnt) for an input voltage

    print("curve calibrated:")
    for q in (220, 200, 150, 120, 100):
        print(q, calcurve.gety(q << 8) >> 8)  # something about precision needs these bit shifts
        # todo - just put that nonsense inside the function
        # todo - affects DAC resolution


calibrate_voices()  # set up filter curves

for v in VOICES:
    v.assign_filter_fitter()  # now fitters are calibrated we can tell the voices which to use

from display_manager import DisplayManager

DM = DisplayManager([],[],[])

pair = DM.update((1,))  # get a new frame buffer for the LCD
DISPLAY.update(pair)  # send the new frame buffer for display next loop

while 1:

    loopcount += 1
    DISPLAY.draw_screen()
    MR.read()  # induce the MidiReader to compile messages to read out

    while 1:
        note_message = MR.note_queue.get()

        if not note_message:
            break
        #print(note_message)
        status = (note_message & 256) >> 8  # 1 = note on, 0 = note off
        note = note_message & 255
        #print(status,note)
        if status:
            voice = VOICE_ALLOCATOR.next()
            VOICE_ALLOCATOR.key_down(voice)
            NOTE_QUEUE.put(note | (voice << 8))
            VOICES[voice].key_down()
            HELD_NOTES[note] = voice
        else:
            voice_index = HELD_NOTES[note]
            VOICES[voice_index].key_up()
            VOICE_ALLOCATOR.key_up(voice_index)

    while 1:
        control_message = MR.control_queue.get()
        if not control_message:
            break
        a = control_message >> 8
        b = control_message & 255
        #print(a, b)
        if a == 23 and b == 254:
            shut_down()
        CONTROLS.process_control_signal(control_message)
        
    # process the note queue
    new_note = NOTE_QUEUE.get()
    while new_note:  # set up tuning of the new note

        midinote = new_note & 255
        voice = new_note >> 8
        VOICES[voice].set_note(midinote)
        new_note = NOTE_QUEUE.get()

    for v in VOICES:
        v.update()

    # now that all the modulations are calculated, write out the DAC values
    for v in (0, 1, 2, 3):  # apparently faster than using a range object

        todo = DAC_MESSAGES.get_dirty(v)  # only update the values that have changed
        # this is a number where each bit denotes the DAC channel to be updated

        if todo:  # need to send the messages to this DAC, if not to do then we will skip the while loop, send nowt
            #time.sleep(0.001)
            ADDRESS_MANAGER.put(CUTOFF_FREQUENCY_DAC_ADDRESS)
            #time.sleep(0.001)
            cutoff = DAC_MESSAGES.get(v, 8)
            #time.sleep(0.001)
            #print("sending cof value", cutoff)
            send_dac_value_mcp(0, cutoff)  # this bus voltage will be sampled by the voice card during the time when its
            # chip select is brought low
            time.sleep(0.0001)  # TODO: can we get away from this sleep!??!
            ADDRESS_MANAGER.put(v)

        chan = 0
        while todo and chan < 8:  # the 9th channel was handled above, so don't send it here
            #print("todo lopp")
            if todo & 1:
                val = DAC_MESSAGES.get(v, chan)
                # print(f"sending {val} to {chan} on dac {v}")
                send_dac_value(chan, val)  # puts the message into the state machine FIFO
            todo >>= 1
            chan += 1

        if todo:  # deals with the case where the ONLY modulation was for the cutoff, in this case, we need to
            # write a "dummy" message to the DAC so that the cutoff control voltage can be sampled
            send_dac_value(5, 0)  # channel 5 is unused and unconnected, so harmlessly write to it
            # which induces a chip select toggle
