# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""The TLV320DAC3100's clocks, and the rate the I2S output really runs at."""

import time

import microcontroller

MCLK_HZ = 15_000_000

# 88.2 and 96 kHz, which the TLV library's MCLK table stops short of:
# PLL 15 MHz * J.D to 64 * 16 * rate, NDAC 2, MDAC 8, DOSR 64. That leaves the
# DAC's DSP MDAC * DOSR = 512 clocks per sample (half rate with DOSR 64 left
# it 64 and played slow and garbled). Processing block 8 is filter B, for rates
# above 48 kHz.
HIGH_RATES = {88200: (6, 211), 96000: (6, 5536)}  # J, D


def set_clocks(dac, rate):
    """Set the TLV's clocks for `rate`."""
    if rate not in HIGH_RATES:
        dac.configure_clocks(sample_rate=rate, bit_depth=16, mclk_freq=MCLK_HZ)
        dac._page0._write_register(0x3C, 1)  # processing block 1, filter A
        return
    dac.configure_clocks(sample_rate=rate // 2, bit_depth=16, mclk_freq=MCLK_HZ)  # format, muxes
    j, d = HIGH_RATES[rate]
    p0 = dac._page0
    p0._set_bits(0x3F, 0x03, 6, 0b00)  # DACs off
    p0._write_register(0x05, 0x11)  # PLL off, P 1, R 1
    p0._write_register(0x06, j)
    p0._write_register(0x07, d >> 8)
    p0._write_register(0x08, d & 0xFF)
    p0._write_register(0x05, 0x91)  # PLL on
    time.sleep(0.01)
    p0._write_register(0x0B, 0x82)  # NDAC 2
    p0._write_register(0x0C, 0x88)  # MDAC 8
    p0._write_register(0x0D, 0)  # DOSR 64
    p0._write_register(0x0E, 64)
    p0._write_register(0x3C, 8)
    p0._set_bits(0x3F, 0x03, 6, 0b11)


def output_rate(rate):
    """The sample rate the I2S output really runs at. CircuitPython clocks
    the PIO at 6 x 32 x rate from the CPU clock with a 1/256 divider, rounded
    up (ports/raspberrypi/common-hal/rp2pio/StateMachine.c). At 300 MHz, 96 kHz
    comes out at 95992 Hz, 80 ppm slow. The player would drift 5 ms a minute
    timing its halves from the nominal rate, and after about a minute it wrote
    halves before the output had copied them: clicks, with no underrun counted."""
    f256 = microcontroller.cpu.frequency * 256
    want = 6 * 32 * rate
    div = f256 // want
    if f256 % div:  # the same test as StateMachine.c
        div += 1
    return f256 / div / (6 * 32)
