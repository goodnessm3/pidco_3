from pin_assignments import *
import machine
from machine import Pin
import time
from math import floor
import rp2
from rp2 import PIO, asm_pio
from array import array

#CS_PIN = Pin(21,Pin.OUT,Pin.PULL_UP)  # this is really address enable on the PCB test
RST_PIN = Pin(P_DAC_RESET,Pin.OUT,Pin.PULL_UP)
RST_PIN.low()
#CS_PIN.low()  # address enable is active HIGH

# old spi using actual proper built in code rather than bit-banged nonsense
"""
spi = machine.SPI(0,
                  baudrate=1000000,
                  polarity=0,
                  phase=0,
                  bits=8,
                  firstbit=machine.SPI.MSB,
                  sck=machine.Pin(18),
                  mosi=machine.Pin(19),
                  miso=machine.Pin(16))

"""


# custom SPI that manages CS transitions between 12-bit instructions
@asm_pio(
    out_init=PIO.OUT_LOW,
    set_init=PIO.OUT_LOW,
    sideset_init=PIO.OUT_LOW, #!!!!
    out_shiftdir=PIO.SHIFT_LEFT,
    autopull=False,
    pull_thresh=12,
)
def myspi():
    pull(block)  # wait here to load 32-bit value from RX FIFO
    #set(x, 1)  # two instructions are packed into a 32-bit word
    #label("outer")
    set(pins, 1)  # enable high -> CS low -> DAC starts listening
    irq(0)  # used to communicate with the tune latching pio, so it only toggles the latch when AEN is high
    set(y,15)  # counter for sending 16-bit DAC instruction
    label("bitloop")
    out(pins, 1).side(0) # put the data on MOSI pin and bring clock low
    nop().side(1)  # rising edge of clock so bit is read into DAC
    jmp(y_dec, "bitloop")  # repeat until we've written 16 bits of data
    irq(clear, 0)
    set(pins, 0)  # enable low -> CS high -> data is latched in

    #jmp(x_dec, "outer")  # loop back to send the second instruction

# address line manager, writes the binary address (0-7) to the output pins
@asm_pio(
    out_init=(PIO.OUT_LOW,) *3,
    out_shiftdir=PIO.SHIFT_RIGHT,
    autopull=False,

)  # pull_thresh=3,
def addressmgr():
    pull()
    out(pins, 3)


sm_spi = rp2.StateMachine(7, myspi, freq=1000000, out_base=Pin(P_MOSI_PIN),
    set_base=Pin(P_AEN_PIN),
    sideset_base=Pin(P_SCK_PIN))
sm_spi.active(1)


ADDRPIN = Pin(P_ADDRESS_BASE_PIN)

# 19, 20, 21 address pins
# this state machine is accessed from within the main program loop
ADDRESS_MANAGER = rp2.StateMachine(6, addressmgr, freq=1000000, out_base=ADDRPIN)
ADDRESS_MANAGER.active(1)

# no tuning for DCO based approach but maybe resurrect later for filter tuning
#TUNE_LATCH_MANAGER = rp2.StateMachine(6, tune_latch_manager, freq=1000000,
#                                      set_base=Pin(P_TUNE_LATCH_PIN),
#                                      )
#TUNE_LATCH_MANAGER.active(1)

#admgr.put(0)  # TODO - this is temporary, we eventually need to manage addresses of multiple DACs

def bytes_to_binary_string(bytes_data):
    """
    Converts a bytes object into a string representing its binary value.

    Args:
        bytes_data: A bytes object.

    Returns:
        A string representing the binary value of the bytes object.
    """
    binary_parts = []
    for byte in bytes_data:
        # Format each byte as an 8-bit binary string, zero-padded
        binary_parts.append(f"{byte:08b}")
    return "".join(binary_parts)


def make_dac_bytes(val, channel):

    """Ask the DAC to output a fraction (0-255) of its total voltage
    on channel 1 thru 8"""
    
    if type(val) is not int:
        raise ValueError("DAC expects an 8-bit value")
    
    chans = [0b1000,
             0b0100,
             0b1100,
             0b0010,
             0b1010,
             0b0110,
             0b1110,
             0b0001
        ]  # can't just use the channel number directly
    # because teh DAC expects it BACKWARDS.

    #amt = int(frac * 255.0)  # 8-bit DAC so work out the fraction of 255

    word = (chans[channel] << 8) | val

    return word

def make_dac_bytes_mcp(amt, dacbit=0):

    """for sending a value to the MCP4822
    dacbit = 0 or 1 for first or second channel (we only use one)"""

    prefix = 0b1  # shutdown bit, always 1 to keep on
    #amt = int(frac * 255.0)  # 8-bit DAC so work out the fraction of 255
    word = (prefix << 12) | (amt << 4) | (dacbit << 15)
    # todo - don't need the shift by 4 when we start sending higher res values from 12 bit DAC

    return word  # doesn't need to be bytes, custom state machine deals with arbitrary length messages
    #    return word.to_bytes(2, "big")

