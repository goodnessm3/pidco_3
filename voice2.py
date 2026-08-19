from array import array
from ADSR3 import ADSRS
from LFO2 import LFOS
from mydacs import DAC_MESSAGES
import omni
from dac_channels import *
from fastlog2 import fast_log2
from settings import *
from dco_controls import DCO_STATE_MACHINE_GENERATOR
import wavecount_table

class GlobalMods:

    def __init__(self):

        self.parameters = array("H", [0] * 8)  # baseline quantities to which we add modulations

    def get(self, channel):

        return self.parameters[channel]

GLOBALMODS = GlobalMods()

# set up an array where MIDI note index corresponds to the log2 wavecount. We send these numbers into the filter
# line fitter to determine what voltage to send to the filter to get this as the cutoff frequency.
#  TODO can we make this part of the wavecount_table?? Or somehow associate it with that?
A1 = 55.00
FILTER_CVS = array("I", [0] * 33)  # pad lower unavailable notes
# going from A1 as it's the lowest integer number
for x in range(100):
    freq = round(A1 * 2**(x/12.0),2)
    wavetime = 1.0 / freq
    counttime = 1.0 / SM_FREQ
    counts = int(wavetime / counttime)
    l = fast_log2(counts)
    #print(freq, l)
    FILTER_CVS.append(l)


class Voice:

    def __init__(self, address, adsrs=2, lfos=0):

        self.address = address
        self.active_adsrs = adsrs  # this is a bitmask that tells us which ADSRs to query. Default just to VCA.
        self.active_lfos = lfos
        self.oscillator = next(DCO_STATE_MACHINE_GENERATOR)

        #for x in range(8):
            #self.adsrs.append(LinearADSR())
        self.adsrs = ADSRS[address * 9: address * 9 + 9]  # todo - memoryview?????
        self.lfos = LFOS

        self.filter_fitter = None  # calculate volts per octave
        #print(self.adsrs)

        #self.base_values = array("H", [0] * 8)  # class-level parameters set by hardware sliders. Add our modulations
        # e.g. ADSRs and per-voice LFOs, to these variables

        self.key_counter = 0  # rather than true or false we need to increment/decrement a counter for "key rollover"

        self.held_note = 0  # MIDI note number for looking up filter CV, this is updated from the main loop

    def assign_filter_fitter(self):

        self.filter_fitter = omni.FILTER_VOLTAGE_CURVES[self.address]  # calculate volts per octave
        # this needs to be run after the filter fitters have been set up, which happens after the voices be instantiated


    def key_down(self):

        for x in self.adsrs:
            x.gate(True)
        self.key_counter += 1

    def key_up(self):

        self.key_counter -= 1
        if self.key_counter == 0:  # need this otherwise an old key up event will un-gate a newer note
            for x in self.adsrs:
                x.gate(False)

    def set_note(self, midinote):

        self.held_note = midinote
        voltage = wavecount_table.get_note_voltage(self.address, midinote)
        wavecount = wavecount_table.get_note_sm_value(midinote)
        DAC_MESSAGES.set(self.address, DAC_INTEGRATOR, voltage)
        #print(f"voice {self.address} sent {voltage} to its integrator")
        #print(f"voice {self.address} played note {midinote}")
        self.oscillator.put(wavecount)
        #print(f"voice {self.address} put oscillator counter {wavecount}")

    def update(self):

        addr = self.address
        todo_adsr = self.active_adsrs
        todo_lfo = self.active_lfos
        #print(todo_lfo)
        # todo_params = DIRTY_PARAMS  # a static parameter got changed by a slider

        chan = 0

        #print(VOICE_PARAMS)
        #print(todo_params)

        #while todo_adsr or todo_lfo or todo_params:
        while chan < 9:  # 0-7 for onboard dac and channel 8 is cof, this is dispatched differently by the DAC msg code
            #print(todo_lfo)
            if chan == DAC_INTEGRATOR:

                chan += 1
                todo_adsr >>= 1  # TODO: NOT ideal that we bit shift in two different places!!!
                todo_lfo >>= 1
                continue  # don't touch this

            modulation = omni.VOICE_PARAMS[chan]
            #if chan == DAC_CUTOFF:
                #print("filter slider mod is", modulation)

            if chan == DAC_CUTOFF:  # get the v/oct tracking as an additional mod source

                scale = omni.FILTER_V_OCT  # 0..65535 to scale the v/oct
                log2_note = FILTER_CVS[self.held_note]
                voct = self.filter_fitter.getx(log2_note)
                # somehow all the scales cancel each other out but I've lost track of what is what
                #print("voct from fitter is", voct)
                vocter = voct * scale >> 16
                modulation += vocter
                #print("Filter scale: ", scale)
                #print("Filter mod: ", modulation)
                #modulation -= 32767
                modulation -= FILTER_MOD_OFFSET
                # this is something to do with the difference between the cof and fundamental
                # we need to sort of invert the slider. Slider fully up -> 0 and filter is fully open
                # lower slider values = lower cutoff freq


            if todo_adsr & 1:
                val = self.adsrs[chan].get()
                modulation += val

            if todo_lfo & 1:
                #print("voice calling lfo", chan)
                val = self.lfos[chan].get(self.address)  # LFOs track the caller to do a unique phase offset
                modulation += val

            if modulation > 65535:  # filter mod may exceed the range due to v/oct tracking
                modulation = 65535  # apparently this is faster than using min, because no function call

            if modulation < 0:
                modulation = 0

            #if chan == DAC_CUTOFF:
                #print("filter mod after clipping is", modulation)

            # TODO: scaling for higher res cof DAC??!?!?!? 12 bit
            DAC_MESSAGES.set(addr, chan, modulation >> 8)  # TODO - is this the best place to scale down to 8 bit?
            todo_adsr >>= 1
            todo_lfo >>= 1
            #todo_params >>= 1
            chan += 1
