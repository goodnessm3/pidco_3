from machine import Pin, I2C
import time
from array import array
from custom_fifo import CustomFIFO

class LCD:
    def __init__(self, i2c, topline, bottomline, addr=None, backlight_enable=1):

        self.topline = topline
        self.bottomline = bottomline
        self.bus = i2c
        self.addr = self.scanAddress(addr)
        self.backlight_enable = backlight_enable
        self.txbuf = bytearray(4)  # don't allocate it every time we write
        self.send_data(0x33, 0)  # Must initialize to 8-line mode at first
        time.sleep(0.005)
        self.send_data(0x32, 0)  # Then initialize to 4-line mode
        time.sleep(0.005)
        self.send_data(0x28, 0)  # 2 Lines & 5*7 dots
        time.sleep(0.005)
        self.send_data(0x0C, 0)  # Enable display without cursor
        time.sleep(0.005)
        self.send_data(0x01, 0)  # Clear Screen
        self.bus.writeto(self.addr, bytearray([0x08]))

        #self.queue = []  # a list of characters to write out to the display. Process one of these instructions
        # per 50 microseconds
        self.last_time = time.ticks_us()  # when did we last write to the display? Must wait 50 us between instructions
        # so do nothing if we are asked to update faster than this

        self.run_queue = CustomFIFO(16)
        self.pos_queue = CustomFIFO(16)

        self.pos = 0  # position in the framebuffer to start sending characters
        self.line = 0  # top or bottom line
        self.update_counter = 0  # decrement this until the update is finished, then look for a new position

    def scanAddress(self, addr):

        devices = self.bus.scan()
        if len(devices) == 0:
            raise Exception("No LCD found")
        if addr is not None:
            if addr in devices:
                return addr
            else:
                raise Exception(f"LCD at 0x{addr:2X} not found")
        elif 0x27 in devices:
            return 0x27
        elif 0x3F in devices:
            return 0x3F
        else:
            raise Exception("No LCD found")

    def update_old(self, lists):

        """Given the two lists of (position, chars) from the DisplayManager class, update internal queue
        accordingly"""

        top, bottom = lists
        if not (top or bottom):
            return
        self.queue.extend(self.build_instruction_queue(top, 0))
        self.queue.extend(self.build_instruction_queue(bottom, 1))

        #print(self.queue)

    def update(self, pos, length):

        """Tell the display to start writing length characters starting at position pos.
        Positions in bottom line are from 16 to 31."""

        self.run_queue.put(length)
        self.pos_queue.put(pos)

    def draw_screen(self):

        delta = time.ticks_diff(time.ticks_us(), self.last_time)
        if delta < 50:
            print("too soon!")
            return

        if self.update_counter == 0:  # we finished the last update, time to get a new one
            runlen = self.run_queue.get()
            if not runlen:
                return

            self.pos = self.pos_queue.get()

            if self.pos > 15:
                self.line = 1
                self.pos -= 15
            else:
                self.line = 0

            self.update_counter = runlen
            self.send_data(0x80 + 0x40 * self.line + self.pos, 0)

        if self.line == 0:
            letter = self.topline[self.pos]
        else:
            letter = self.bottomline[self.pos]

        flag = 1  # todo - deal with zeros, need to get bits from self.cmd_flag_queue

        # might be nothing to do in which case we just popped from an empty list
        #print(dat, cmd)
        self.send_data(letter, flag)

        self.pos += 1
        self.update_counter -= 1
        self.last_time = time.ticks_us()


    def build_instruction_queue(self, ls, line):

        """given a list of update tuples, break it into instructions to be sent to the LCD screen"""
        # only need to position the cursor once, then it auto-increments
        # need to tell it whether it's on line 0 (top) or 1 to set the y address appropriately

        out = []
        for loc, chrs in ls:
            out.append((0x80 + 0x40 * line + loc, 0))  # position cursor and 0 = command, not data
            for c in chrs:
                #out.append((ord(c), 1))
                out.append((c, 1))

        return out


    def send_data(self, data, rs):

        """rs = 1: data, 0: command"""
        RS = 0x01 if rs else 0x00
        BL = 0x08
        EN = 0x04

        high = (data & 0xF0) | RS | BL
        low = ((data << 4) & 0xF0) | RS | BL

        self.txbuf[0] = high | EN
        self.txbuf[1] = high
        self.txbuf[2] = low | EN
        self.txbuf[3] = low

        print("wrote ", high, low, " to lcd")
        self.bus.writeto(self.addr, self.txbuf)

        #  time.sleep_us(40)  # no explicit sleep, just check in the calling fxn whether we've waited long enough

    def position_cursor(self, x, y):

        if x < 0:
            x = 0
        if x > 15:
            x = 15
        if y < 0:
            y = 0
        if y > 1:
            y = 1

        # calculate cursor address and send it
        addr = 0x80 + 0x40 * y + x
        self.send_data(addr, 0)


    def clear(self):
        self.send_data(0x01, 0)  # Clear Screen


"""

if __name__ == "__main__":
    i2c = I2C(0, scl=Pin(17), sda=Pin(16))  # for driving the LCD display
    import random
    import time
    letters = [chr(x) for x in range(65, 91)]
    LC = LCD(i2c)

    LC.message("Loading...")
    time.sleep(1)
    while True:
        st = ""
        for q in range(0, 12):
            st += letters[random.randint(0, 25)]
        LC.message(st)
        time.sleep(0.1)

"""