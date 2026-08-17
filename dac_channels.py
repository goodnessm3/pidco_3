# defines what the physical DAC channels control on the board

DAC_SUBOCTAVE = 0
DAC_VCA = 1
DAC_INTEGRATOR = 2
DAC_RESONANCE = 3
DAC_DUMMY = 5  # write 0 to this pin to force a chip select and new sample of the COF voltage
DAC_PWM = 6
DAC_WAVESELECT = 7
DAC_CUTOFF = 8  # not actually a channel on the voice card dac! Outboard, higher res DAC.
DAC_COMPARATOR = 9  # the second channel of the outboard DAC used to calibrate amplitude
# TODO - channel 9 needs different update mechanism without the wacky chip select SnH dance

PARAMETER_NAMES = ["SUB", "VCA", None, "RES", None, None, "DUTY", None, "CUTOFF"]
# only 5 of these make sense to adjust via hardware sliders
# cutoff, the fifth, is the imaginary 8th DAC channel (actually a separate DAC)

CUTOFF_FREQUENCY_DAC_ADDRESS = 7  # addressed in the same way as the boards, note this is the address of the chip