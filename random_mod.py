from random import getrandbits
import omni

def gen2():

    # x is the number of samples between inflections of a sequence of random linear segments
    # when x = 512, get on average one transition per 500 cycles (or about 5 secs at our current speed)
    # 256 -> 3 transitions
    # 128 -> about 7
    # lowest useful value probably about 16, so want 16..512 from the controller

    val = 0
    target = 2
    increment = 1
    count = 0

    while True:
        if count <= 0:
            target = getrandbits(17) - 65536
            while target == val:
                target = getrandbits(17) - 65536

            increment = (target - val) // omni.RANDOM_SLOPE
            if increment == 0:
                increment = 1 if target > val else -1

            count = omni.RANDOM_SLOPE

        val += increment
        count -= 1

        yield val

class RandomLFO:

    """Object that yields a value in the range -65536 to 65535, for doing noise modulation."""

    def __init__(self):

        self.gen = gen2()
        self.depth = 0

    def get(self):

        return next(self.gen) * self.depth >> 16


RANDOM_MOD_SOURCES = []

for x in range(9):
    RANDOM_MOD_SOURCES.append(RandomLFO())