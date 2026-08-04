from settings import *  # definitions of all constants used in the code
from pin_assignments import *
from rp2 import PIO, asm_pio
import machine
import rp2
from fastlog2 import fast_log2
from array import array

freq_pin = machine.Pin(P_FREQ_COUNTER, machine.Pin.IN, pull=None)

SAMPLE_ARRAY = array("I", [0] * 16)

@asm_pio(autopush=True, fifo_join=PIO.JOIN_RX)
def freq_counter():
    # pull(noblock)      # Load max counter value to OSR
    mov(x, invert(null))  # Reset Counter
    # HIGH phase count - decrement counter while the input signal is high
    label("count")
    jmp(pin, "decrementing")  # if high cycle, decrement the counter
    jmp("write")  # fell through because wave went low, unconditional jump to write out this count
    label("decrementing")
    jmp(x_dec, "count")
    label("write")
    mov(isr, x)        # Capture count
    in_(x, 32)  # shift 32 bits to the ISR (to be read out by the python code)
    # push(noblock)  # not needed because autopush is set
    mov(x, invert(null))  # Reset Counter immediately
    # LOW phase count - decrement counter while input signal is low
    label("count2")  #
    jmp(pin, "lowwrite")  # escape the decrementing loop one the signal goes high again
    jmp(x_dec, "count2")
    label("lowwrite")
    mov(isr, x)  # Capture count
    in_(x, 32)  # shift 32 bits to the ISR (to be read out by the python code)
    # loop around to the top and start counting in high phase again

sm_freq_counter = rp2.StateMachine(5, freq_counter, freq=SM_FREQ, jmp_pin=freq_pin)
sm_freq_counter.active(1)  # todo: eventually this will only be used during calibration phase

def get_frequency_counts():

    """Blocking function that monitors the frequency at the measurement pin. Return frequency in Hz
    and duty cycle as a float from 0 to 1"""

    MAXX = (1 << 32) - 1

    counts = 0
    fifosize = sm_freq_counter.rx_fifo()

    if fifosize == 0:
        return  # for some reason no frequency counts are appearing

    for x in range(16):
        _ = sm_freq_counter.get()  # flush out old values

    while counts < 16:
        # accumulate 32 wave cycles into the array
        SAMPLE_ARRAY[counts] = MAXX - sm_freq_counter.get()  # the freq counter counts DOWN so subtract from 2**32-1
        counts += 1

    # now compute the mean of the hi and lo cycles. No guarantee which is which, hi or lo, but generally doesn't matter
    # might not even matter at all if we never try and calibrate PWM using this

    c1 = 0
    c2 = 0

    for x in range(16):
        if x % 2 == 0:
            c1 += SAMPLE_ARRAY[x]
        else:
            c2 += SAMPLE_ARRAY[x]

    return c1//8, c2//8  # if you just wanted the raw hi, lo counts

    '''
    h = c1//8
    l = c2//8

    # to convert this tuple into a frequency in Hz, do 10**8 / ((26568.0 + 30455.0)) / 2
    # 100 MHz, divided by the total cycle time, divided by 2 because of the time taken per loop (2 instructions)
    # but better to stay with reciprocal of frequency to avoid needing floats

    freq = 10**8 / (h + l) / 2   # the frequency in Hz
    duty = float(h) / (h + l)  # UNKNOWN which is high or low, but we can work it out

    print("hi and lo were", h, l)

    return freq, duty
    
    '''