def send_dac_value_mcp(chan, val):

    msg = make_dac_bytes_mcp(val, chan)  # chan = dacbit in the old parlance
    write_to_dac(msg)


def dac_setup():
    
    time.sleep(1)  # DACs should be reset once power has stabilized
    RST_PIN.high()

    msg1 = 0b0000100100000000  # power down release
    msg2 = 0b0000001111111111  # all channels to analog output (I/O DA select)
    msg3 = 0b0000111111111111  # all channels to output mode (I/O status setting)

    write_to_dac(msg1)
    write_to_dac(msg2)
    write_to_dac(msg3)

    print("dac setup done")

def write_to_dac(b):

    sm_spi.put(b << 16)  # TODO: this currently only handles a single instruction
    # bit shift because it's a 32-bit word, but we only output 16 bits? I think?

def dummy_lcd_write(q):

    # 40012 = '1001110001001100'
    # 257 = 0000000100000001  the QA outputs of both shift registers are high
    # 1 = 0000000000000001  only the QA of the first chip is high
    # 256 = 0000000100000000  only the QA of the second chip is high
    # so we are sending the biggest bit first
    sm_spi.put(q << 16)

    # prototyping - QA is D0, Qb D1, 8th bit is D7 - from second SR
    # so 10000000 sends 1 to D7

    # FIRST register - QH, the lowest bit, is E
    # rw is second bit
    # 3rd bit is RS

def lcd_write(data, rs):

    RS = 0b00100000 if rs else 0b00000000  # register select, 0 for character, 1 for command
    RW = 0b01000000  # read/write, always zero. So not used here, but keep it as a note.
    EN = 0b10000000  # enable, data is clocked in at rising edge

    der = ((data << 8) | RS | EN)
    sm_spi.put(der << 16)  # put the command into the shift registers with enable = hi
    time.sleep(0.0001)  # TODO - NO SLEEP in PROPER VERSION
    der2 = ((data << 8) | RS )
    sm_spi.put(der2 << 16)  # now the data is presented at the pins, tell the LCD to load it in
    # data is latched in at falling edge of E pin
    time.sleep(0.0001)


def write_to_dac_old(b):

    """Expects a 16-bit command that will be split into two bytes for sending"""

    bs = b.to_bytes(2, "big")
    #print(bytes_to_binary_string(bs))
    CS_PIN.low()
    #time.sleep(0.001)
    spi.write(bs)
    #time.sleep(0.001)
    CS_PIN.high()
    #time.sleep(0.001)


def send_dac_value(dac, val):

    #print("sending val ", val, "to ", dac)

    if val < 0:
        #print(f"warning - {val} was clamped to 0")
        val = 0
        
    if val > 255:
        #print(f"warning - {val} was clamped to 255")
        val = 255

    msg = make_dac_bytes(val, dac)  # send val (0 to 255) to dac channel number
    write_to_dac(msg)

def send_dac_fraction(dac, val):

    """Set the dac with a float between 0.0 and 1.0, we translate it here to 8-bit"""

    v = floor(val * 255)
    send_dac_value(dac, v)


class DacMessages:

    """Manages DAC values."""

    def __init__(self):

        self.messages = array("B", [0] * 6 * 9)  # 9 channels on 6 dacs - 9th channel is the shared COF DAC
        self.dirty = 0  # 9 bits per voice

    def set(self, dac, channel, val):

        """Record a message that we want to send this value on dac x, channel y. These messages are read
        by the fast loop to determine what to send out to the DAC chip."""

        addr = dac * 9 + channel
        if not self.messages[addr] == val:
            self.dirty |= 1 << addr  # only set dirty flag if the value actually changed
            self.messages[addr] = val

    def add(self, dac, channel, val):

        """modify the value in the array, for example applying a modulation."""

        addr = dac * 9 + channel
        self.dirty |= 1 << addr  # only set dirty flag if the value actually changed
        self.messages[addr] += val

    def get(self, dac, channel):

        """Return the most recent value we wanted to write to dac x channel y."""

        addr = dac * 9 + channel
        return self.messages[addr]

    def get_dirty(self, dac):

        """Returns which channels for this DAC changed since we last checked.
        IMPORTANT: DESTRUCTIVE. Once we send this out, we re-zero the dirty flags
        under the assumption that all these values will be sent to the DAC."""

        out = (self.dirty >> (dac * 9)) & 511
        self.dirty &= (~out << (dac * 9))
        return out

DAC_MESSAGES = DacMessages()