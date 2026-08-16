from array import array
import random

dummy_lists = ["abcdefghabcdefgh"
               "abcdefgh123defgh",
               "abc123ghabcdefgh",
               "a123efghabcdefgh",
               "abcdefgha123efgh"]

def listgen():

    idx = 0
    while 1:
        yield dummy_lists[idx]
        idx += 1
        if idx < len(dummy_lists):
            idx = 0

LG = listgen()

class DisplayManager:

    def __init__(self):

        self.line1 = array("B", [0] * 16)
        self.line2 = array("B", [0] * 16)

    def update(self):

        #line1, line2 = self.get_lines(update_tup)

        line1 = array("B", list([ord(x) for x in next(LG)]))
        line2 = array("B", list([ord(x) for x in next(LG)]))

        diff1 = self.diff_line(self.line1, line1)
        diff2 = self.diff_line(self.line2, line2)

        #self.line1 = line1
        #self.line2 = line2

        return diff1, diff2  # lists of tuples [(index, run of characters)]
        # this lets us only update the LCD characters that have changed

    def get_lines(self, update_tup):

        pass

    def diff_line(self, old_line, new_line):

        """Detect only the characters that changed"""

        #while len(new_line) < len(old_line):
            #new_line += " "  # add spaces to overwrite the longer old line

        oldlen = len(old_line)
        newlen = len(new_line)

        minlen = min(oldlen, newlen)

        runs = []  # start index and a run of characters that need to be replaced
        index = 0

        runstart = 0
        run = []
        accumulating = False

        while index < minlen:
            old = old_line[index]
            new = new_line[index]

            if old == new:
                if run:  # don't append the empty list first time round
                    accumulating = False
                    runs.append((runstart, run))
                    runstart = 0
                    run = []
            else:
                if not accumulating:
                    accumulating = True
                    runstart = index
                run.append(new)

            index += 1

        if accumulating:  # make sure we catch the run if the line was different right
            # up until the last character
            runs.append((runstart, run))

        if oldlen < len(new_line):
            runs.append((oldlen, new_line[oldlen:]))

        return runs