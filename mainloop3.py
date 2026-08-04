import wavecount_table
from custom_fifo import CustomFIFO
from settings import *  # definitions of all constants used in the code
from pin_assignments import *
#from machine import Pin, I2C
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

from mydacs import send_dac_value, dac_setup, ADDRESS_MANAGER, prepare_tune_latch, DAC_MESSAGES, send_dac_value_mcp

time.sleep(1)

from filter_calibration import get_frequency_counts
from line_fitter_fixedpoint import FitterFP

# DAC setup code
#prepare_tune_latch()
#ADDRESS_MANAGER.put(7)  # unused address to force all latches off
#(2, 0)
"""
for x in range(10):
    ADDRESS_MANAGER.put(1)
    time.sleep(0.1)
    dac_setup()  # manages reset pin
    prepare_tune_latch()
    send_dac_value(4, 80)
    send_dac_value(5, 0)
    time.sleep(0.2)
    ADDRESS_MANAGER.put(0)
    time.sleep(0.1)
    dac_setup()  # manages reset pin
    prepare_tune_latch()
    send_dac_value(4, 80)
    send_dac_value(5, 0)
    time.sleep(0.2)

time.sleep(20)
"""

for x in range(VOICE_COUNT):
    #prepare_tune_latch()
    ADDRESS_MANAGER.put(x)
    time.sleep(0.1)
    dac_setup()  # manages reset pin


################### TESTING SETUP CODE #######################

cnt = 0
loopcount = 0
loopstart = time.ticks_ms()

"""
ADDRESS_MANAGER.put(0)
time.sleep(0.1)
dac_setup()  # manages reset pin
prepare_tune_latch()

ADDRESS_MANAGER.put(1)
time.sleep(0.1)
dac_setup()  # manages reset pin
"""
################### END OF SETUP FUNCTIONS #######################




  # manages values to be written to the DACs
RUNNING = False
NOTE_QUEUE = CustomFIFO(size=8)  # new notes we want to play. upper 4 bits: voice address, lower 8: MIDI note number

######### Temporary things for data logging ###########
#TIMES = array("I", [0] * 6096)
#EXPECTEDS = array("I", [0] * 6096)
#FREQS = array("i", [0] * 6096)



def shut_down():

    global RUNNING

    DAC_MESSAGES.set(0, 2, 0)
    DAC_MESSAGES.set(1, 2, 0)

    time.sleep(0.5)

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

configure_voice_list(VOICES)  # so that the controls module can alter the properties of the voice objects
HELD_NOTES = array("B", [0] * 150)  # record which voice is playing which note
VOICE_ALLOCATOR = VoiceAllocator(VOICE_COUNT)

from dco_controls import OSC  # todo - make better, multiple, etc

DAC_MESSAGES.set(0, DAC_WAVESELECT, 255)
time.sleep(0.001)
ADDRESS_MANAGER.put(7)
time.sleep(0.001)
send_dac_value_mcp(0, 255)
time.sleep(0.001)
ADDRESS_MANAGER.put(0)
time.sleep(0.001)

def calibration_loop():

    while 1:

        inst = input(">")
        dest = inst[:2]  # where to send the value, d1... d8 = DAC channel 1..8
        val = inst[2:]  # the value to send, 0-255
        if dest[0] == "d":  # a DAC channel
            chan = int(dest[1])
            val = int(val)
            print(f"sending {val} to DAC channel {chan}")
            if chan == 8 or chan == 9:  # special case, cutoff freq
                if chan == 8:
                    dacchan = 0
                else:
                    dacchan = 1
                ADDRESS_MANAGER.put(CUTOFF_FREQUENCY_DAC_ADDRESS)
                time.sleep(0.001)
                send_dac_value_mcp(dacchan, val)
                time.sleep(0.001)
                ADDRESS_MANAGER.put(0)
                send_dac_value(5, 0)  # force a new sample and hold
                time.sleep(0.001)

            else:
                time.sleep(0.001)
                send_dac_value(chan, val)
                time.sleep(0.001)
        if dest[0] == "f":  # frequency, set the DCO state machine
            val = int(val)  # in this case, ff066 means play midi note 66
            wavecount = wavecount_table.get_note_sm_value(val)
            OSC.put(wavecount)
        if dest[0] == "z":
            break


#calibration_loop()

def calibrate_voices():

    for x in range(VOICE_COUNT):
        startup_calibration(x)

def startup_calibration(voiceno):

    calcurve = FitterFP(size=5)  # important to give it the right number of samples for its size!!

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
        time.sleep(1)  # temp to see on the scope, make shorter after
        hi, lo = get_frequency_counts()
        logcnt = fast_log2(hi + lo)
        print(f"logcnt at {q} is {logcnt} Hz from {hi} {lo}")
        calcurve.add(q, logcnt)

    calcurve.fit_line()  # curve established. Can predict the log2(wavecnt) for an input voltage

    print("curve calibrated:")
    for q in (100, 200, 150, 120, 220):
        print(q, calcurve.gety(q << 8) >> 8)  # something about precision needs these bit shifts
        # todo - just put that nonsense inside the function


calibrate_voices()

while 1:

    #if PLAYING:
        #print(get_frequency())

    loopcount += 1
    #DISPLAY.draw_screen()
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
            PLAYING = True  # TEMPORARY testing thing for freq measure
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
        # print(new_note)
        midinote = new_note & 255
        voice = new_note >> 8
        #print("getting integrator voltage for ", voice, midinote)
        voltage = wavecount_table.get_note_voltage(voice, midinote)
        wavecount = wavecount_table.get_note_sm_value(midinote)

        DAC_MESSAGES.set(voice, DAC_INTEGRATOR, voltage)
        #print("integrator message", voice, DAC_INTEGRATOR, voltage)
        OSC.put(wavecount)

        #print(f"For note {midinote} voice {voice} voltages were {coarse}, {fine}")

        new_note = NOTE_QUEUE.get()

    for v in VOICES:
        v.update()

    # now that all the modulations are calculated, write out the DAC values
    for v in (0, 1, 2, 3):  # apparently faster than using a range object

        todo = DAC_MESSAGES.get_dirty(v)  # only update the values that have changed
        # this is a number where each bit denotes the DAC channel to be updated
        #print(todo)

        ##########
        # todo LISTINDEX error with ADSR on cof
        #########

        if todo:  # need to send the messages to this DAC, if not to do then we will skip the while loop, send nowt
            #time.sleep(0.001)
            ADDRESS_MANAGER.put(CUTOFF_FREQUENCY_DAC_ADDRESS)
            #time.sleep(0.001)
            cutoff = DAC_MESSAGES.get(v, 8)
            #time.sleep(0.001)
            send_dac_value_mcp(0, cutoff)  # this bus voltage will be sampled by the voice card during the time when its
            # chip select is brought low
            time.sleep(0.001)
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
            
        #send_dac_value(7, 0)





#except Exception as e:
    #print(repr(e))

#finally:
 #   pass
    #shut_down()
