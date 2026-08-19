import time
from array import array

from settings import VOICE_COUNT


class LinearADSR:

    def __init__(self, a=300, d=1000, s=20000, r=450, depth=0, inverted=0):

        #print("made ADSR with args ", a, d, s, r, depth, inverted)

        self.max_level = 65535
        self.sustain_level = s
        self.depth = depth

        self.rates = array("i", [0] * 5)  # how much we should increment/decrement the bucket per millisecond
        self.raw_rates = array("I", [0] * 5)  # for saving and loading

        self.set_rate(1, a)
        self.set_rate(2, d)
        self.set_rate(4, r)

        self.phase = 0  # 0 = quiescent, 1 = atk, 2, dky, 3 = sus, 4 = rel. These are used as array indices
        self.last_called = time.ticks_ms()
        self.bucket = 0

        self.inverted = inverted == 1  # need to pass the argument as 1/0 so it can be written out to a file

    def export(self):

        """Generate a tuple of args that can be used to reinstantiate this object with the same properties"""

        if self.inverted:
            inv = 1
        else:
            inv = 0

        return (self.raw_rates[1],
                self.raw_rates[2],
                self.sustain_level,
                self.raw_rates[4],
                self.depth,
                inv)

    def set_rate(self, rate_index, time):

        """a = 1, d = 2, r = 3. Time = the length of the phase in milliseconds from max to min"""

        """These numbers specify the gradient of each phase, i.e. how much the bucket in/de-creases over 1 millisecond"""

        #print(f"set rate called with {time}")

        self.raw_rates[rate_index] = time

        a = time // 5041  # divide range 0..65536 into 0..13
        q = 1 << (a + 1)  # 2 to the power of that. 2**14 = 16 seconds
        val = 65536 // q  # todo - probably just have a series of linear regimes, this range feels wonky

        if rate_index == 2 or rate_index == 4:  # decay and release are negative rates
            val = -1 * val
        self.rates[rate_index] = val

    def gate(self, status):

        if status:
            self.phase = 1
            self.last_called = time.ticks_ms()
        else:
            self.phase = 4  # releasing

    def get(self):

        phase = self.phase
        if phase == 0:
            return 0  # not doing anything

        tdelta = time.ticks_diff(time.ticks_ms(), self.last_called)
        self.last_called = time.ticks_ms()

        self.bucket += self.rates[phase] * tdelta  # the rate of sustain is always 0 so doesn't change the bucket

        if self.bucket > self.max_level:
            self.bucket = self.max_level
            self.phase = 2  # move to decaying
        if self.bucket < self.sustain_level and phase == 2:
            self.bucket = self.sustain_level
            self.phase = 3
        if self.bucket < 0:
            self.bucket = 0
            self.phase = 0

        if self.inverted:
            return -1 * ((self.bucket * self.depth) >> 16)
        else:
            return (self.bucket * self.depth) >> 16

ADSRS = [None] * 9 * VOICE_COUNT
ACTIVE_ADSRS = 0  # assemble a bitmask on loading

try:
    with open("ADSRDATA.bin", "rb") as f:
        print("Loading ADSR settings")
        for x in range(9):
            accumulator = []
            while len(accumulator) < 6:
                raw_bytes = f.read(2)
                val = int.from_bytes(raw_bytes, "little")
                accumulator.append(val)

            if accumulator[4] > 0:  # depth is set, need to tell the voices to use this source
                ACTIVE_ADSRS |= 1 << x  # this gets written multiple times but doesn't really matter unless one day
                # we want different voices to have different settings.

            offset = 0
            for _ in range(VOICE_COUNT):
                ADSRS[x + offset] = LinearADSR(*accumulator)  # instantiate using the args we just read in
                #print(f"at offset {offset}, made an ADSR with these args: ", accumulator)
                offset += 9

except Exception as e:
    print(e)
    print("Didn't find ADSR settings file, making blank ones.")
    for x in range(9 * VOICE_COUNT):  # todo - properly calculate how many and don't instantiate for unused channels
        ADSRS.append(LinearADSR())  # address these by index, 9 per voice (COF is 9th channel, channel #8)

def save_adsrs():

    with open("ADSRDATA.bin", "wb") as f:
        for a in ADSRS:
            vals = a.export()
            for v in vals:
                f.write(v.to_bytes(2, "little"))