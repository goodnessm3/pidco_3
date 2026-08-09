from machine import Pin
import time
import math
import rp2
from rp2 import PIO, asm_pio
from settings import DCO_PINS, DCO_FREQ

@rp2.asm_pio(
    set_init=rp2.PIO.OUT_LOW,
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
)
def dco_signal():
    wrap_target()
    pull(noblock)  # pull a value from the FIFO into the OSR
    mov(y, osr)         # move contents of OSR into y
    mov(x, osr)  # IMPORTANT! x is copied to y when pulling from empty FIFO
    set(pins, 1)        # high
    label("high")
    jmp(y_dec, "high")  # jump to high if y != 0, and decrement y
    mov(y, osr)         # move contents of OSR into y, "refreshing" y
    set(pins, 0)        # low
    label("low")
    jmp(y_dec, "low")
    wrap()

def freq2count(f):
    """How high the state machine needs to count to make this freq"""

    if f == 0:
        return 0
    return round(float(DCO_FREQ) / f / 2)

# PIO blocks 6 and 7 are used for address manager and SPI, 0-5 can be for DCOs
# block 5 will be used for the freq counter in testing mode - 08/02
#OSC = rp2.StateMachine(0, dco_signal, freq=1953125, set_base=Pin(13))
#OSC.active(1)

def dco_state_machine_generator():

    idx = 0
    p = DCO_PINS[idx]  # find the next output pin for the DCO - hard coded because hard wired
    while idx < 5:  # todo - if we want 6-voice polyphony, need to steal the freq measurement PIO
        sm = rp2.StateMachine(idx, dco_signal, freq=DCO_FREQ, set_base=Pin(p))
        sm.active(1)
        yield sm
        idx += 1

DCO_STATE_MACHINE_GENERATOR = dco_state_machine_generator()  # query this to get state machines